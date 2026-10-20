"""Config and options flow."""

from __future__ import annotations

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.components.modbus.connection import async_get_connection_info
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from modbus_connection import ModbusConnectionError, ModbusTlsParams
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, ReadEvent
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nuos_modbus.const import (
    CONF_ADDRESS_OFFSET,
    CONF_DATAPOINT_SPACE,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DOMAIN,
    MODEL_NUOS_400_B,
)

from .conftest import HOST, PORT

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT, CONF_UNIT_ID: 1, CONF_MODEL: MODEL_NUOS_400_B}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


async def test_user_flow_creates_entry_with_one_read(
    hass: HomeAssistant, nuos_unit: MockModbusUnit
) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == f"{HOST}:{PORT}:1"
    assert nuos_unit.read_events[0] == ReadEvent("holding", 8, 1)


async def test_probe_releases_temporary_hold(
    hass: HomeAssistant, nuos_unit: MockModbusUnit
) -> None:
    """The config flow probe leaves no connection behind."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.nuos_modbus.async_setup_entry",
            _noop_setup,
        )
        result = await _start(hass)
        await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert async_get_connection_info(hass) == []


async def _noop_setup(hass, entry) -> bool:
    return True


async def test_cannot_connect(hass: HomeAssistant, nuos_unit: MockModbusUnit) -> None:
    nuos_unit.fail_requests(ModbusConnectionError("down"))
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_endpoint_in_use(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    async with async_get_temporary_unit(hass, ModbusTlsParams(host=HOST, port=PORT), 9):
        result = await _start(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "endpoint_in_use"}


async def test_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert nuos_unit.read_events == []  # aborted before any Modbus request


@pytest.mark.parametrize(
    "bad",
    [
        {CONF_MODEL: "nuos_extra"},
        {CONF_UNIT_ID: 0},
        {CONF_UNIT_ID: 248},
        {CONF_PORT: 0},
    ],
)
async def test_schema_rejects_invalid_input(
    hass: HomeAssistant, nuos_unit: MockModbusUnit, bad: dict
) -> None:
    result = await _start(hass)
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], {**USER_INPUT, **bad})
    assert nuos_unit.read_events == []


async def test_options_flow_sets_and_reloads(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 300, CONF_DATAPOINT_SPACE: "holding", CONF_ADDRESS_OFFSET: "minus_1"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_SCAN_INTERVAL: 300,
        CONF_DATAPOINT_SPACE: "holding",
        CONF_ADDRESS_OFFSET: -1,
    }
    coordinator = config_entry.runtime_data.coordinator
    assert coordinator.update_interval.total_seconds() == 300


async def test_options_reject_too_fast_polling(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_SCAN_INTERVAL: 5, CONF_DATAPOINT_SPACE: "input", CONF_ADDRESS_OFFSET: "zero"},
        )
