"""Common identity, availability and command handling."""

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from modbus_connection import ModbusError

from .connection import endpoint_id
from .const import DOMAIN
from .coordinator import D3netCoordinator


class D3netEntity(CoordinatorEntity[D3netCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, unit, key: str) -> None:
        super().__init__(coordinator, context=unit.index)
        self.unit = unit
        entry = coordinator.config_entry
        identity = f"{endpoint_id(entry.data)}:{unit.name}"
        self._attr_unique_id = f"{identity}:{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            manufacturer="Daikin",
            model=unit.profile.model,
            name=f"{entry.title} {unit.name}",
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.unit.name in self.coordinator.data.updated
        )

    async def async_control(self, **changes) -> None:
        try:
            await self.unit.async_control(**changes)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        except ModbusError as err:
            raise HomeAssistantError(f"Daikin command failed: {err}") from err
        finally:
            await self.coordinator.async_request_refresh()

    def temperature_limits(self) -> tuple[int, int]:
        return self.unit.temperature_limits()
