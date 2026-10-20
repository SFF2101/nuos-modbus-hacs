"""Config entry diagnostics."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.modbus.connection import async_get_connection_info
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import NuosConfigEntry
from .write_policy import READ_ONLY_PROFILE

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NuosConfigEntry
) -> dict[str, Any]:
    """Return read plan, counters and validation state (host redacted)."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    held = [
        {"connected": info.connected, "units": info.units}
        for info in async_get_connection_info(hass)
        if entry.entry_id in info.units
    ]
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "write_profile": {
            "name": READ_ONLY_PROFILE.name,
            "validated": READ_ONLY_PROFILE.validated,
            "allowed_keys": sorted(READ_ONLY_PROFILE.allowed_keys),
        },
        "read_plan": [
            {"space": b.space, "address": b.address, "count": b.count}
            for b in coordinator.plan
        ],
        "stats": asdict(coordinator.stats),
        "last_update_success": coordinator.last_update_success,
        "raw": {
            f"{space}:{address}": value
            for (space, address), value in sorted((coordinator.data or {}).items())
        },
        "registers": {
            r.key: {
                "address": runtime.addresses.get(r.key),
                "validation": r.validation,
                "enabled_default": r.enabled_default,
            }
            for r in runtime.registers
        },
        "shared_connection": held,
    }
