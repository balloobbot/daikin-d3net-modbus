"""Protocol regression tests against the library's in-memory backend."""

import asyncio
from unittest.mock import patch

import pytest
from modbus_connection import ModbusError, ModbusTimeoutError

from custom_components.daikin_d3net.device import D3netGateway, Mode
from custom_components.daikin_d3net.device.models import (
    Capabilities,
    FaultStatus,
    IndoorStatus,
)

from .conftest import seed


async def gateway_for(unit):
    gateway = D3netGateway(unit)
    await gateway.async_update()
    return gateway


async def test_documented_discovery_and_strides(modbus_unit):
    seed(modbus_unit, (0, 15, 16, 31, 32, 47, 48, 63))
    gateway = await gateway_for(modbus_unit)
    assert list(gateway.units) == [0, 15, 16, 31, 32, 47, 48, 63]
    assert gateway.units[63].name == "4-15"
    assert modbus_unit.message_spacing == 0.025
    assert modbus_unit.required_timeout == 10
    assert gateway.units[15].name == "1-15"
    assert gateway.units[15].status.setpoint == 22.5
    assert all(
        event.register_type == "input" and event.count <= 32
        for event in modbus_unit.read_events
    )
    assert {(event.address, event.count) for event in modbus_unit.read_events} >= {
        (0, 9),
        (1045, 3),
        (2090, 3),
        (2094, 1),
        (1189, 3),
        (2378, 3),
        (2382, 1),
        (3726, 2),
    }


async def test_status_and_error_mapping(modbus_unit):
    indoor = (await gateway_for(modbus_unit)).units[0]
    status = indoor.status
    assert status.power
    assert status.direction == 2
    assert status.fan_speed == 5
    assert status.mode == Mode.COOL
    assert status.operation == Mode.COOL
    assert status.master == 2
    assert status.room_temperature == 23.4
    assert indoor.fault.error_code == "U4"
    assert indoor.fault.malfunction and not indoor.fault.warning


@pytest.mark.parametrize(
    ("raw", "expected"), [(0xFFF6, -1.0), (0xFF85, -12.3), (225, 22.5)]
)
async def test_signed_temperature(modbus_unit, raw, expected):
    modbus_unit.input[2000] = [0, 0x8202, raw]
    modbus_unit.input[2004] = raw
    status = IndoorStatus(modbus_unit)
    await status.async_update()
    assert status.setpoint == expected
    assert status.room_temperature == expected


async def test_status_does_not_read_old_board_reserved_words(modbus_unit):
    status = IndoorStatus(modbus_unit)
    await status.async_update()
    assert status.room_temperature == 23.4
    addresses = {
        address
        for event in modbus_unit.read_events
        for address in range(event.address, event.address + event.count)
    }
    assert addresses == {2000, 2001, 2002, 2004}


async def test_signed_limits_and_capabilities(modbus_unit):
    modbus_unit.input[1000] = [0xBD1F, 0xF620, 0xEC1E]
    caps = Capabilities(modbus_unit)
    await caps.async_update()
    assert caps.temperature_limits(Mode.COOL) == (-10, 32)
    assert caps.temperature_limits(Mode.HEAT) == (-20, 30)
    assert caps.fan_speeds == (0, 1, 3, 5)
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
        {"fan_speed": 6},
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
        (2001, [0x03]),
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
    assert writes[0].address == 2001 and writes[0].values == [0x06]
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
    assert [event.values for event in writes] == [[0x02], [0xF2], [0x02]]
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


@pytest.mark.parametrize("index", [0, 15, 16, 32, 48, 63])
async def test_holding_reads_preserve_bits_and_skip_matching_sync(modbus_unit, index):
    seed(modbus_unit, (index,))
    # Bits 15, 11 and 1–3 are outside the power/fan fields we own.
    preserved = 0x880E
    modbus_unit.holding[2000 + 3 * index] = [0x5261 | preserved, 0x202, 225]
    gateway = await gateway_for(modbus_unit)
    writes = []
    modbus_unit.on_write(writes.append)
    await gateway.units[index].async_control(power=False)
    assert [
        (event.address, event.count)
        for event in modbus_unit.read_events
        if event.register_type == "holding"
    ] == [(2000 + 3 * index, 3)]
    assert [(event.address, event.values) for event in writes] == [
        (2000 + 3 * index, [0x5260 | preserved])
    ]
    assert gateway.units[index].status.power  # Holding values are not live state.


async def test_holding_target_still_requires_sync_after_wall_change(modbus_unit):
    # The wall controller turned the unit off, but the holding word is still ON.
    modbus_unit.input[2000] = [0x5200, 0x8202, 225, 0, 234, 0x8000]
    modbus_unit.holding[2000] = [0x5261 | 0x880E, 0x202, 225]
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep") as sleep:
        await indoor.async_control(power=True)
    assert [event.values for event in writes] == [[0x5260 | 0x880E], [0x5261 | 0x880E]]
    sleep.assert_awaited_once()
    assert 0.50 < sleep.call_args.args[0] <= 0.51


