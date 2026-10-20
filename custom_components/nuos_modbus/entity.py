"""Base entity for NUOS registers."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NuosConfigEntry, unique_id_for
from .const import CONF_MODEL, DOMAIN, MANUFACTURER, MODEL_NAMES
from .coordinator import NuosCoordinator
from .registers import Register


class NuosEntity(CoordinatorEntity[NuosCoordinator]):
    """An entity backed by exactly one register."""

    _attr_has_entity_name = True

    def __init__(self, entry: NuosConfigEntry, register: Register) -> None:
        """Bind the entity to its register."""
        super().__init__(entry.runtime_data.coordinator)
        self.register = register
        self._key = entry.runtime_data.addresses.get(register.key)
        self._attr_unique_id = unique_id_for(entry, register)
        self._attr_name = register.name
        self._attr_entity_registry_enabled_default = register.enabled_default
        if register.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        # One isolated device per config entry; deliberately no via_device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL_NAMES[entry.data[CONF_MODEL]],
            name="NUOS",
        )

    @property
    def raw(self) -> int | None:
        """The raw register value from the last update, if any."""
        if self._key is None or self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        """Unavailable when the update failed or this register was not read."""
        return super().available and self.raw is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Provenance and validation state, so candidates are never mistaken."""
        space, address = self._key if self._key else (None, None)
        attrs: dict[str, Any] = {
            "register_space": space,
            "register_address": address,
            "function_code": 4 if space == "input" else 3,
            "validation": self.register.validation,
            "raw_value": self.raw,
        }
        if self.register.source_page is not None:
            attrs["source"] = f"NUOS II manual 09/2026 p.{self.register.source_page}"
        return attrs
