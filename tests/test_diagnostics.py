"""Diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nuos_modbus.diagnostics import async_get_config_entry_diagnostics

from .conftest import HOST


async def test_diagnostics(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["data"]["host"] == "**REDACTED**"
    assert HOST not in str(diag)
    assert diag["write_profile"] == {"name": "read_only", "validated": False, "allowed_keys": []}
    assert diag["read_plan"] == [{"space": "holding", "address": 8, "count": 1}]
    assert diag["raw"] == {"holding:8": 12}
    assert diag["stats"]["requests"] == 1
    assert diag["shared_connection"] == [
        {"connected": True, "units": {config_entry.entry_id: [1]}}
    ]
    assert diag["registers"]["t2_tank"]["validation"] == "not_validated"
