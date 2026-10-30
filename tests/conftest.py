"""Input status and holding-register fixtures."""

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.daikin_d3net.const import CONF_TRANSPORT, CONF_UNIT_ID, DOMAIN

DATA = {
    "adapter_model": "EKMBDXB7V1",
    CONF_HOST: "gateway.local",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
    CONF_TRANSPORT: "tcp",
    CONF_NAME: "Daikin",
}


def seed(unit, indexes=(0,)):
    unit.input[0] = [1, 0, 0, 0, 0, 0, 0, 0, 0]
    for group in range(4):
        unit.input[1 + group] = sum(
            1 << (index % 16) for index in indexes if index // 16 == group
        )
    for index in indexes:
        # All modes, five flap positions, three fan speeds; cooling 16–32, heating 10–30.
        unit.input[1000 + 3 * index] = [0xBD1F, 0x1020, 0x0A1E]
        # On, P2, high fan; cooling master; 22.5 °C; U4 malfunction; 23.4 °C, valid.
        unit.input[2000 + 6 * index] = [0x5201, 0x8202, 225]
        unit.input[2004 + 6 * index] = 234
        unit.input[3600 + 2 * index] = [0x5534, 0x100]
        unit.holding[2000 + 3 * index] = [0, 0, 0]
    return unit


def seed_dta(unit, indexes=(0,)):
    """Seed DTA116A51 fields without any newer-board register blocks."""
    unit.input.clear()
    unit.holding.clear()
    unit.input.update({0: 1, 1: sum(1 << index for index in indexes), 5: 0})
    for index in indexes:
        unit.input[1000 + 3 * index] = [0xBD1F, 0x1020, 0x0A1E]
        unit.input[2000 + 6 * index] = [0x5201, 0x8202, 225, 0x294, 234, 0x8000]
        unit.holding[2000 + 3 * index] = [0, 0, 0]
    return unit


@pytest.fixture
def modbus_unit():
    return seed(MockModbusConnection().for_unit(1))


@pytest.fixture
def mock_entry():
    return MockConfigEntry(
        domain=DOMAIN, title="Daikin", data=DATA, unique_id="gateway.local:502:1"
    )


@pytest.fixture
def shared_unit(modbus_unit):
    @asynccontextmanager
    async def temporary(*args, **kwargs):
        yield modbus_unit

    with (
        patch(
            "custom_components.daikin_d3net.async_get_unit", return_value=modbus_unit
        ) as acquire,
        patch(
            "custom_components.daikin_d3net.config_flow.async_get_temporary_unit",
            temporary,
        ),
    ):
        yield acquire
