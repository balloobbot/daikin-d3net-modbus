"""Recorded cross-check cases at martinstafford/daikin_d3net@92ae9ab.

The shared climate fields also appear in EKMBDXB guide 4P642495-1A. tools/compare_reference.py
also runs these common cases through the actual original decoder, without
vendoring its source into this independent implementation.
"""

import pytest

from custom_components.daikin_d3net.device.models import Capabilities, IndoorStatus


@pytest.mark.parametrize("index", [0, 1, 15])
async def test_reference_address_math(modbus_unit, index):
    from .conftest import seed

    seed(modbus_unit, (index,))
    caps = Capabilities(modbus_unit, index=index + 1)
    status = IndoorStatus(modbus_unit, index=index + 1)
    await caps.async_update()
    await status.async_update()
    assert [(event.address, event.count) for event in modbus_unit.read_events] == [
        (1000 + index * 3, 3),
        (2000 + index * 6, 3),
        (2004 + index * 6, 1),
    ]
    # Positive, ordinary values agree with the original integration.
    assert status.power is True
    assert status.mode == 2
    assert status.fan_speed == 5
    assert status.direction == 2
    assert status.setpoint == 22.5
    assert status.temperature == 23.4
    assert caps.temperature_limits(2) == (16, 32)
    assert caps.temperature_limits(1) == (10, 30)
