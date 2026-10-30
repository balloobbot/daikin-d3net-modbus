"""Validate a DTA116A51 with a temporary shared connection."""

import voluptuous as vol
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import ModbusError

from .connection import connection_params, endpoint_id
from .const import CONF_TRANSPORT, CONF_UNIT_ID, DOMAIN, TRANSPORT_RTU, TRANSPORT_TCP
from .device import D3netGateway

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): vol.All(str, vol.Strip, vol.Length(min=1)),
        vol.Required(CONF_PORT, default=502): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_UNIT_ID, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=15)
        ),
        vol.Required(CONF_TRANSPORT, default=TRANSPORT_TCP): vol.In(
            {
                TRANSPORT_TCP: "Modbus TCP gateway",
                TRANSPORT_RTU: "RTU over TCP bridge",
            }
        ),
        vol.Optional(CONF_NAME, default="Daikin DIII-Net"): vol.All(
            str, vol.Strip, vol.Length(min=1)
        ),
    }
)


class D3netConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(endpoint_id(user_input))
            self._abort_if_unique_id_configured()
            try:
                async with async_get_temporary_unit(
                    self.hass, connection_params(user_input), user_input[CONF_UNIT_ID]
                ) as unit:
                    report = await D3netGateway(unit).async_update()
                    if not report.updated:
                        raise ModbusError("No indoor unit is communicating")
            except ModbusError:
                errors["base"] = "cannot_connect"
            except HomeAssistantError:
                errors["base"] = "connection_conflict"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)
