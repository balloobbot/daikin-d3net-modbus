"""Filter reset with a bounded pulse and retryable clear."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import D3netEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        D3netFilterReset(coordinator, unit)
        for unit in coordinator.gateway.units.values()
    )


class D3netFilterReset(D3netEntity, ButtonEntity):
    _attr_name = "Filter reset"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, unit):
        super().__init__(coordinator, unit, "filter_reset")

    async def async_press(self):
        await self.async_control(reset_filter=True)
