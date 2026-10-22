"""Display texts validated on the installed unit's own display (DAI-IN-639).

Only the exact codes photographed on the NUOS 400 B (VTC200, VT15) display are
mapped. Every other raw value has no display text, the entity state stays the
raw register value, and no write path is created.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import yaml

from custom_components.nuos_modbus.const import DISPLAY_EVIDENCE
from custom_components.nuos_modbus.registers import REGISTERS, REGISTERS_BY_KEY
from custom_components.nuos_modbus.write_policy import (
    READ_ONLY_PROFILE,
    WriteDeniedError,
    check_write,
)

from .helpers import enable, entity_id

CATALOGUE = Path(__file__).parents[1] / "docs" / "registers" / "modbus.yaml"

# Exactly what the owner's photos showed on 2026-10-22, next to the raw value
# Home Assistant read at the same time.
EXPECTED = {
    "wp_ls": {1: "High"},  # FanSpeed High, holding 15 = 1
    "fan_pause": {2: "30m/30s"},  # FanPause 30m/30s, holding 23 = 2
    "language": {0: "English"},  # Language English, holding 25 = 0
    "defrost_type": {1: "Gas"},  # Defrost Gas, holding 26 = 1
    "status_bits": {2: "Standby"},  # InfoMode Standby, input 16 = 2
}


def test_exact_display_mappings_only() -> None:
    """The five validated mappings exist; no other register has display text."""
    actual = {r.key: r.display_values for r in REGISTERS if r.display_values is not None}
    assert actual == EXPECTED


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_mapped_registers_stay_raw(key: str) -> None:
    """State semantics unchanged: raw value, no unit, no device/state class."""
    register = REGISTERS_BY_KEY[key]
    assert register.raw_only
    assert register.options is None
    assert register.unit is None
    assert register.device_class is None
    assert register.state_class is None
    assert register.validation == "not_validated"


def test_catalogue_records_the_same_validated_codes() -> None:
    cat = yaml.safe_load(CATALOGUE.read_text(encoding="utf-8"))
    entries = [e for section in ("parameters", "datapoints") for e in cat[section]]
    recorded = {e["key"]: e["display_validated"] for e in entries if "display_validated" in e}
    assert recorded == EXPECTED


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_display_mapped_registers_are_not_writable(key: str) -> None:
    with pytest.raises(WriteDeniedError):
        check_write(READ_ONLY_PROFILE, REGISTERS_BY_KEY[key], 0)


async def test_display_text_attribute_and_unmapped_fallback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    nuos_unit: MockModbusUnit,
    writes: list[WriteEvent],
) -> None:
    """Validated codes get their text; any other code gets None; state is raw."""
    nuos_unit.holding.update({15: 1, 23: 2, 25: 0, 26: 1})
    nuos_unit.input.update({16: 2})
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await enable(hass, config_entry.entry_id, *EXPECTED)

    shown = {"wp_ls": "1", "fan_pause": "2", "language": "0", "defrost_type": "1", "status_bits": "2"}
    for key, raw in shown.items():
        state = hass.states.get(entity_id(hass, config_entry.entry_id, key))
        assert state.state == raw, key
        assert state.attributes["raw_value"] == int(raw), key
        assert state.attributes["display_text"] == EXPECTED[key][int(raw)], key
        assert state.attributes["display_text_evidence"] == DISPLAY_EVIDENCE
        assert "unit_of_measurement" not in state.attributes, key

    # Codes never seen on the display: raw state kept, no invented text.
    nuos_unit.holding.update({15: 0, 23: 5, 25: 3, 26: 2})
    nuos_unit.input.update({16: 4})
    await config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    unseen = {"wp_ls": "0", "fan_pause": "5", "language": "3", "defrost_type": "2", "status_bits": "4"}
    for key, raw in unseen.items():
        state = hass.states.get(entity_id(hass, config_entry.entry_id, key))
        assert state.state == raw, key
        assert state.attributes["display_text"] is None, key

    # Registers without validated codes carry no display_text attribute.
    t2 = hass.states.get(entity_id(hass, config_entry.entry_id, "raw_holding_8"))
    assert "display_text" not in t2.attributes
    assert writes == []
