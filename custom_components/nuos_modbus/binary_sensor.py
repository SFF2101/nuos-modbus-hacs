"""Binary sensor platform (read only)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NuosConfigEntry
from .decode import decode_binary
from .entity import NuosEntity
from .registers import Register

PARALLEL_UPDATES = 0  # coordinator-driven


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one binary sensor per on/off register of the model profile."""
    async_add_entities(
        NuosBinarySensor(entry, register)
        for register in entry.runtime_data.registers
        if register.platform == "binary_sensor"
    )


class NuosBinarySensor(NuosEntity, BinarySensorEntity):
    """A documented 0/1 register."""

    def __init__(self, entry: NuosConfigEntry, register: Register) -> None:
        """Map the device class."""
        super().__init__(entry, register)
        if register.device_class == "running":
            self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool | None:
        """On for 1, off for 0, unknown for any undocumented value."""
        raw = self.raw
        return None if raw is None else decode_binary(raw)
