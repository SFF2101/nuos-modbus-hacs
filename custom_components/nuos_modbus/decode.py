"""Pure decoding and read planning (no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .registers import Register


@dataclass(frozen=True)
class ReadBlock:
    """One read request: ``count`` registers from ``address`` in ``space``."""

    space: str
    address: int
    count: int

    @property
    def addresses(self) -> range:
        """The PDU addresses this block covers."""
        return range(self.address, self.address + self.count)


def plan_reads(
    targets: Iterable[tuple[str, int]], max_block: int
) -> list[ReadBlock]:
    """Coalesce (space, address) targets into contiguous read blocks.

    Only addresses that were asked for are read: a gap always splits a block,
    so no undocumented register is ever requested to bridge one.
    """
    if max_block < 1:
        raise ValueError("max_block must be >= 1")
    blocks: list[ReadBlock] = []
    by_space: dict[str, list[int]] = {}
    for space, address in set(targets):
        by_space.setdefault(space, []).append(address)
    for space in sorted(by_space):
        start = prev = None
        for address in sorted(by_space[space]):
            if start is None:
                start = prev = address
                continue
            if address == prev + 1 and address - start < max_block:
                prev = address
                continue
            blocks.append(ReadBlock(space, start, prev - start + 1))
            start = prev = address
        if start is not None:
            blocks.append(ReadBlock(space, start, prev - start + 1))
    return blocks


def to_signed16(raw: int) -> int:
    """Interpret a 16-bit register as two's complement."""
    if not 0 <= raw <= 0xFFFF:
        raise ValueError(f"register value {raw} outside 0..65535")
    return raw - 0x10000 if raw & 0x8000 else raw


def decode_numeric(register: Register, raw: int) -> int | float:
    """Return the scaled value of a numeric register.

    Raw-only registers are returned unscaled. No sentinel values are
    documented by the manufacturer, so none are applied.
    """
    if register.raw_only:
        return raw
    value = to_signed16(raw) if register.signed else raw
    if register.decimals:
        return round(value / (10**register.decimals), register.decimals)
    return value


def decode_option(register: Register, raw: int) -> str | None:
    """Return the enumeration option for ``raw`` or None if undocumented."""
    if register.options is None:
        raise ValueError(f"{register.key} is not an enumeration")
    return register.options.get(raw)


def decode_binary(raw: int) -> bool | None:
    """Return the on/off state of a documented 0/1 register, else None."""
    if raw == 0:
        return False
    if raw == 1:
        return True
    return None


def in_documented_range(register: Register, raw: int) -> bool:
    """Whether ``raw`` lies within the printed min/max (True if none printed)."""
    if register.minimum is not None and raw < register.minimum:
        return False
    if register.maximum is not None and raw > register.maximum:
        return False
    return True
