"""Default write denial: by behaviour, by policy and by source inspection."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nuos_modbus import PLATFORMS
from custom_components.nuos_modbus.const import VALIDATION_VALIDATED
from custom_components.nuos_modbus.registers import REGISTERS, REGISTERS_BY_KEY
from custom_components.nuos_modbus.write_policy import (
    READ_ONLY_PROFILE,
    WriteDeniedError,
    WriteProfile,
    async_guarded_write,
    check_write,
)

from .helpers import enable

PACKAGE = Path(__file__).parents[1] / "custom_components" / "nuos_modbus"
WRITE_CALLS = re.compile(
    r"\.(write_register|write_registers|write_coil|write_coils|mask_write_register|"
    r"read_write_registers|write_file_record)\("
)


async def test_no_write_during_setup_and_polling(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    nuos_unit: MockModbusUnit,
    writes: list[WriteEvent],
) -> None:
    """All entities enabled + repeated polling: zero writes reach the unit."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    keys = [r.key for r in config_entry.runtime_data.registers]
    await enable(hass, config_entry.entry_id, *[k for k in keys if k != "raw_holding_8"])
    for _ in range(3):
        await config_entry.runtime_data.coordinator.async_refresh()
    assert writes == []


def test_only_read_platforms() -> None:
    """No number/switch/select/button/climate/water_heater platform exists."""
    assert set(PLATFORMS) == {Platform.SENSOR, Platform.BINARY_SENSOR}
    modules = {p.stem for p in PACKAGE.glob("*.py")}
    forbidden = {"number", "switch", "select", "button", "climate", "water_heater", "text", "time"}
    assert not modules & forbidden
    assert not (PACKAGE / "services.yaml").exists()


def test_write_calls_only_in_write_policy() -> None:
    """The single (unused) write path is write_policy.async_guarded_write."""
    offenders = {
        p.name
        for p in PACKAGE.glob("*.py")
        if WRITE_CALLS.search(p.read_text(encoding="utf-8"))
    }
    assert offenders == {"write_policy.py"}
    callers = {
        p.name
        for p in PACKAGE.glob("*.py")
        if "async_guarded_write" in p.read_text(encoding="utf-8")
    }
    assert callers == {"write_policy.py"}


@pytest.mark.parametrize("register", REGISTERS, ids=lambda r: r.key)
def test_shipped_profile_denies_every_register(register) -> None:
    """READ_ONLY_PROFILE (the only shipped profile) refuses everything."""
    with pytest.raises(WriteDeniedError):
        check_write(READ_ONLY_PROFILE, register, register.minimum or 0)


def test_validated_profile_still_needs_every_condition() -> None:
    """A validated allow-all profile is still refused per register condition."""
    allow_all = WriteProfile("test", validated=True, allowed_keys=frozenset(REGISTERS_BY_KEY))
    with pytest.raises(WriteDeniedError, match="never writable"):
        check_write(allow_all, REGISTERS_BY_KEY["modbus_address"], 1)
    with pytest.raises(WriteDeniedError, match="never writable"):
        check_write(allow_all, REGISTERS_BY_KEY["defrost_type"], 1)
    with pytest.raises(WriteDeniedError, match="not documented as writable"):
        check_write(allow_all, REGISTERS_BY_KEY["t2_tank"], 450)
    with pytest.raises(WriteDeniedError, match="not validated"):
        check_write(allow_all, REGISTERS_BY_KEY["t_soll"], 50)
    validated = replace(REGISTERS_BY_KEY["t_soll"], validation=VALIDATION_VALIDATED)
    with pytest.raises(WriteDeniedError, match="outside documented range"):
        check_write(allow_all, validated, 63)
    check_write(allow_all, validated, 50)  # architecture works when all hold


def test_unvalidated_profile_denied_even_if_allowed() -> None:
    """validated=False refuses even an explicitly allowed key."""
    profile = WriteProfile("draft", validated=False, allowed_keys=frozenset({"t_soll"}))
    with pytest.raises(WriteDeniedError, match="not validated"):
        check_write(profile, REGISTERS_BY_KEY["t_soll"], 50)


async def test_guarded_write_denied_sends_nothing(
    nuos_unit: MockModbusUnit, writes: list[WriteEvent]
) -> None:
    """A denied write never reaches the transport."""
    with pytest.raises(WriteDeniedError):
        await async_guarded_write(
            nuos_unit, READ_ONLY_PROFILE, REGISTERS_BY_KEY["t_soll"], 4, 50
        )
    assert writes == []
