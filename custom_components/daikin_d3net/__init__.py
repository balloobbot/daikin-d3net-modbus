"""Daikin DTA116A51 DIII-Net integration."""

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform

from .connection import connection_params
from .const import CONF_UNIT_ID
from .coordinator import D3netCoordinator
from .device import D3netGateway

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_setup_entry(hass, entry) -> bool:
    unit = async_get_unit(
        hass, entry, connection_params(entry.data), entry.data[CONF_UNIT_ID]
    )
    coordinator = D3netCoordinator(hass, entry, D3netGateway(unit))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
