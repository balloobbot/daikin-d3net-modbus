"""Set up a Daikin adapter over TCP or a serial port."""

import probatio
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow
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
    CONF_ADAPTER_MODEL,
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    DOMAIN,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from .device import Board, D3netGateway

MODEL_SELECTOR = SelectSelector(SelectSelectorConfig(options=list(Board)))
PARITY_SELECTOR = SelectSelector(
    SelectSelectorConfig(options=["e", "o", "n", "n1"], translation_key="parity")
)

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=15)),
    probatio.Coerce(int),
)
COMMON_FIELDS = {
    probatio.Required(CONF_ADAPTER_MODEL): MODEL_SELECTOR,
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
        probatio.Required(CONF_PARITY, default="e"): PARITY_SELECTOR,
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

    async def _async_validate(self, data):
        if (
            data[CONF_ADAPTER_MODEL] == Board.DTA116A51
            and data[CONF_TRANSPORT] == TRANSPORT_SERIAL
            and data[CONF_PARITY] == "n1"
        ):
            return {CONF_PARITY: "invalid_parity"}
        try:
            async with async_get_temporary_unit(
                self.hass, connection_params(data), data[CONF_UNIT_ID]
            ) as unit:
                report = await D3netGateway(
                    unit, Board(data[CONF_ADAPTER_MODEL])
                ).async_update()
                if not report.updated:
                    raise ModbusError("No indoor unit is communicating")
        except ModbusError:
            return {"base": "cannot_connect"}
        except HomeAssistantError:
            return {"base": "connection_conflict"}
        return {}

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        fields = {probatio.Required(CONF_ADAPTER_MODEL): MODEL_SELECTOR}
        if entry.data[CONF_TRANSPORT] == TRANSPORT_SERIAL:
            fields[probatio.Required(CONF_PARITY)] = PARITY_SELECTOR
        errors = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            unloaded = False
            if entry.state is ConfigEntryState.LOADED and connection_params(
                data
            ) != connection_params(entry.data):
                unloaded = await self.hass.config_entries.async_unload(entry.entry_id)
                if not unloaded:
                    errors = {"base": "connection_conflict"}
            try:
                if not errors:
                    errors = await self._async_validate(data)
                if not errors:
                    result = self.async_update_reload_and_abort(
                        entry, data_updates=user_input
                    )
                    unloaded = False
                    return result
            finally:
                if unloaded:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(fields), user_input or entry.data
            ),
            errors=errors,
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
            errors = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(title=data[CONF_NAME], data=data)
        suggested = user_input
        if user_input is not None and transport == TRANSPORT_SERIAL:
            suggested = {**user_input, CONF_BAUDRATE: str(user_input[CONF_BAUDRATE])}
        return self.async_show_form(
            step_id=transport,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )
