"""Config and options flow.

The connection test is ONE read of holding register 8 (the register the
proven YAML pilot already polls) through ``async_get_temporary_unit``. No
writes, scans or other requests are made.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from modbus_connection import ModbusError, ModbusTcpParams
import voluptuous as vol

from .const import (
    ADDRESS_OFFSETS,
    CONF_ADDRESS_OFFSET,
    CONF_DATAPOINT_SPACE,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DATAPOINT_SPACES,
    DEFAULT_ADDRESS_OFFSET,
    DEFAULT_DATAPOINT_SPACE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MODEL_NAMES,
    MODEL_NUOS_400_B,
    REQUEST_TIMEOUT,
    SUPPORTED_MODELS,
)

_LOGGER = logging.getLogger(__name__)
PROBE_ADDRESS = 8  # holding register already read by the YAML pilot

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=247)
        ),
        vol.Required(CONF_MODEL, default=MODEL_NUOS_400_B): vol.In(SUPPORTED_MODELS),
    }
)


async def async_probe(hass: HomeAssistant, host: str, port: int, unit_id: int) -> None:
    """Read one holding register; raise on any failure."""
    async with async_get_temporary_unit(
        hass, ModbusTcpParams(host=host, port=port), unit_id
    ) as unit:
        unit.require_timeout(REQUEST_TIMEOUT)
        await unit.read_holding_registers(PROBE_ADDRESS, 1)


def _offset_option(offset: int) -> str:
    """Selector option key for a stored integer offset."""
    return next(k for k, v in ADDRESS_OFFSETS.items() if v == offset)


class NuosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a NUOS unit."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the gateway endpoint, unit id and model."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            unit_id = user_input[CONF_UNIT_ID]
            await self.async_set_unique_id(f"{host.lower()}:{port}:{unit_id}")
            self._abort_if_unique_id_configured()
            try:
                await async_probe(self.hass, host, port, unit_id)
            except HomeAssistantError:
                errors["base"] = "endpoint_in_use"
            except (ModbusError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error probing NUOS")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{MODEL_NAMES[user_input[CONF_MODEL]]} @ {host}:{port}/{unit_id}",
                    data={**user_input, CONF_HOST: host},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> NuosOptionsFlow:
        """Options: poll interval and the unresolved addressing choices."""
        return NuosOptionsFlow()


class NuosOptionsFlow(OptionsFlowWithReload):
    """Poll interval, datapoint register space and address offset."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            user_input[CONF_ADDRESS_OFFSET] = ADDRESS_OFFSETS[user_input[CONF_ADDRESS_OFFSET]]
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
                vol.Required(
                    CONF_DATAPOINT_SPACE,
                    default=options.get(CONF_DATAPOINT_SPACE, DEFAULT_DATAPOINT_SPACE),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(DATAPOINT_SPACES),
                        translation_key=CONF_DATAPOINT_SPACE,
                    )
                ),
                vol.Required(
                    CONF_ADDRESS_OFFSET,
                    default=_offset_option(options.get(CONF_ADDRESS_OFFSET, DEFAULT_ADDRESS_OFFSET)),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(ADDRESS_OFFSETS),
                        translation_key=CONF_ADDRESS_OFFSET,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
