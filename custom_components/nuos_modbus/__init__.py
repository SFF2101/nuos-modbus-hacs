"""Domotec NUOS hot-water heat pump over a Modbus TCP gateway (read only).

The connection comes from Home Assistant's official Modbus integration through
``homeassistant.components.modbus.async_get_unit`` (HA 2026.10+). That helper
shares one connection per endpoint between integrations that use it, serialises
their requests, and releases the hold when this config entry unloads. The
deprecated ``get_hub`` is not used.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from modbus_connection import ModbusTcpParams

from .const import (
    CONF_ADDRESS_OFFSET,
    CONF_DATAPOINT_SPACE,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_ADDRESS_OFFSET,
    DEFAULT_DATAPOINT_SPACE,
    DEFAULT_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
)
from .coordinator import NuosCoordinator, RegisterKey
from .registers import (
    Register,
    UnsupportedModelError,
    registers_for_model,
    resolve_address,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class NuosRuntimeData:
    """Per-entry runtime objects."""

    coordinator: NuosCoordinator
    registers: tuple[Register, ...]
    addresses: dict[str, RegisterKey]
    """Register key -> (space, PDU address) as configured."""


type NuosConfigEntry = ConfigEntry[NuosRuntimeData]


def unique_id_for(entry: ConfigEntry, register: Register) -> str:
    """Stable entity unique ID."""
    return f"{entry.entry_id}_{register.key}"


def _enabled_keys(
    hass: HomeAssistant, entry: ConfigEntry, registers: tuple[Register, ...]
) -> set[str]:
    """Keys whose entity is (or will be, on first setup) enabled.

    Disabled entities are not polled at all, so enabling a candidate entity
    (which reloads the entry) is the only way its register gets read.
    """
    ent_reg = er.async_get(hass)
    existing = {
        e.unique_id: e for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }
    enabled: set[str] = set()
    for register in registers:
        reg_entry = existing.get(unique_id_for(entry, register))
        if reg_entry is None:
            if register.enabled_default:
                enabled.add(register.key)
        elif reg_entry.disabled_by is None:
            enabled.add(register.key)
    return enabled


async def async_setup_entry(hass: HomeAssistant, entry: NuosConfigEntry) -> bool:
    """Set up one NUOS unit."""
    try:
        registers = registers_for_model(entry.data[CONF_MODEL])
    except UnsupportedModelError as err:
        raise ConfigEntryError(str(err)) from err

    options = entry.options
    datapoint_space = options.get(CONF_DATAPOINT_SPACE, DEFAULT_DATAPOINT_SPACE)
    address_offset = options.get(CONF_ADDRESS_OFFSET, DEFAULT_ADDRESS_OFFSET)
    scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    addresses: dict[str, RegisterKey] = {}
    for register in registers:
        try:
            addresses[register.key] = resolve_address(
                register, datapoint_space=datapoint_space, address_offset=address_offset
            )
        except ValueError:
            continue  # offset -1 on address 0: that entity stays unavailable

    try:
        unit = async_get_unit(
            hass,
            entry,
            ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
            entry.data[CONF_UNIT_ID],
        )
    except HomeAssistantError as err:
        # Same endpoint already held with different link settings.
        raise ConfigEntryError(str(err)) from err
    unit.require_timeout(REQUEST_TIMEOUT)

    enabled = _enabled_keys(hass, entry, registers)
    targets = {addresses[k] for k in enabled if k in addresses}
    coordinator = NuosCoordinator(hass, entry, unit, targets, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NuosRuntimeData(coordinator, registers, addresses)
    # Option changes reload the entry via OptionsFlowWithReload.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NuosConfigEntry) -> bool:
    """Unload; async_get_unit's hold is released via entry.async_on_unload."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
