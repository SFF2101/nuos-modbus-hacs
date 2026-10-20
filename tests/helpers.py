"""Test helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.nuos_modbus.const import DOMAIN


def entity_id(hass: HomeAssistant, entry_id: str, key: str) -> str:
    """Entity id for a register key."""
    platform = None
    ent_reg = er.async_get(hass)
    for domain in ("sensor", "binary_sensor"):
        platform = ent_reg.async_get_entity_id(domain, DOMAIN, f"{entry_id}_{key}")
        if platform:
            return platform
    raise AssertionError(f"no entity for {key}")


async def enable(hass: HomeAssistant, entry_id: str, *keys: str) -> None:
    """Enable entities and reload the entry, as HA does after enabling."""
    ent_reg = er.async_get(hass)
    for key in keys:
        ent_reg.async_update_entity(entity_id(hass, entry_id, key), disabled_by=None)
    assert await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()
