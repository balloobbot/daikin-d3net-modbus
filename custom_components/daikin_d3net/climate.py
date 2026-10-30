"""Climate controls derived from the adapter's capability registers."""

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .device import Mode
from .entity import D3netEntity

PARALLEL_UPDATES = 0
MODE_TO_HA = {
    Mode.FAN: HVACMode.FAN_ONLY,
    Mode.HEAT: HVACMode.HEAT,
    Mode.COOL: HVACMode.COOL,
    Mode.AUTO: HVACMode.AUTO,
    Mode.DRY: HVACMode.DRY,
}
HA_TO_MODE = {value: key for key, value in MODE_TO_HA.items()}
FAN_NAMES = {1: "low", 3: "medium", 5: "high"}
DIRECTION_NAMES = {0: "P0", 1: "P1", 2: "P2", 3: "P3", 4: "P4", 6: "off", 7: "on"}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        D3netClimate(coordinator, unit) for unit in coordinator.gateway.units.values()
    )


class D3netClimate(D3netEntity, ClimateEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.1

    def __init__(self, coordinator, unit):
        super().__init__(coordinator, unit, "climate")
        caps = unit.capabilities
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        )
        if caps.heat or caps.cool:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if len(caps.fan_speeds) > 1:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = [FAN_NAMES[value] for value in caps.fan_speeds]
        if caps.directions:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = [
                DIRECTION_NAMES[value] for value in caps.directions
            ]

    @property
    def hvac_modes(self):
        return [
            HVACMode.OFF,
            *(
                MODE_TO_HA[mode]
                for mode in self.unit.capabilities.modes
                if not (mode == Mode.AUTO and self.unit.status.master == 1)
            ),
        ]

    @property
    def hvac_mode(self):
        if self.unit.status.power is None:
            return None
        return (
            MODE_TO_HA.get(self.unit.status.mode)
            if self.unit.status.power
            else HVACMode.OFF
        )

    @property
    def hvac_action(self):
        if self.unit.status.power is None:
            return None
        if not self.unit.status.power:
            return HVACAction.OFF
        return {0: HVACAction.FAN, 1: HVACAction.HEATING, 2: HVACAction.COOLING}.get(
            self.unit.status.operation
        )

    @property
    def current_temperature(self):
        return self.unit.status.room_temperature

    @property
    def target_temperature(self):
        return self.unit.status.setpoint

    @property
    def min_temp(self):
        return self.temperature_limits()[0]

    @property
    def max_temp(self):
        return self.temperature_limits()[1]

    @property
    def fan_mode(self):
        return FAN_NAMES.get(self.unit.status.fan_speed)

    @property
    def swing_mode(self):
        return DIRECTION_NAMES.get(self.unit.status.direction)

    async def async_turn_on(self):
        await self.async_control(power=True)

    async def async_turn_off(self):
        await self.async_control(power=False)

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.async_control(power=False)
        else:
            await self.async_control(power=True, mode=HA_TO_MODE[hvac_mode])

    async def async_set_temperature(self, **kwargs):
        changes = {"temperature": kwargs[ATTR_TEMPERATURE]}
        if (mode := kwargs.get("hvac_mode")) is not None:
            changes["power"] = mode != HVACMode.OFF
            if mode != HVACMode.OFF:
                changes["mode"] = HA_TO_MODE[mode]
        await self.async_control(**changes)

    async def async_set_fan_mode(self, fan_mode):
        await self.async_control(
            fan_speed={name: value for value, name in FAN_NAMES.items()}[fan_mode]
        )

    async def async_set_swing_mode(self, swing_mode):
        await self.async_control(
            direction={name: value for value, name in DIRECTION_NAMES.items()}[
                swing_mode
            ]
        )
