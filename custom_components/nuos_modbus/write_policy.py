"""Write guard — INERT architecture for a future, separately approved profile.

Nothing in this integration calls :func:`async_guarded_write`. There are no
number/switch/select/button entities and no services. The module exists so
that a later, validated tariff-optimisation profile has exactly one audited
path to the device, and so tests can prove that the default denies every write.

A write is only ever possible when ALL of the following hold:

* the active :class:`WriteProfile` is marked ``validated`` (no such profile
  ships with this package),
* the register key is in that profile's allow-list,
* the source documents the register as writable (FC06) and it is not on the
  integration's forbidden list (communication, RTC, defrost type, fan type),
* the register's on-site validation state is ``validated``,
* the value lies within the printed min/max.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.exceptions import HomeAssistantError

from .const import VALIDATION_VALIDATED
from .decode import in_documented_range
from .registers import Register


class WriteDeniedError(HomeAssistantError):
    """A write was refused by the write guard."""


@dataclass(frozen=True)
class WriteProfile:
    """A named set of registers that may be written."""

    name: str
    validated: bool = False
    allowed_keys: frozenset[str] = field(default_factory=frozenset)


READ_ONLY_PROFILE = WriteProfile(name="read_only")
"""The only profile shipped. It allows nothing."""


def check_write(profile: WriteProfile, register: Register, value: int) -> None:
    """Raise WriteDeniedError unless every write condition holds."""
    if not profile.validated:
        raise WriteDeniedError(f"profile {profile.name!r} is not validated")
    if register.key not in profile.allowed_keys:
        raise WriteDeniedError(f"{register.key} not allowed by {profile.name!r}")
    if register.write_forbidden:
        raise WriteDeniedError(f"{register.key} is never writable")
    if not register.writable_documented:
        raise WriteDeniedError(f"{register.key} is not documented as writable")
    if register.validation != VALIDATION_VALIDATED:
        raise WriteDeniedError(f"{register.key} is not validated on site")
    if not in_documented_range(register, value):
        raise WriteDeniedError(f"{value} outside documented range for {register.key}")


async def async_guarded_write(
    unit: object, profile: WriteProfile, register: Register, address: int, value: int
) -> None:
    """The single write path. Unused by default; see module docstring."""
    check_write(profile, register, value)
    await unit.write_register(address, value)  # type: ignore[attr-defined]
