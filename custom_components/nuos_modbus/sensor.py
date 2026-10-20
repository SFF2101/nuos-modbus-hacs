"""Sensor platform (read only)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NuosConfigEntry
from .decode import decode_numeric, decode_option
from .entity import NuosEntity
from .registers import Register

PARALLEL_UPDATES = 0  # coordinator-driven

_UNITS = {
    "°C": UnitOfTemperature.CELSIUS,
    "h": UnitOfTime.HOURS,
    "min": UnitOfTime.MINUTES,
    "d": UnitOfTime.DAYS,
    "%": PERCENTAGE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one sensor per sensor-type register of the model profile."""
    async_add_entities(
        NuosSensor(entry, register)
        for register in entry.runtime_data.registers
        if register.platform == "sensor"
    )


class NuosSensor(NuosEntity, SensorEntity):
    """A numeric, enumeration or raw register."""

    def __init__(self, entry: NuosConfigEntry, register: Register) -> None:
        """Map the register metadata onto sensor attributes."""
        super().__init__(entry, register)
        if register.raw_only:
            return  # unit-less raw value; never given a device class
        if register.options is not None:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(register.options.values())
            return
        if register.unit is not None:
            self._attr_native_unit_of_measurement = _UNITS[register.unit]
        if register.device_class == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        if register.state_class == "measurement":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | float | str | None:
        """Decode the raw register."""
        raw = self.raw
        if raw is None:
            return None
        if self.register.options is not None and not self.register.raw_only:
            return decode_option(self.register, raw)
        return decode_numeric(self.register, raw)
