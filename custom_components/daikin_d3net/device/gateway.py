"""EKMBDXB7V1 discovery, polling and commands from design guide 4P642495-1A."""

import asyncio
import math
import time

from modbus_connection import ModbusConnectionError, ModbusError, ModbusUnit
from modbus_connection.model import UpdateReport

from .models import (
    AdapterStatus,
    Capabilities,
    FaultStatus,
    HoldingSettings,
    IndoorStatus,
    Mode,
)

# Fields changed by commands; preserve the other holding-register bits.
CONTROL_MASKS = (0x77F1, 0x00FF, 0xFFFF)

# §2.2.3–2.2.5: at least 5 ms silence + 20 ms at 9600 baud.
MESSAGE_SPACING = 0.025
# §2.3.2: more than 0.5 seconds between writes to the same register.
WRITE_INTERVAL = 0.51


class D3netGateway:
    """A DIII-Net adapter using a shared Modbus connection."""

    def __init__(self, unit: ModbusUnit) -> None:
        self.modbus_unit = unit
        unit.set_message_spacing(MESSAGE_SPACING)
        unit.require_timeout(10)
        self.adapter = AdapterStatus(unit)
        self.units: dict[int, IndoorUnit] = {}
        self._setup_done = False

    async def async_setup(self) -> None:
        """Discover climate units at addresses 1-00 through 4-15."""
        if self._setup_done:
            return
        await self.adapter.async_update()
        if not self.adapter.ready:
            raise ModbusError("DIII-Net adapter is not ready")
        units = {}
        for index in range(64):
            if self.adapter.connected & (1 << index):
                indoor = IndoorUnit(self, index)
                await indoor.capabilities.async_update()
                if not indoor.capabilities.modes:
                    continue
                units[index] = indoor
        if not units:
            raise ModbusError("No supported climate units are connected")
        self.units = units
        self._setup_done = True

    async def async_update(self) -> UpdateReport:
        """Poll connected units and collect per-unit failures."""
        await self.async_setup()
        await self.adapter.async_update()
        if not self.adapter.ready:
            raise ModbusError("DIII-Net adapter is not ready")
        report = UpdateReport()
        for unit in self.units.values():
            try:
                self.check_connected(unit.index)
                await unit.async_update()
            except ModbusConnectionError:
                raise
            except ModbusError as err:
                report.failed[unit.name] = err
            else:
                report.updated.add(unit.name)
        return report

    def check_connected(self, index: int) -> None:
        """Reject stale status when the DIII bus reports a communication fault."""
        if (
            not self.adapter.ready
            or not self.adapter.connected & (1 << index)
            or self.adapter.communication_errors & (1 << index)
        ):
            raise ModbusError(
                f"Indoor unit {index // 16 + 1}-{index % 16:02d} is not communicating"
            )


