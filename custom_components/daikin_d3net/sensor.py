"""Room temperature and DIII-Net status sensors."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature

from .climate import MODE_TO_HA
from .entity import D3netEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        D3netSensor(coordinator, unit, key)
        for unit in coordinator.gateway.units.values()
        for key in unit.profile.sensor_keys
    )


class D3netSensor(D3netEntity, SensorEntity):
    def __init__(self, coordinator, unit, key):
        super().__init__(coordinator, unit, key)
        self.key = key
        self._attr_name = {
            "temperature": "Temperature",
            "state": "State",
            "error_code": "Error code",
            "error_subcode": "Error subcode",
            "error_unit": "Error unit number",
        }[key]
        if key == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        status = self.unit.status
        if self.key == "temperature":
            return status.room_temperature
        if self.key == "error_code":
            return self.unit.fault.error_code
        if self.key == "error_subcode":
            return self.unit.fault.subcode
        if self.key == "error_unit":
            return self.unit.fault.unit_number
        if status.power is None:
            return None
        return MODE_TO_HA.get(status.mode) if status.power else "off"
