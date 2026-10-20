"""Setup, polling, failure/recovery and lifecycle against real HA 2026.10.2."""

from __future__ import annotations

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.components.modbus.connection import async_get_connection_info
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from modbus_connection import (
    GatewayTargetError,
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTlsParams,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, ReadEvent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nuos_modbus.const import (
    CONF_ADDRESS_OFFSET,
    CONF_DATAPOINT_SPACE,
    CONF_MODEL,
    VALIDATION_READ_OK,
)
from custom_components.nuos_modbus.registers import registers_for_model

from .conftest import HOST, PORT
from .helpers import enable, entity_id


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _refresh(entry: MockConfigEntry) -> None:
    await entry.runtime_data.coordinator.async_refresh()


async def test_default_setup_reads_only_the_pilot_register(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """Out of the box: exactly one FC03 read of holding 8, shown raw."""
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert nuos_unit.read_events == [ReadEvent("holding", 8, 1)]
    assert nuos_unit.required_timeout == 5.0

    state = hass.states.get(entity_id(hass, config_entry.entry_id, "raw_holding_8"))
    assert state.state == "12"
    assert "unit_of_measurement" not in state.attributes  # never a temperature
    assert "device_class" not in state.attributes
    assert state.attributes["validation"] == VALIDATION_READ_OK
    assert state.attributes["function_code"] == 3


async def test_all_candidates_disabled_by_default(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """Only the pilot diagnostic is enabled; every candidate is disabled."""
    await _setup(hass, config_entry)
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    assert len(entries) == len(registers_for_model(config_entry.data[CONF_MODEL]))
    enabled = [e.unique_id for e in entries if e.disabled_by is None]
    assert enabled == [f"{config_entry.entry_id}_raw_holding_8"]
    assert all(
        e.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for e in entries
        if e.disabled_by is not None
    )


async def test_enabled_candidate_t2_reads_input_space_by_default(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """T2 candidate uses FC04 input 8 — distinct from the FC03 holding 8 pilot."""
    await _setup(hass, config_entry)
    await enable(hass, config_entry.entry_id, "t2_tank")
    assert ReadEvent("input", 8, 1) in nuos_unit.read_events
    t2 = hass.states.get(entity_id(hass, config_entry.entry_id, "t2_tank"))
    assert t2.state == "45.2"
    assert t2.attributes["unit_of_measurement"] == "°C"
    assert t2.attributes["validation"] == "not_validated"
    pilot = hass.states.get(entity_id(hass, config_entry.entry_id, "raw_holding_8"))
    assert pilot.state == "12"


async def test_datapoint_space_option_holding_reproduces_ambiguity(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """With FC03 for datapoints, T2 decodes the site value 12 as 1.2 °C.

    This is the implausible reading that keeps the question open; the single
    holding-8 request is shared by both entities (deduplicated).
    """
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_DATAPOINT_SPACE: "holding"}
    )
    await _setup(hass, config_entry)
    await enable(hass, config_entry.entry_id, "t2_tank")
    nuos_unit.read_events.clear()
    await _refresh(config_entry)
    assert nuos_unit.read_events == [ReadEvent("holding", 8, 1)]
    assert hass.states.get(entity_id(hass, config_entry.entry_id, "t2_tank")).state == "1.2"


async def test_address_offset_applies_to_catalogue_not_pilot(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """Offset -1 moves t_soll from 4 to 3; the pilot stays at holding 8."""
    hass.config_entries.async_update_entry(config_entry, options={CONF_ADDRESS_OFFSET: -1})
    await _setup(hass, config_entry)
    await enable(hass, config_entry.entry_id, "t_soll")
    nuos_unit.read_events.clear()
    await _refresh(config_entry)
    assert sorted(nuos_unit.read_events, key=lambda e: e.address) == [
        ReadEvent("holding", 3, 1),
        ReadEvent("holding", 8, 1),
    ]


async def test_illegal_address_isolated_and_not_repolled(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """A rejected register goes unavailable; its neighbours keep working."""
    await _setup(hass, config_entry)
    nuos_unit.fail_read(7, IllegalDataAddressError("x"), register_type="input")
    await enable(hass, config_entry.entry_id, "t1_evaporator", "t2_tank")
    coordinator = config_entry.runtime_data.coordinator
    assert coordinator.is_unsupported(("input", 7))
    assert hass.states.get(entity_id(hass, config_entry.entry_id, "t1_evaporator")).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(hass, config_entry.entry_id, "t2_tank")).state == "45.2"
    nuos_unit.read_events.clear()
    await _refresh(config_entry)
    assert ReadEvent("input", 7, 1) not in nuos_unit.read_events
    assert all(e.address != 7 for e in nuos_unit.read_events)


async def test_connection_failure_then_recovery(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """Lost link -> unavailable; restored link -> value returns."""
    await _setup(hass, config_entry)
    eid = entity_id(hass, config_entry.entry_id, "raw_holding_8")
    nuos_unit.fail_requests(ModbusConnectionError("gateway gone"))
    await _refresh(config_entry)
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == STATE_UNAVAILABLE
    stats = config_entry.runtime_data.coordinator.stats
    assert stats.failed_updates == 1
    assert "gateway gone" in stats.last_error

    nuos_unit.fail_requests(None)
    nuos_unit._conn.simulate_connection_lost()  # next request reconnects
    await _refresh(config_entry)
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == "12"
    assert stats.last_error is None


async def test_gateway_target_error_is_update_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """Gateway exception 0x0B (target not responding) fails the update."""
    await _setup(hass, config_entry)
    nuos_unit.fail_requests(GatewayTargetError("no answer"))
    await _refresh(config_entry)
    assert config_entry.runtime_data.coordinator.last_update_success is False


async def test_unreachable_at_startup_retries(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """No answer during setup -> SETUP_RETRY (HA retries later)."""
    nuos_unit.fail_requests(ModbusConnectionError("down"))
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_releases_shared_connection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    nuos_unit: MockModbusUnit,
) -> None:
    """async_get_unit's hold is released on unload; HA closes the connection."""
    await _setup(hass, config_entry)
    [info] = async_get_connection_info(hass)
    assert info.endpoint == ("tcp", HOST, PORT)
    assert info.units == {config_entry.entry_id: [1]}
    closes = mock_connection.close_calls
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert async_get_connection_info(hass) == []
    assert mock_connection.close_calls == closes + 1


async def test_unsupported_model_is_setup_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, nuos_unit: MockModbusUnit
) -> None:
    """An unknown model never gets a guessed register map."""
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_MODEL: "nuos_extra"}
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert nuos_unit.read_events == []


async def test_endpoint_held_with_other_link_settings_is_setup_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_connection: MockModbusConnection
) -> None:
    """Same endpoint, different link settings -> refuse instead of hijacking."""
    async with async_get_temporary_unit(hass, ModbusTlsParams(host=HOST, port=PORT), 9):
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_only_configured_unit_is_ever_addressed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    nuos_unit: MockModbusUnit,
) -> None:
    """Non-interference by construction: unit 2 (Dimplex) receives nothing.

    Every entity enabled, several refreshes: all traffic goes to unit 1 and is
    reads only.
    """
    dimplex = mock_connection.for_unit(2)
    await _setup(hass, config_entry)
    keys = [r.key for r in config_entry.runtime_data.registers if not r.enabled_default]
    await enable(hass, config_entry.entry_id, *keys)
    for _ in range(3):
        await _refresh(config_entry)
    assert dimplex.read_events == []
    assert set(mock_connection._units) == {1, 2}  # 2 only because this test created it
    assert nuos_unit.read_events
    assert {e.register_type for e in nuos_unit.read_events} <= {"holding", "input"}
