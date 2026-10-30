"""Keep reads, writes and capabilities tied to the selected board."""

from unittest.mock import patch

import pytest
from modbus_connection import ModbusError

from custom_components.daikin_d3net.device import Board, D3netGateway, Mode

from .conftest import seed_dta


async def test_dta_discovery_reads_only_its_map(modbus_unit):
    seed_dta(modbus_unit, (0, 15))
    gateway = D3netGateway(modbus_unit, Board.DTA116A51)
    assert (await gateway.async_update()).updated == {"1-00", "1-15"}
    assert {(event.address, event.count) for event in modbus_unit.read_events} == {
        (0, 2),
        (5, 1),
        (1000, 3),
        (1045, 3),
        (2000, 6),
        (2090, 6),
    }
    indoor = gateway.units[15]
    assert indoor.fault.error_code == "U4"
    assert indoor.fault.malfunction and not indoor.fault.warning
    assert indoor.status.room_temperature == 23.4
    assert indoor.capabilities.fan_speeds == (1, 3, 5)
    with pytest.raises(ValueError, match="Unsupported fan speed"):
        await indoor.async_control(fan_speed=0)


@pytest.mark.parametrize("flags", [0, 0x100, 0x8100])
async def test_dta_invalid_temperature(modbus_unit, flags):
    seed_dta(modbus_unit)
    modbus_unit.input[2000][-1] = flags
    gateway = D3netGateway(modbus_unit, Board.DTA116A51)
    await gateway.async_update()
    assert gateway.units[0].status.room_temperature is None


async def test_dta_auto_selector_and_reserved_bits(modbus_unit):
    seed_dta(modbus_unit)
    modbus_unit.input[2000][1] = 0x8203
    modbus_unit.holding[2000] = [0x5261, 0xA103, 225]
    gateway = D3netGateway(modbus_unit, Board.DTA116A51)
    await gateway.async_update()
    indoor = gateway.units[0]
    assert indoor.temperature_limits() == (16, 32)
    writes = []
    modbus_unit.on_write(writes.append)
    await indoor.async_control(temperature=31)
    assert [(event.address, event.values) for event in writes] == [
        (2001, [0xA203]),
        (2002, [310]),
    ]


async def test_dta_auto_waits_for_operation(modbus_unit):
    seed_dta(modbus_unit)
    modbus_unit.input[2000][1] = 0x8003
    gateway = D3netGateway(modbus_unit, Board.DTA116A51)
    await gateway.async_update()
    with pytest.raises(ValueError, match="Wait for Auto"):
        await gateway.units[0].async_control(temperature=23)


async def test_dta_slave_mode_and_filter_reset(modbus_unit):
    seed_dta(modbus_unit)
    modbus_unit.input[2000][1] = 0x4202
    modbus_unit.holding[2000] = [0x5261, 0xA206, 225]
    gateway = D3netGateway(modbus_unit, Board.DTA116A51)
    await gateway.async_update()
    writes = []
    modbus_unit.on_write(writes.append)
    with patch("custom_components.daikin_d3net.device.gateway.asyncio.sleep"):
        await gateway.units[0].async_control(reset_filter=True)
    assert [event.values for event in writes] == [[0xA2F6], [0xA206]]
    with pytest.raises(ValueError, match="master"):
        await gateway.units[0].async_control(mode=Mode.HEAT)


async def test_dta_still_requires_holding_reads(modbus_unit):
    seed_dta(modbus_unit)
    gateway = D3netGateway(modbus_unit, Board.DTA116A51)
    await gateway.async_update()
    modbus_unit.fail_read(2000, ModbusError("FC03 failed"))
    writes = []
    modbus_unit.on_write(writes.append)
    with pytest.raises(ModbusError, match="FC03 failed"):
        await gateway.units[0].async_control(power=False)
    assert not writes


async def test_wrong_new_profile_fails_without_falling_back(modbus_unit):
    seed_dta(modbus_unit)
    modbus_unit.fail_read(
        3600, ModbusError("unsupported fault block"), register_type="input"
    )
    gateway = D3netGateway(modbus_unit, Board.EKMBDXB7V1)
    report = await gateway.async_update()
    assert not report.updated
    assert set(report.failed) == {"1-00"}
    assert gateway.profile.model == Board.EKMBDXB7V1
