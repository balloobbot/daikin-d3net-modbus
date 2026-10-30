"""Optional separate power control for dashboard compatibility."""

from homeassistant.components.switch import SwitchEntity

from .entity import D3netEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        D3netPower(coordinator, unit) for unit in coordinator.gateway.units.values()
    )


class D3netPower(D3netEntity, SwitchEntity):
    _attr_name = "Power"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, unit):
        super().__init__(coordinator, unit, "power")

    @property
    def is_on(self):
        return self.unit.status.power

    async def async_turn_on(self, **kwargs):
        await self.async_control(power=True)

    async def async_turn_off(self, **kwargs):
        await self.async_control(power=False)
