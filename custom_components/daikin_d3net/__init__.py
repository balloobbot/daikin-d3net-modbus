"""Daikin DIII-Net integration."""

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er

from .connection import connection_params
from .const import CONF_ADAPTER_MODEL, CONF_UNIT_ID
from .coordinator import D3netCoordinator
from .device import Board, D3netGateway

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
    if entry.data.get(CONF_ADAPTER_MODEL) not in Board:
        raise ConfigEntryError(
            "Select the adapter model using Reconfigure in the integration menu."
        )
    unit = async_get_unit(
        hass, entry, connection_params(entry.data), entry.data[CONF_UNIT_ID]
    )
    gateway = D3netGateway(unit, Board(entry.data[CONF_ADAPTER_MODEL]))
    coordinator = D3netCoordinator(hass, entry, gateway)
    await coordinator.async_config_entry_first_refresh()
    # Keep shared identities when changing profiles; remove unsupported entities.
    registry = er.async_get(hass)
    diagnostics = {"alarm", "sensor_error", "error_subcode", "error_unit"}
    supported = set(gateway.profile.sensor_keys + gateway.profile.binary_sensor_keys)
    units_by_name = {indoor.name: indoor for indoor in gateway.units.values()}
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        address, _, key = entity.unique_id.rpartition(":")
        name = address.rpartition(":")[2]
        group = name.split("-")[0]
        unsupported_control = False
        if indoor := units_by_name.get(name):
            caps = indoor.capabilities
            unsupported_control = (
                (key == "fan_speed" and len(caps.fan_speeds) <= 1)
                or (key == "direction" and not caps.directions)
                or (key == "setpoint" and not (caps.heat or caps.cool))
            )
        if (
            unsupported_control
            or key in diagnostics - supported
            or (group in ("2", "3", "4") and gateway.profile.unit_count == 16)
        ):
            registry.async_remove(entity.entity_id)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
