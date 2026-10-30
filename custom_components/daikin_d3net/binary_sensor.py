"""Documented fault and filter status bits."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory

from .entity import D3netEntity

PARALLEL_UPDATES = 0
NAMES = {
    "filter_sign": "Filter warning",
    "forced_off": "Forced off",
    "malfunction": "Malfunction",
    "warning": "Warning",
    "sensor_error": "Temperature sensor fault",
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        D3netBinarySensor(coordinator, unit, key)
        for unit in coordinator.gateway.units.values()
        for key in NAMES
    )


class D3netBinarySensor(D3netEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, unit, key):
        super().__init__(coordinator, unit, key)
        self.key = key
        self._attr_name = NAMES[key]

    @property
    def is_on(self):
        value = getattr(self.unit.status, self.key)
        return None if value is None else bool(value)
