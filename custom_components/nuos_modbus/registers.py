"""Runtime register table.

Mirrors docs/registers/modbus.yaml (the cited source of truth); the test
``tests/test_catalogue.py`` fails if the two drift apart. Every entry except the
pilot diagnostic is a *candidate*: documented for NUOS II, not validated on the
installed NUOS 400 B (VTC200), so its entity is disabled by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .const import (
    MODEL_NUOS_400_B,
    MODEL_NUOS_II,
    SPACE_HOLDING,
    SPACE_INPUT,
    SUPPORTED_MODELS,
    VALIDATION_NOT_VALIDATED,
    VALIDATION_READ_OK,
)

Platform = Literal["sensor", "binary_sensor"]
Group = Literal["parameter", "rtc", "communication", "datapoint", "pilot"]


class UnsupportedModelError(ValueError):
    """Raised for a model this integration has no register profile for."""


@dataclass(frozen=True, kw_only=True)
class Register:
    """One documented register and how the integration exposes it."""

    key: str
    name: str
    group: Group
    address: int
    """Manual 'Modbus Adresse' (or fixed PDU address for the pilot)."""
    space: Literal["holding", "input"]
    """Candidate register space. Datapoints follow the configured option."""
    platform: Platform = "sensor"
    decimals: int = 0
    signed: bool = False
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    options: dict[int, str] | None = None
    """Enumeration raw value -> state option (sensor ENUM)."""
    minimum: int | None = None
    maximum: int | None = None
    raw_only: bool = False
    """Expose the raw register value only (scaling/meaning ambiguous in source)."""
    display_values: dict[int, str] | None = None
    """Raw value -> text shown on the installed unit's own display (VTC200, VT15).

    Only codes observed on the physical display are listed (owner photos,
    2026-10-22, DAI-IN-639). Any other raw value has no display text. The entity
    state stays the raw value; the text is an extra attribute.
    """
    diagnostic: bool = True
    enabled_default: bool = False
    writable_documented: bool = False
    """Source documents FC06 write for this register (NOT used by default)."""
    write_forbidden: bool = False
    """Never writable through this integration, whatever profile is active."""
    fixed_address: bool = False
    """Address is a PDU address used as-is (no offset, no space option)."""
    validation: str = VALIDATION_NOT_VALIDATED
    source_page: int | None = 35
    models: tuple[str, ...] = field(default=(MODEL_NUOS_II, MODEL_NUOS_400_B))


def _p(key: str, name: str, address: int, **kw: object) -> Register:
    """Shorthand for a §10.4 parameter (holding, FC03 read, FC06 documented)."""
    return Register(
        key=key,
        name=name,
        group=kw.pop("group", "parameter"),  # type: ignore[arg-type]
        address=address,
        space=SPACE_HOLDING,
        writable_documented=kw.pop("writable_documented", True),  # type: ignore[arg-type]
        source_page=kw.pop("source_page", 33 if address <= 23 else 34),  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


def _d(key: str, name: str, address: int, **kw: object) -> Register:
    """Shorthand for a §10.5 ES1076 datapoint (read only)."""
    return Register(
        key=key,
        name=name,
        group="datapoint",
        address=address,
        space=SPACE_INPUT,
        source_page=35,
        **kw,  # type: ignore[arg-type]
    )


C, H, MIN, D, PCT = "°C", "h", "min", "d", "%"
TEMP = {"unit": C, "device_class": "temperature"}
ONOFF = {0: "off", 1: "on"}

PILOT = Register(
    key="raw_holding_8",
    name="Holding register 8 raw (unverified)",
    group="pilot",
    address=8,
    space=SPACE_HOLDING,
    raw_only=True,
    enabled_default=True,
    fixed_address=True,
    validation=VALIDATION_READ_OK,
    source_page=None,
)

REGISTERS: tuple[Register, ...] = (
    PILOT,
    # §10.4 parameters, page 33
    _p("t_soll", "Hot water setpoint (candidate)", 4, minimum=5, maximum=62, **TEMP),
    _p("t_min", "Backup heater threshold (candidate)", 5, minimum=5, maximum=62, **TEMP),
    _p("t2_min", "Frost threshold T2 min (candidate)", 6, minimum=5, maximum=62, **TEMP),
    _p("timer", "Timer enabled (candidate)", 7, platform="binary_sensor", minimum=0, maximum=1),
    _p("start_hp_hour", "Timer start hour (candidate)", 8, unit=H, minimum=0, maximum=23),
    _p("start_hp_min", "Timer start minute (candidate)", 9, unit=MIN, minimum=0, maximum=59),
    _p("stop_hp_hour", "Timer stop hour (candidate)", 10, unit=H, minimum=0, maximum=23),
    _p("stop_hp_min", "Timer stop minute (candidate)", 11, unit=MIN, minimum=0, maximum=59),
    _p(
        "operating_mode",
        "Operating mode (candidate)",
        12,
        device_class="enum",
        diagnostic=False,
        minimum=0,
        maximum=5,
        options={
            0: "off",
            1: "heat_pump_only",
            2: "electric_only",
            3: "heat_pump_and_electric",
            4: "boiler",
            5: "heat_pump_and_boiler",
        },
    ),
    _p(
        "t_legio",
        "Legionella protection (candidate)",
        13,
        device_class="enum",
        minimum=0,
        maximum=2,
        options={0: "off", 1: "60_c", 2: "65_c"},
    ),
    _p("t_min_rl", "T min RL (candidate)", 14, minimum=5, maximum=20, **TEMP),
    _p(
        "wp_ls",
        "Fan speed in operation raw (candidate)",
        15,
        raw_only=True,
        display_values={1: "High"},
        minimum=0,
        maximum=3,
    ),
    _p("kwl", "Standby fan mode raw (candidate)", 16, raw_only=True, minimum=0, maximum=2),
    _p(
        "pv_mode",
        "PV mode (candidate)",
        17,
        device_class="enum",
        minimum=0,
        maximum=3,
        options={0: "off", 1: "heat_pump_only", 2: "electric_only", 3: "heat_pump_and_electric"},
    ),
    _p("t_pv_wp", "PV setpoint heat pump (candidate)", 18, minimum=5, maximum=62, **TEMP),
    _p("t_pv_el", "PV setpoint electric (candidate)", 19, minimum=5, maximum=62, **TEMP),
    _p(
        "holiday",
        "Holiday mode (candidate)",
        20,
        device_class="enum",
        minimum=0,
        maximum=5,
        options={0: "off", 1: "1_week", 2: "2_weeks", 3: "3_weeks", 4: "3_days", 5: "manual"},
    ),
    _p("absence_days", "Absence days (candidate)", 21, unit=D, minimum=1, maximum=99),
    _p("boost", "Boost (candidate)", 22, platform="binary_sensor", diagnostic=False, minimum=0, maximum=1),
    _p(
        "fan_pause",
        "Fan pause raw (candidate)",
        23,
        raw_only=True,
        display_values={2: "30m/30s"},
        minimum=0,
        maximum=6,
    ),
    # §10.4 parameters, page 34
    _p(
        "language",
        "Display language raw (candidate)",
        25,
        raw_only=True,
        display_values={0: "English"},
        minimum=0,
        maximum=10,
    ),
    _p(
        "defrost_type",
        "Defrost type raw (candidate)",
        26,
        raw_only=True,
        display_values={1: "Gas"},
        write_forbidden=True,
        minimum=0,
        maximum=2,
    ),
    _p("anode", "Signal anode monitoring (candidate)", 27, platform="binary_sensor", minimum=0, maximum=1),
    _p("t_max", "Maximum hot water temperature (candidate)", 28, minimum=5, maximum=62, **TEMP),
    _p(
        "fan_type",
        "Fan type (candidate)",
        29,
        device_class="enum",
        write_forbidden=True,
        minimum=0,
        maximum=1,
        options={0: "ac", 1: "ec"},
    ),
    _p("ec_ls1", "EC fan level 1 (candidate)", 30, unit=PCT, minimum=0, maximum=100),
    _p("ec_ls2", "EC fan level 2 (candidate)", 31, unit=PCT, minimum=0, maximum=100),
    _p("ec_ls3", "EC fan level 3 (candidate)", 32, unit=PCT, minimum=0, maximum=100),
    _p("legionella_auto_days", "Legionella auto interval (candidate)", 33, unit=D, minimum=3, maximum=14),
    # §10.4 RTC, page 34 — encoding undocumented, raw only, never written
    *(
        _p(key, name, address, group="rtc", raw_only=True, writable_documented=False, write_forbidden=True)
        for key, name, address in (
            ("rtc_second", "RTC second raw (candidate)", 103),
            ("rtc_minute", "RTC minute raw (candidate)", 104),
            ("rtc_hour", "RTC hour raw (candidate)", 105),
            ("rtc_weekday", "RTC day raw (candidate)", 106),
            ("rtc_date", "RTC date raw (candidate)", 107),
            ("rtc_month", "RTC month raw (candidate)", 108),
            ("rtc_year", "RTC year raw (candidate)", 109),
        )
    ),
    # §10.4 communication, page 34 — never written (would cut the gateway link)
    _p("modbus_address", "Modbus address (candidate)", 114, group="communication", write_forbidden=True, minimum=1, maximum=247),
    _p(
        "modbus_baud",
        "Modbus baud rate (candidate)",
        115,
        group="communication",
        device_class="enum",
        write_forbidden=True,
        minimum=1,
        maximum=2,
        options={1: "19200", 2: "9600"},
    ),
    _p(
        "modbus_parity",
        "Modbus parity (candidate)",
        116,
        group="communication",
        device_class="enum",
        write_forbidden=True,
        minimum=0,
        maximum=2,
        options={0: "none", 1: "odd", 2: "even"},
    ),
    _p(
        "modbus_allow_write",
        "Modbus write allowed (candidate)",
        117,
        group="communication",
        platform="binary_sensor",
        write_forbidden=True,
        minimum=0,
        maximum=1,
    ),
    # §10.5 ES1076 datapoints, page 35 — read only
    _d("di1_pressure_switch", "Pressure switch input (candidate)", 0, platform="binary_sensor"),
    _d("di2_pv_input", "PV contact input (candidate)", 1, platform="binary_sensor", diagnostic=False),
    _d("t1_evaporator", "Evaporator temperature T1 (candidate)", 7, decimals=1, signed=True, state_class="measurement", diagnostic=False, **TEMP),
    _d("t2_tank", "Tank temperature T2 (candidate)", 8, decimals=1, signed=True, state_class="measurement", diagnostic=False, **TEMP),
    _d("relay1_compressor", "Compressor running (candidate)", 9, platform="binary_sensor", device_class="running", diagnostic=False),
    _d("relay2_electric_heater", "Electric heater running (candidate)", 10, platform="binary_sensor", device_class="running", diagnostic=False),
    _d("relay3_boiler", "Boiler relay (candidate)", 11, platform="binary_sensor", device_class="running"),
    _d("relay4_solenoid_valve", "Solenoid valve relay (candidate)", 12, platform="binary_sensor"),
    _d("relay6_condenser", "Condenser relay (candidate)", 13, platform="binary_sensor"),
    _d("relay7_fan", "Fan running (candidate)", 14, platform="binary_sensor", device_class="running", diagnostic=False),
    _d("da0_output", "0-10 V output raw (candidate)", 15, raw_only=True),
    _d("status_bits", "Status word raw (candidate)", 16, raw_only=True, display_values={2: "Standby"}),
    _d("rest_days", "Remaining absence days (candidate)", 17, unit=D),
    _d("unit_alarm_bits", "Alarm word raw (candidate)", 18, raw_only=True),
    _d("t3", "Temperature T3 (candidate)", 19, decimals=1, signed=True, state_class="measurement", diagnostic=False, **TEMP),
    _d("fw_version", "Firmware version raw (candidate)", 119, raw_only=True),
)

REGISTERS_BY_KEY: dict[str, Register] = {r.key: r for r in REGISTERS}


def registers_for_model(model: str) -> tuple[Register, ...]:
    """Return the register profile for a model.

    Raises UnsupportedModelError for a model without a profile, rather than
    guessing a map for an unknown controller.
    """
    if model not in SUPPORTED_MODELS:
        raise UnsupportedModelError(f"No NUOS register profile for model {model!r}")
    return tuple(r for r in REGISTERS if model in r.models)


def resolve_address(
    register: Register, *, datapoint_space: str, address_offset: int
) -> tuple[str, int]:
    """Return the (space, PDU address) actually requested for a register.

    The pilot diagnostic is fixed. Catalogue addresses take the configured
    offset; datapoints take the configured register space. Raises ValueError
    if the offset would produce a negative address.
    """
    if register.fixed_address:
        return register.space, register.address
    space = datapoint_space if register.group == "datapoint" else register.space
    address = register.address + address_offset
    if address < 0:
        raise ValueError(f"{register.key}: address {register.address}{address_offset:+d} < 0")
    return space, address