async def test_each_command_reads_fresh_holding_values(modbus_unit):
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await indoor.async_control(power=False)
        # Another controller changes bits outside the fields this integration owns.
        modbus_unit.holding[2000] = [0x5261 | 0x880E, 0x202, 225]
        writes.clear()
        await indoor.async_control(power=False)
    assert [event.values for event in writes] == [[0x5260 | 0x880E]]
    assert (
        sum(event.register_type == "holding" for event in modbus_unit.read_events) == 2
    )


@pytest.mark.parametrize(
    "error_name",
    [
        "ModbusTimeoutError",
        "ModbusConnectionError",
        "ModbusProtocolError",
        "IllegalDataAddressError",
        "IllegalDataValueError",
        "IllegalFunctionError",
    ],
)
async def test_holding_read_failures_abort_command(modbus_unit, error_name):
    import modbus_connection

    error_type = getattr(modbus_connection, error_name)
    error = error_type()
    gateway = await gateway_for(modbus_unit)
    modbus_unit.fail_read(2000, error)
    writes = []
    modbus_unit.on_write(writes.append)
    with pytest.raises(error_type):
        await gateway.units[0].async_control(power=False)
    assert not writes
    modbus_unit.fail_read(2000, None)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await gateway.units[0].async_control(power=False)
    assert writes


async def test_auto_setpoint_preserves_reserved_upper_byte(modbus_unit):
    modbus_unit.input[2000] = [0x5201, 0x8203, 225, 0, 234, 0x8000]
    # The old DTA operation selector is reserved on EKMBDXB.
    modbus_unit.holding[2000] = [0x5261, 0xA103, 225]
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    await indoor.async_control(temperature=23)
    assert [(event.address, event.values) for event in writes] == [
        (2002, [230]),
    ]


async def test_filter_reset_preserves_other_holding_bits(modbus_unit):
    modbus_unit.holding[2000] = [0x5261, 0xA202, 225]
    indoor = (await gateway_for(modbus_unit)).units[0]
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await indoor.async_control(reset_filter=True)
    assert [event.values for event in writes] == [[0xA2F2], [0xA202]]


@pytest.mark.parametrize("index", [16, 31, 32, 47, 48, 63])
async def test_each_group_communication_failure_blocks_commands(modbus_unit, index):
    writes = []
    modbus_unit.on_write(writes.append)
    seed(modbus_unit, (0, index))
    gateway = await gateway_for(modbus_unit)
    modbus_unit.input[5 + index // 16] = 1 << (index % 16)
    report = await gateway.async_update()
    assert report.updated == {"1-00"}
    assert set(report.failed) == {gateway.units[index].name}
    with pytest.raises(ModbusError, match="not communicating"):
        await gateway.units[index].async_control(power=False)
    assert not writes


@pytest.mark.parametrize(
    ("steps", "speeds"),
    [(1, (5,)), (2, (0, 1, 5)), (3, (0, 1, 3, 5)), (4, ()), (5, (0, 1, 2, 3, 4, 5))],
)
async def test_documented_fan_steps(modbus_unit, steps, speeds):
    writes = []
    modbus_unit.on_write(writes.append)
    modbus_unit.input[1000] = [0x8D1F | steps << 12, 0x1020, 0x0A1E]
    indoor = (await gateway_for(modbus_unit)).units[0]
    assert indoor.capabilities.fan_speeds == speeds
    if 0 in speeds:
        modbus_unit.holding[2000] = [0x5261, 2, 225]
        await indoor.async_control(fan_speed=0)
        assert writes[-1].values == [0x0261]


@pytest.mark.parametrize(
    ("word", "code"),
    [(0x4337, "C7"), (0x5534, "U4"), (0x3030, "00"), (0, None), (0xFF34, None)],
)
async def test_extended_faults(modbus_unit, word, code):
    modbus_unit.input[3600] = [word, 0xA700 | 42]
    fault = FaultStatus(modbus_unit)
    await fault.async_update()
    assert fault.error_code == code
    assert fault.subcode == 42
    assert fault.unit_number == 10
    assert fault.malfunction and fault.alarm and fault.warning


async def test_no_fan_unit_does_not_set_fan_control_flag(modbus_unit):
    writes = []
    modbus_unit.on_write(writes.append)
    modbus_unit.input[1000] = [0x1F, 0x1020, 0x0A1E]
    modbus_unit.holding[2000] = [1, 2, 225]
    indoor = (await gateway_for(modbus_unit)).units[0]
    await indoor.async_control(power=False)
    assert writes[-1].values == [0]


async def test_ventilation_only_unit_is_not_exposed_as_climate(modbus_unit):
    seed(modbus_unit, (0, 16))
    modbus_unit.input[1048] = [0, 0, 0]
    gateway = await gateway_for(modbus_unit)
    assert list(gateway.units) == [0]


async def test_auto_temperature_without_current_operation(modbus_unit):
    writes = []
    modbus_unit.on_write(writes.append)
    modbus_unit.input[2000] = [0x5201, 0x8003, 225]
    modbus_unit.holding[2000] = [0x5261, 0xAB03, 225]
    indoor = (await gateway_for(modbus_unit)).units[0]
    await indoor.async_control(temperature=23)
    assert [(e.address, e.values) for e in writes] == [(2002, [230])]
    with pytest.raises(ValueError, match="between 16 and 30"):
        await indoor.async_control(temperature=31)
