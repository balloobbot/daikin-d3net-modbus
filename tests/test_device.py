"""Protocol regression tests against the library's strict in-memory backend."""

import asyncio
from unittest.mock import patch

import pytest
from modbus_connection import ModbusError, ModbusTimeoutError

from custom_components.daikin_d3net.device import D3netGateway, Mode
from custom_components.daikin_d3net.device.models import Capabilities, IndoorStatus

from .conftest import seed


async def gateway_for(unit):
    gateway = D3netGateway(unit)
    await gateway.async_update()
    return gateway


async def test_documented_discovery_and_strides(modbus_unit):
    seed(modbus_unit, (0, 15))
    gateway = await gateway_for(modbus_unit)
    assert list(gateway.units) == [0, 15]
    assert modbus_unit.message_spacing == 0.025
    assert modbus_unit.required_timeout == 10
    assert gateway.units[15].name == "1-15"
    assert gateway.units[15].status.setpoint == 22.5
    assert all(
        event.register_type == "input" and event.count <= 32
        for event in modbus_unit.read_events
    )
    assert {(event.address, event.count) for event in modbus_unit.read_events} >= {
        (0, 2),
        (5, 1),
        (1045, 3),
        (2090, 6),
    }


async def test_status_and_error_mapping(modbus_unit):
    status = (await gateway_for(modbus_unit)).units[0].status
    assert status.power
    assert status.direction == 2
    assert status.fan_speed == 5
    assert status.mode == Mode.COOL
    assert status.operation == Mode.COOL
    assert status.master == 2
    assert status.room_temperature == 23.4
    assert status.error_code == "U4"
    assert status.malfunction and not status.warning


@pytest.mark.parametrize(
    ("raw", "expected"), [(0xFFF6, -1.0), (0xFF85, -12.3), (225, 22.5)]
)
async def test_signed_temperature(modbus_unit, raw, expected):
    modbus_unit.input[2000] = [0, 0x8202, raw, 0, raw, 0x8000]
    status = IndoorStatus(modbus_unit)
    await status.async_update()
    assert status.setpoint == expected
    assert status.room_temperature == expected


@pytest.mark.parametrize("flags", [0, 0x100, 0x8100])
async def test_invalid_sensor_is_unknown(modbus_unit, flags):
    modbus_unit.input[2000] = [0, 0x8202, 225, 0, 234, flags]
    status = IndoorStatus(modbus_unit)
    await status.async_update()
    assert status.room_temperature is None


async def test_signed_limits_and_capabilities(modbus_unit):
    modbus_unit.input[1000] = [0xBD1F, 0xF620, 0xEC1E]
    caps = Capabilities(modbus_unit)
    await caps.async_update()
    assert caps.temperature_limits(Mode.COOL) == (-10, 32)
    assert caps.temperature_limits(Mode.HEAT) == (-20, 30)
    assert caps.fan_speeds == (1, 3, 5)
    assert caps.directions == (0, 1, 2, 3, 4, 6, 7)


async def test_partial_failure_and_recovery(modbus_unit):
    seed(modbus_unit, (0, 1))
    gateway = await gateway_for(modbus_unit)
    modbus_unit.fail_read(2000, ModbusTimeoutError("timeout"), register_type="input")
    report = await gateway.async_update()
    assert report.updated == {"1-01"}
    assert set(report.failed) == {"1-00"}
    modbus_unit.fail_read(2000, None, register_type="input")
    assert (await gateway.async_update()).complete
    modbus_unit.input[5] = 2
    report = await gateway.async_update()
    assert report.updated == {"1-00"}
    assert "1-01" in report.failed


@pytest.mark.parametrize(("address", "value"), [(0, 0), (1, 0)])
async def test_unready_or_empty_adapter(modbus_unit, address, value):
    modbus_unit.input[address] = value
    with pytest.raises(ModbusError):
        await D3netGateway(modbus_unit).async_setup()


async def test_control_synchronizes_and_spaces_writes(modbus_unit):
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep") as sleep:
        await indoor.async_control(power=False)
    assert [(event.address, event.values) for event in writes] == [
        (2000, [0x5261]),
        (2000, [0x5260]),
    ]
    assert all(event.function_code == 16 for event in writes)
    sleep.assert_awaited_once()
    assert 0.50 < sleep.call_args.args[0] <= 0.51
    assert indoor.status.power  # Acknowledgement is not fabricated device status.


async def test_failed_write_does_not_claim_success(modbus_unit):
    indoor = (await gateway_for(modbus_unit)).units[0]
    modbus_unit.fail_write(2000, ModbusError("rejected"))
    with pytest.raises(ModbusError, match="rejected"):
        await indoor.async_control(power=False)
    assert indoor.status.power


async def test_noop_does_not_write(modbus_unit):
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    await indoor.async_control(power=True, temperature=22.5, fan_speed=5)
    assert writes == []


@pytest.mark.parametrize(
    "changes",
    [
        {"fan_speed": 0},
        {"direction": 5},
        {"temperature": 35},
        {"temperature": float("nan")},
    ],
)
async def test_invalid_commands_do_not_write(modbus_unit, changes):
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with pytest.raises(ValueError):
        await indoor.async_control(**changes)
    assert not writes


async def test_auto_setpoint_operation_selection(modbus_unit):
    modbus_unit.input[2000] = [0x5201, 0x8203, 225, 0, 234, 0x8000]
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await indoor.async_control(temperature=23)
    assert [(event.address, event.values) for event in writes] == [
        (2001, [0x203]),
        (2002, [225]),
        (2002, [230]),
    ]


async def test_slave_setpoint_and_restricted_modes(modbus_unit):
    modbus_unit.input[2000] = [0x5201, 0x4202, 225, 0, 234, 0x8000]
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await indoor.async_control(temperature=23)
    assert writes[0].address == 2001 and writes[0].values == [0x206]
    for mode in (Mode.HEAT, Mode.AUTO):
        with pytest.raises(ValueError):
            await indoor.async_control(mode=mode)


async def test_filter_pulse_and_recovery(modbus_unit):
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []

    def fail_clear(event):
        writes.append(event)
        if event.values[0] & 0xF0:
            modbus_unit.fail_write(2001, ModbusTimeoutError("clear timed out"))

    modbus_unit.on_write(fail_clear)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        with pytest.raises(ModbusTimeoutError):
            await indoor.async_control(reset_filter=True)
        modbus_unit.fail_write(2001, None)
        await indoor.async_update()
    assert [event.values for event in writes] == [[0x202], [0x2F2], [0x202]]
    assert not indoor._reset_pending


async def test_commands_are_serialized(modbus_unit):
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await asyncio.gather(
            indoor.async_control(power=False), indoor.async_control(temperature=23)
        )
    assert [event.address for event in writes] == [2000, 2000, 2001, 2002, 2002]
