"""Optional separate temperature setpoint control."""

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature

from .entity import D3netEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        D3netSetpoint(coordinator, unit)
        for unit in coordinator.gateway.units.values()
        if unit.capabilities.heat or unit.capabilities.cool
    )


class D3netSetpoint(D3netEntity, NumberEntity):
    _attr_name = "Setpoint"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, unit):
        super().__init__(coordinator, unit, "setpoint")

    @property
    def native_value(self):
        return self.unit.status.setpoint

    @property
    def native_min_value(self):
        return self.temperature_limits()[0]

    @property
    def native_max_value(self):
        return self.temperature_limits()[1]

    async def async_set_native_value(self, value):
        await self.async_control(temperature=value)
