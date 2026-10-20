"""Decoding, addressing and read planning (pure functions)."""

from __future__ import annotations

import pytest

from custom_components.nuos_modbus.const import MODEL_NUOS_400_B, MODEL_NUOS_II
from custom_components.nuos_modbus.decode import (
    ReadBlock,
    decode_binary,
    decode_numeric,
    decode_option,
    in_documented_range,
    plan_reads,
    to_signed16,
)
from custom_components.nuos_modbus.registers import (
    PILOT,
    REGISTERS_BY_KEY as R,
    UnsupportedModelError,
    registers_for_model,
    resolve_address,
)


def test_plan_coalesces_contiguous_and_splits_gaps() -> None:
    targets = {("input", 7), ("input", 8), ("input", 9), ("input", 19), ("holding", 8)}
    assert plan_reads(targets, 16) == [
        ReadBlock("holding", 8, 1),
        ReadBlock("input", 7, 3),
        ReadBlock("input", 19, 1),
    ]


def test_plan_never_bridges_undocumented_gap() -> None:
    """Parameter 24 (display 025) is undocumented: 23 and 25 stay separate."""
    assert plan_reads({("holding", 23), ("holding", 25)}, 16) == [
        ReadBlock("holding", 23, 1),
        ReadBlock("holding", 25, 1),
    ]


def test_plan_respects_max_block_and_dedupes() -> None:
    targets = [("holding", a) for a in range(4, 24)] + [("holding", 8)]
    blocks = plan_reads(targets, 16)
    assert blocks == [ReadBlock("holding", 4, 16), ReadBlock("holding", 20, 4)]
    with pytest.raises(ValueError):
        plan_reads(targets, 0)


def test_plan_empty() -> None:
    assert plan_reads(set(), 16) == []


@pytest.mark.parametrize(("raw", "signed"), [(0, 0), (452, 452), (0x7FFF, 32767), (0xFFEC, -20), (0x8000, -32768)])
def test_signed16(raw: int, signed: int) -> None:
    assert to_signed16(raw) == signed


def test_signed16_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        to_signed16(0x10000)


def test_temperature_scaling_and_sign() -> None:
    assert decode_numeric(R["t2_tank"], 452) == 45.2
    assert decode_numeric(R["t1_evaporator"], 0xFFEC) == -2.0
    assert decode_numeric(R["t_soll"], 50) == 50  # Dezimal 0


def test_pilot_and_raw_only_are_unscaled() -> None:
    assert decode_numeric(PILOT, 12) == 12
    assert decode_numeric(R["da0_output"], 1000) == 1000  # '1000 = 10 V' NOT applied
    assert decode_numeric(R["language"], 1) == 1  # Dezimal 2 / Offset 2 NOT applied


def test_enum_known_and_undocumented() -> None:
    assert decode_option(R["operating_mode"], 3) == "heat_pump_and_electric"
    assert decode_option(R["operating_mode"], 9) is None
    with pytest.raises(ValueError):
        decode_option(R["t_soll"], 1)


@pytest.mark.parametrize(("raw", "state"), [(0, False), (1, True), (2, None), (0xFFFF, None)])
def test_binary(raw: int, state: bool | None) -> None:
    assert decode_binary(raw) is state


def test_documented_range() -> None:
    assert in_documented_range(R["t_soll"], 5)
    assert in_documented_range(R["t_soll"], 62)
    assert not in_documented_range(R["t_soll"], 63)
    assert not in_documented_range(R["t_soll"], 4)
    assert in_documented_range(R["t2_tank"], 9999)  # no min/max printed


def test_resolve_parameter_datapoint_and_pilot() -> None:
    kw = {"datapoint_space": "input", "address_offset": 0}
    assert resolve_address(R["start_hp_hour"], **kw) == ("holding", 8)
    assert resolve_address(R["t2_tank"], **kw) == ("input", 8)
    assert resolve_address(PILOT, **kw) == ("holding", 8)


def test_resolve_alternatives_are_explicit_options() -> None:
    assert resolve_address(R["t2_tank"], datapoint_space="holding", address_offset=0) == ("holding", 8)
    assert resolve_address(R["t2_tank"], datapoint_space="input", address_offset=-1) == ("input", 7)
    assert resolve_address(R["t_soll"], datapoint_space="holding", address_offset=1) == ("holding", 5)
    # parameters never move to the input space
    assert resolve_address(R["t_soll"], datapoint_space="holding", address_offset=0)[0] == "holding"
    # pilot ignores both options
    assert resolve_address(PILOT, datapoint_space="input", address_offset=1) == ("holding", 8)


def test_resolve_negative_address_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_address(R["di1_pressure_switch"], datapoint_space="input", address_offset=-1)


def test_models() -> None:
    assert registers_for_model(MODEL_NUOS_400_B)[0] is PILOT
    assert len(registers_for_model(MODEL_NUOS_II)) == len(registers_for_model(MODEL_NUOS_400_B))
    for bad in ("nuos_extra", "", "NUOS 400"):
        with pytest.raises(UnsupportedModelError):
            registers_for_model(bad)
