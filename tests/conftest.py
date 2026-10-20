"""Fixtures.

Home Assistant runs for real (pytest-homeassistant-custom-component pinned to
the HA release under test). Only the TRANSPORT is replaced: HA's own
``homeassistant.components.modbus.connection.ModbusConnection`` is patched to
modbus-connection's in-memory ``MockModbusConnection``, so the real
``async_get_unit`` / ``async_get_temporary_unit`` ownership and release code is
exercised. No physical device or network is involved.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nuos_modbus.const import (
    CONF_MODEL,
    CONF_UNIT_ID,
    DOMAIN,
    MODEL_NUOS_400_B,
)

HOST = "192.0.2.10"  # TEST-NET-1, never a real device
PORT = 1502
UNIT = 1


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components/nuos_modbus."""


class ReopenableMockConnection(MockModbusConnection):
    """In-memory connection that records HA closing it.

    In production HA builds a NEW connection after the last holder released
    the old one; here the same object (with its unit stores) is handed out
    again, so close() records the call and leaves it reopenable.
    """

    def __init__(self) -> None:
        super().__init__()
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        await self.disconnect()


@pytest.fixture
def mock_connection() -> Generator[ReopenableMockConnection]:
    """Every HA Modbus shared connection is this in-memory one."""
    connection = ReopenableMockConnection()
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        side_effect=lambda params: connection,
    ):
        yield connection


@pytest.fixture
def nuos_unit(mock_connection: MockModbusConnection) -> MockModbusUnit:
    """Unit 1 with the value observed on site at holding 8, and some datapoints."""
    unit = mock_connection.for_unit(UNIT)
    unit.holding.update({4: 50, 8: 12, 12: 3})
    unit.input.update({7: 0xFFEC, 8: 452, 9: 1, 19: 213})
    return unit


@pytest.fixture
def writes(nuos_unit: MockModbusUnit) -> list[WriteEvent]:
    """Every write attempted on unit 1 (must stay empty)."""
    events: list[WriteEvent] = []
    nuos_unit.on_write(events.append)
    return events


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A NUOS 400 B entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NUOS",
        unique_id=f"{HOST}:{PORT}:{UNIT}",
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_UNIT_ID: UNIT, CONF_MODEL: MODEL_NUOS_400_B},
    )
    entry.add_to_hass(hass)
    return entry
