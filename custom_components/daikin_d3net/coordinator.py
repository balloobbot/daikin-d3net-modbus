"""Poll a Daikin adapter and report availability per indoor unit."""

import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError
from modbus_connection.model import UpdateReport

from .device import D3netGateway

_LOGGER = logging.getLogger(__name__)


class D3netCoordinator(DataUpdateCoordinator[UpdateReport]):
    def __init__(self, hass, entry, gateway: D3netGateway) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=10),
        )
        self.gateway = gateway
        self._failed: set[str] = set()

    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.gateway.async_update()
        except ModbusError as err:
            raise UpdateFailed(str(err)) from err
        if not report.updated:
            raise UpdateFailed("No DIII-Net indoor units are communicating")
        for name in report.failed.keys() - self._failed:
            _LOGGER.warning("Indoor unit %s unavailable: %s", name, report.failed[name])
        self._failed = set(report.failed)
        return report