class IndoorUnit:
    """An indoor unit and its command lock."""

    def __init__(self, gateway: D3netGateway, index: int) -> None:
        self.gateway = gateway
        self.index = index
        self.name = f"{index // 16 + 1}-{index % 16:02d}"
        self.capabilities = Capabilities(gateway.modbus_unit, index=index + 1)
        self.status = IndoorStatus(gateway.modbus_unit, index=index + 1)
        self.fault = FaultStatus(gateway.modbus_unit, index=index + 1)
        self.settings = HoldingSettings(gateway.modbus_unit, index=index + 1)
        self._lock = asyncio.Lock()
        self._last_write: dict[int, float] = {}
        self._reset_pending: int | None = None

    async def async_update(self) -> None:
        async with self._lock:
            await self.status.async_update()
            await self.fault.async_update()
            if self._reset_pending is not None:
                await self._clear_reset()

    async def _write(self, offset: int, values: list[int]) -> None:
        """Enforce register write spacing, including failed or cancelled writes."""
        addresses = range(offset, offset + len(values))
        deadline = (
            max(self._last_write.get(a, -math.inf) for a in addresses) + WRITE_INTERVAL
        )
        if (delay := deadline - time.monotonic()) > 0:
            await asyncio.sleep(delay)
        try:
            await self.gateway.modbus_unit.write_registers(
                2000 + self.index * 3 + offset, values
            )
        finally:
            for address in addresses:
                self._last_write[address] = time.monotonic()

    def _mode_word(self, mode: int | None = None) -> int:
        """Build the mode nibble; the upper byte is reserved."""
        status = self.status
        caps = self.capabilities
        mode = status.mode if mode is None else mode
        if mode not in caps.modes:
            raise ValueError("This indoor unit does not support the requested mode")
        if mode == Mode.AUTO and status.master == 1:
            raise ValueError("Auto mode requires the cool/heat master")
        if (
            mode in (Mode.HEAT, Mode.COOL)
            and status.master == 1
            and caps.heat
            and caps.cool
        ):
            # Page 34: code 6 changes setpoint without requesting system mode.
            if mode != status.mode:
                raise ValueError("Change cooling/heating at the system's master unit")
            mode = Mode.DEPENDENT
        return mode

    async def _clear_reset(self) -> None:
        await self._write(1, [self._reset_pending])
        self._reset_pending = None

    async def async_control(
        self,
        *,
        power: bool | None = None,
        mode: Mode | None = None,
        temperature: float | None = None,
        fan_speed: int | None = None,
        direction: int | None = None,
        reset_filter: bool = False,
    ) -> None:
        """Sync affected holding registers with live status, then write the command."""
        async with self._lock:
            await self.gateway.adapter.async_update()
            self.gateway.check_connected(self.index)
            await self.status.async_update()
            if self._reset_pending is not None:
                await self._clear_reset()
            status, caps = self.status, self.capabilities
            if power and status.forced_off:
                raise ValueError("The indoor unit is forced off")
            if fan_speed is not None and fan_speed not in caps.fan_speeds:
                raise ValueError("Unsupported fan speed")
            if direction is not None and direction not in caps.directions:
                raise ValueError("Unsupported fan direction")
            if mode is not None and mode not in caps.modes:
                raise ValueError("Unsupported operating mode")
            # Construct and validate every word before sending any writes.
            baseline: dict[int, int] = {}
            target: dict[int, int] = {}
            if power is not None or fan_speed is not None or direction is not None:
                speed = status.fan_speed if caps.fan_speed else 0
                flap = status.direction if caps.direction else 0
                fan_control = 0x60 if caps.fan_speed or caps.direction else 0
                baseline[0] = (
                    int(status.power) | fan_control | (flap << 8) | (speed << 12)
                )
                target[0] = (
                    int(status.power if power is None else power)
                    | fan_control
                    | ((flap if direction is None else direction) << 8)
                    | ((speed if fan_speed is None else fan_speed) << 12)
                )
            if mode is not None or temperature is not None or reset_filter:
                baseline[1] = self._mode_word()
                target[1] = self._mode_word(mode)
            if temperature is not None:
                selected_mode = status.mode if mode is None else mode
                if selected_mode == Mode.AUTO:
                    limits = [
                        caps.temperature_limits(candidate)
                        for candidate in (Mode.HEAT, Mode.COOL)
                    ]
                    low = max(bounds[0] for bounds in limits)
                    high = min(bounds[1] for bounds in limits)
                else:
                    low, high = caps.temperature_limits(selected_mode)
                if not math.isfinite(temperature) or not low <= temperature <= high:
                    raise ValueError(f"Temperature must be between {low} and {high} °C")
                baseline[2] = round(status.setpoint * 10) & 0xFFFF
                target[2] = round(temperature * 10) & 0xFFFF
            if reset_filter:
                target[1] |= 0xF0
            changed = {
                offset for offset in target if target[offset] != baseline[offset]
            }
            if not changed:
                return
            settings = await self.settings.async_read()
            for offset in baseline:
                retained = settings[offset] & ~CONTROL_MASKS[offset]
                baseline[offset] |= retained
                target[offset] |= retained
            # Synchronize the mode before a setpoint write, including dependent mode.
            sync_offsets = changed | ({1} if 2 in changed else set())
            for offset in sorted(sync_offsets):
                if settings[offset] != baseline[offset]:
                    await self._write(offset, [baseline[offset]])
            for offset in sorted(changed):
                if reset_filter and offset == 1:
                    self._reset_pending = target[offset] & ~0xF0
                await self._write(offset, [target[offset]])
            if reset_filter:
                await self._clear_reset()
