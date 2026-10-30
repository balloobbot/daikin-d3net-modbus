"""Set up a Daikin adapter over TCP or a serial port."""

import probatio
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SerialPortSelector,
    TextSelector,
)
from modbus_connection import ModbusError

from .connection import connection_params, endpoint_id
from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DOMAIN,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from .device import D3netGateway

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=15)),
    probatio.Coerce(int),
)
COMMON_FIELDS = {
    probatio.Required(CONF_UNIT_ID, default=1): UNIT_ID_SELECTOR,
    probatio.Optional(CONF_NAME, default="Daikin DIII-Net"): TextSelector(),
}
TCP_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=502): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        **COMMON_FIELDS,
    }
)
SERIAL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default="9600"): probatio.All(
            SelectSelector(SelectSelectorConfig(options=["9600", "19200"])),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_PARITY, default="e"): SelectSelector(
            SelectSelectorConfig(
                options=["e", "o", "n", "n1"], translation_key="parity"
            )
        ),
        **COMMON_FIELDS,
    }
)


class D3netConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(
            step_id="user", menu_options=[TRANSPORT_TCP, TRANSPORT_SERIAL]
        )

    async def async_step_tcp(self, user_input=None):
        return await self._async_step_connection(TRANSPORT_TCP, TCP_SCHEMA, user_input)

    async def async_step_serial(self, user_input=None):
        return await self._async_step_connection(
            TRANSPORT_SERIAL, SERIAL_SCHEMA, user_input
        )

    async def _async_step_connection(self, transport, schema, user_input):
        errors = {}
        if user_input is not None:
            data = {CONF_TRANSPORT: transport, **user_input}
            if transport == TRANSPORT_TCP:
                data[CONF_HOST] = data[CONF_HOST].strip()
                if not data[CONF_HOST]:
                    return self.async_show_form(
                        step_id=transport,
                        data_schema=self.add_suggested_values_to_schema(
                            schema, user_input
                        ),
                        errors={CONF_HOST: "invalid_host"},
                    )
            await self.async_set_unique_id(endpoint_id(data))
            self._abort_if_unique_id_configured()
            try:
                async with async_get_temporary_unit(
                    self.hass, connection_params(data), data[CONF_UNIT_ID]
                ) as unit:
                    report = await D3netGateway(unit).async_update()
                    if not report.updated:
                        raise ModbusError("No indoor unit is communicating")
            except ModbusError:
                errors["base"] = "cannot_connect"
            except HomeAssistantError:
                errors["base"] = "connection_conflict"
            else:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        suggested = user_input
        if user_input is not None and transport == TRANSPORT_SERIAL:
            suggested = {**user_input, CONF_BAUDRATE: str(user_input[CONF_BAUDRATE])}
        return self.async_show_form(
            step_id=transport,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )
