"""Polling coordinator: reads only what enabled entities need."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import (
    GatewayPathUnavailableError,
    GatewayTargetError,
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusError,
    ModbusUnit,
)

from .const import DOMAIN, MAX_BLOCK_LENGTH
from .decode import ReadBlock, plan_reads

_LOGGER = logging.getLogger(__name__)

type RegisterKey = tuple[str, int]  # (space, PDU address)

# Exception codes meaning "this address/function does not exist here". They
# mark the address unsupported instead of failing the whole update.
_UNSUPPORTED = (IllegalDataAddressError, IllegalFunctionError)
# The gateway cannot reach the serial device: the NUOS is unavailable.
_GATEWAY_DOWN = (GatewayPathUnavailableError, GatewayTargetError)


@dataclass
class ReadStats:
    """Counters exposed through diagnostics."""

    requests: int = 0
    failed_updates: int = 0
    last_error: str | None = None
    unsupported: dict[str, str] = field(default_factory=dict)


class NuosCoordinator(DataUpdateCoordinator[dict[RegisterKey, int]]):
    """Read the planned registers of one NUOS unit."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        unit: ModbusUnit,
        targets: set[RegisterKey],
        scan_interval: int,
    ) -> None:
        """Initialise with the unit and the (space, address) set to poll."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.unit = unit
        self.targets = set(targets)
        self.stats = ReadStats()
        self._unsupported: set[RegisterKey] = set()

    @property
    def plan(self) -> list[ReadBlock]:
        """The read requests issued each cycle."""
        return plan_reads(self.targets - self._unsupported, MAX_BLOCK_LENGTH)

    async def _read(self, block: ReadBlock) -> list[int]:
        self.stats.requests += 1
        if block.space == "input":
            return await self.unit.read_input_registers(block.address, block.count)
        return await self.unit.read_holding_registers(block.address, block.count)

    async def _async_update_data(self) -> dict[RegisterKey, int]:
        data: dict[RegisterKey, int] = {}
        try:
            for block in self.plan:
                try:
                    values = await self._read(block)
                except _UNSUPPORTED:
                    if block.count == 1:
                        self._mark_unsupported(block.space, block.address)
                        continue
                    # Retry one register at a time to isolate the bad address.
                    for address in block.addresses:
                        single = ReadBlock(block.space, address, 1)
                        try:
                            data[(block.space, address)] = (await self._read(single))[0]
                        except _UNSUPPORTED:
                            self._mark_unsupported(block.space, address)
                    continue
                if len(values) != block.count:
                    raise UpdateFailed(
                        f"short read at {block.space} {block.address}: "
                        f"{len(values)} of {block.count}"
                    )
                for address, value in zip(block.addresses, values, strict=True):
                    data[(block.space, address)] = value
        except _GATEWAY_DOWN as err:
            self._failed(err)
            raise UpdateFailed(f"gateway cannot reach NUOS unit: {err!r}") from err
        except ModbusError as err:
            self._failed(err)
            raise UpdateFailed(f"Modbus error: {err!r}") from err
        except TimeoutError as err:
            self._failed(err)
            raise UpdateFailed("Modbus request timed out") from err
        self.stats.last_error = None
        return data

    def _failed(self, err: BaseException) -> None:
        self.stats.failed_updates += 1
        self.stats.last_error = repr(err)

    def _mark_unsupported(self, space: str, address: int) -> None:
        """Stop polling an address the device rejects (until reload)."""
        self._unsupported.add((space, address))
        self.stats.unsupported[f"{space}:{address}"] = "illegal address/function"
        _LOGGER.warning(
            "NUOS rejected %s register %s; it is no longer polled until reload",
            space,
            address,
        )

    def is_unsupported(self, key: RegisterKey) -> bool:
        """Whether the device rejected this register."""
        return key in self._unsupported
