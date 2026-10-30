"""Optional separate mode, fan and flap controls."""

from homeassistant.components.select import SelectEntity

from .climate import DIRECTION_NAMES, FAN_NAMES, MODE_TO_HA
from .device import Mode
from .entity import D3netEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = []
    for unit in coordinator.gateway.units.values():
        entities.append(D3netSelect(coordinator, unit, "mode", MODE_TO_HA))
        if len(unit.capabilities.fan_speeds) > 1:
            entities.append(D3netSelect(coordinator, unit, "fan_speed", FAN_NAMES))
        if unit.capabilities.directions:
            entities.append(
                D3netSelect(coordinator, unit, "direction", DIRECTION_NAMES)
            )
    async_add_entities(entities)


class D3netSelect(D3netEntity, SelectEntity):
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, unit, key, names):
        super().__init__(coordinator, unit, key)
        self.key = key
        self.names = names
        self._attr_name = {
            "mode": "Mode",
            "fan_speed": "Fan speed",
            "direction": "Fan direction",
        }[key]

    @property
    def options(self):
        caps = self.unit.capabilities
        values = (
            caps.modes
            if self.key == "mode"
            else caps.fan_speeds
            if self.key == "fan_speed"
            else caps.directions
        )
        return [
            self.names[value]
            for value in values
            if not (
                self.key == "mode"
                and value == Mode.AUTO
                and self.unit.status.master == 1
            )
        ]

    @property
    def current_option(self):
        return self.names.get(getattr(self.unit.status, self.key))

    async def async_select_option(self, option):
        value = {name: value for value, name in self.names.items()}[option]
        await self.async_control(**{self.key: value})
