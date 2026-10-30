"""Exercise real Home Assistant flows, entities and coordinator behavior."""

from unittest.mock import patch

import probatio
import pytest
from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import SerialPortSelector
from homeassistant.loader import async_get_integration
from modbus_connection import ModbusError, ModbusSerialParams
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.daikin_d3net.connection import connection_params, endpoint_id
from custom_components.daikin_d3net.const import DOMAIN

from .conftest import DATA, seed

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "shared_unit")


@pytest.fixture(autouse=True)
def no_requirements():
    with patch(
        "homeassistant.requirements.async_get_integration_with_requirements",
        side_effect=async_get_integration,
    ):
        yield


async def setup_entry(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entities_and_unload(hass, mock_entry, shared_unit):
    await setup_entry(hass, mock_entry)
    assert mock_entry.state is ConfigEntryState.LOADED
    shared_unit.assert_called_once()
    assert shared_unit.call_args.args[-1] == 1
    climates = hass.states.async_all("climate")
    assert len(climates) == 1
    climate = climates[0]
    assert climate.state == "cool"
    assert climate.attributes["current_temperature"] == 23.4
    assert climate.attributes["temperature"] == 22.5
    assert climate.attributes["fan_modes"] == ["low", "medium", "high"]
    assert climate.attributes["min_temp"] == 16
    assert climate.attributes["max_temp"] == 32
    assert len(hass.states.async_all("binary_sensor")) == 5
    assert any(state.state == "U4" for state in hass.states.async_all("sensor"))
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_unavailable_and_recovery(hass, mock_entry, modbus_unit):
    seed(modbus_unit, (0, 1))
    await setup_entry(hass, mock_entry)
    coordinator = mock_entry.runtime_data
    modbus_unit.input[5] = 1
    await coordinator.async_refresh()
    states = hass.states.async_all("climate")
    assert sum(state.state == STATE_UNAVAILABLE for state in states) == 1
    assert sum(state.state == "cool" for state in states) == 1
    modbus_unit.input[5] = 0
    await coordinator.async_refresh()
    assert all(state.state == "cool" for state in hass.states.async_all("climate"))
    modbus_unit.fail_requests(ModbusError("offline"))
    await coordinator.async_refresh()
    assert all(
        state.state == STATE_UNAVAILABLE for state in hass.states.async_all("climate")
    )


async def test_first_read_failure_retries(hass, mock_entry, modbus_unit):
    modbus_unit.fail_requests(ModbusError("offline"))
    mock_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


SERIAL_DATA = {
    "transport": "serial",
    "device": "/dev/serial/by-id/usb-rs485",
    "baudrate": 9600,
    "parity": "E",
    "unit_id": 1,
    "name": "Daikin",
}


async def start_connection_flow(hass, transport):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["tcp", "serial"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": transport}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == transport
    assert probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    if transport == "serial":
        assert isinstance(result["data_schema"].schema[CONF_DEVICE], SerialPortSelector)
    return result


def form_data(data):
    fields = {key: value for key, value in data.items() if key != "transport"}
    if "baudrate" in fields:
        fields["baudrate"] = str(fields["baudrate"])
    return fields


@pytest.mark.parametrize("data", [DATA, SERIAL_DATA])
async def test_flow_probes_before_creating_entry(hass, data):
    result = await start_connection_flow(hass, data["transport"])
    with patch("custom_components.daikin_d3net.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], form_data(data)
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert result["result"].unique_id == endpoint_id(data)


@pytest.mark.parametrize("data", [DATA, SERIAL_DATA])
async def test_flow_rejects_unreachable_device(hass, modbus_unit, data):
    modbus_unit.fail_requests(ModbusError("offline"))
    result = await start_connection_flow(hass, data["transport"])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data(data)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == data["transport"]
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize("data", [DATA, SERIAL_DATA])
async def test_flow_connection_conflict(hass, data):
    result = await start_connection_flow(hass, data["transport"])
    with patch(
        "custom_components.daikin_d3net.config_flow.async_get_temporary_unit",
        side_effect=HomeAssistantError("different settings"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], form_data(data)
        )
    assert result["errors"] == {"base": "connection_conflict"}


@pytest.mark.parametrize("data", [DATA, SERIAL_DATA])
async def test_duplicate_endpoint(hass, data):
    MockConfigEntry(domain=DOMAIN, data=data, unique_id=endpoint_id(data)).add_to_hass(
        hass
    )
    fields = form_data(data)
    if data["transport"] == "tcp":
        fields["host"] = " GATEWAY.local "
    result = await start_connection_flow(hass, data["transport"])
    result = await hass.config_entries.flow.async_configure(result["flow_id"], fields)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "device", ["/dev/serial/by-id/usb-rs485", "socket://gateway.local:6638"]
)
@pytest.mark.parametrize(("parity", "stopbits"), [("E", 1), ("O", 1), ("N", 2)])
async def test_serial_setup_parameters(hass, shared_unit, device, parity, stopbits):
    data = {**SERIAL_DATA, "device": device, "baudrate": 19200, "parity": parity}
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=endpoint_id(data))
    await setup_entry(hass, entry)
    assert shared_unit.call_args.args[2] == ModbusSerialParams(
        device=device, baudrate=19200, parity=parity, stopbits=stopbits
    )


async def test_serial_proxy_duplicate_of_legacy_entry(hass):
    legacy = {**DATA, "transport": "rtu_over_tcp"}
    MockConfigEntry(
        domain=DOMAIN, data=legacy, unique_id=endpoint_id(legacy)
    ).add_to_hass(hass)
    result = await start_connection_flow(hass, "serial")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        form_data({**SERIAL_DATA, "device": "socket://gateway.local:502"}),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_service_failure_is_exposed(hass, mock_entry, modbus_unit):
    await setup_entry(hass, mock_entry)
    modbus_unit.fail_write(2000, ModbusError("rejected"))
    entity_id = hass.states.async_all("climate")[0].entity_id
    with pytest.raises(HomeAssistantError, match="Daikin command failed"):
        await hass.services.async_call(
            "climate", "turn_off", {"entity_id": entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == "cool"


@pytest.mark.parametrize(
    ("transport", "host", "device"),
    [
        ("rtu_over_tcp", "192.0.2.1", "socket://192.0.2.1:502"),
        ("rtu_over_tcp", "2001:db8::1", "socket://[2001:db8::1]:502"),
    ],
)
def test_rtu_parameters(transport, host, device):
    params = connection_params({**DATA, "transport": transport, "host": host})
    assert params.device == device
    assert params.framer == "rtu"


async def test_shared_connection_release(hass, mock_entry):
    connection = MockModbusConnection()
    seed(connection.for_unit(1))
    with (
        patch("custom_components.daikin_d3net.async_get_unit", async_get_unit),
        patch(
            "homeassistant.components.modbus.connection.ModbusConnection",
            return_value=connection,
        ),
    ):
        await setup_entry(hass, mock_entry)
        assert connection.connected
        await mock_entry.runtime_data.async_refresh()
        assert connection.connected  # Polling does not close the shared socket.
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert not connection.connected


async def test_setup_failure_releases_connection(hass, mock_entry):
    connection = MockModbusConnection()
    unit = seed(connection.for_unit(1))
    unit.input[0] = 0
    with (
        patch("custom_components.daikin_d3net.async_get_unit", async_get_unit),
        patch(
            "homeassistant.components.modbus.connection.ModbusConnection",
            return_value=connection,
        ),
    ):
        mock_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert not connection.connected


async def test_all_platform_controls(hass, mock_entry, modbus_unit):
    await setup_entry(hass, mock_entry)
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, mock_entry.entry_id):
        if entity.disabled_by:
            registry.async_update_entity(entity.entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()
    writes = []

    def echo_write(event):
        writes.append(event)
        words = list(modbus_unit.input[2000])
        offset = event.address - 2000
        if offset == 0:
            words[0] = (words[0] & ~0x7701) | (event.values[0] & 0x7701)
        elif offset == 1:
            words[1] = (words[1] & 0xF000) | (event.values[0] & 0xF0F)
        else:
            words[2] = event.values[0]
        modbus_unit.input[2000] = words

    modbus_unit.on_write(echo_write)

    def entity_id(key):
        return next(
            entity.entity_id
            for entity in er.async_entries_for_config_entry(
                registry, mock_entry.entry_id
            )
            if entity.unique_id.endswith(":" + key)
        )

    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": entity_id("power")}, blocking=True
        )
        await mock_entry.runtime_data.async_refresh()
        assert hass.states.get(entity_id("climate")).state == "off"
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id("setpoint"), "value": 24.1},
            blocking=True,
        )
        await mock_entry.runtime_data.async_refresh()
        assert hass.states.get(entity_id("climate")).attributes["temperature"] == 24.1
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id("fan_speed"), "option": "low"},
            blocking=True,
        )
        await mock_entry.runtime_data.async_refresh()
        assert hass.states.get(entity_id("climate")).attributes["fan_mode"] == "low"
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id("direction"), "option": "on"},
            blocking=True,
        )
        await mock_entry.runtime_data.async_refresh()
        assert hass.states.get(entity_id("climate")).attributes["swing_mode"] == "on"
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id("filter_reset")}, blocking=True
        )
        assert writes[-1].values[0] & 0xF0 == 0


async def test_tcp_empty_host(hass):
    result = await start_connection_flow(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**form_data(DATA), "host": "  "}
    )
    assert result["errors"] == {"host": "invalid_host"}


async def test_serial_retry_keeps_baud_rate(hass, modbus_unit):
    modbus_unit.fail_requests(ModbusError("offline"))
    result = await start_connection_flow(hass, "serial")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], form_data({**SERIAL_DATA, "baudrate": 19200})
    )
    assert result["errors"] == {"base": "cannot_connect"}
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    baud = next(field for field in fields if field["name"] == "baudrate")
    assert baud["description"]["suggested_value"] == "19200"
