"""EKMBDXB7V1 registers from design guide 4P642495-1A, §3.

Addresses are zero-based. Input registers report state; holding registers
store commands.
"""

from enum import IntEnum

from modbus_connection.model import Component, bit, bits, gauge, raw_register


class Mode(IntEnum):
    """Operating modes on pages 26 and 34."""

    FAN = 0
    HEAT = 1
    COOL = 2
    AUTO = 3
    DEPENDENT = 6  # Write-only: setpoint control on a cool/heat slave.
    DRY = 7


class InputComponent(Component):
    """Constrain reads to the adapter's 32-register request limit (§2.2.1)."""

    register_space = "input"
    max_span = 32
    max_gap = 1


class AdapterStatus(InputComponent):
    """Ready flag and four groups of 16 units (page 21)."""

    ready = bit(0, 0)
    other_controller = bit(0, 1)
    connected_1 = raw_register(1)
    connected_2 = raw_register(2)
    connected_3 = raw_register(3)
    connected_4 = raw_register(4)
    errors_1 = raw_register(5)
    errors_2 = raw_register(6)
    errors_3 = raw_register(7)
    errors_4 = raw_register(8)

    @property
    def connected(self) -> int:
        return sum(
            getattr(self, f"connected_{group + 1}") << (16 * group)
            for group in range(4)
        )

    @property
    def communication_errors(self) -> int:
        return sum(
            getattr(self, f"errors_{group + 1}") << (16 * group) for group in range(4)
        )


class HoldingSettings(Component):
    """Power/fan, mode/reset and setpoint command registers."""

    power_fan = raw_register(2000, stride=3)
    mode = raw_register(2001, stride=3)
    setpoint = raw_register(2002, stride=3)

    async def async_read(self) -> tuple[int, int, int]:
        """Read the unit's three holding registers."""
        await self.async_update()
        return self.power_fan, self.mode, self.setpoint


class Capabilities(InputComponent):
    """Three registers per indoor unit (pages 22–23)."""

    fan = bit(1000, 0, stride=3)
    cool = bit(1000, 1, stride=3)
    heat = bit(1000, 2, stride=3)
    auto = bit(1000, 3, stride=3)
    dry = bit(1000, 4, stride=3)
    direction_steps = bits(1000, 8, 3, stride=3)
    direction = bit(1000, 11, stride=3)
    fan_steps = bits(1000, 12, 3, stride=3)
    fan_speed = bit(1000, 15, stride=3)
    cooling_limits = raw_register(1001, stride=3)
    heating_limits = raw_register(1002, stride=3)

    def temperature_limits(self, mode: Mode) -> tuple[int, int]:
        """Return the signed low/high bytes as minimum/maximum °C."""
        word = self.heating_limits if mode == Mode.HEAT else self.cooling_limits
        if word is None:
            raise ValueError("Capabilities have not been read")
        return signed_byte(word >> 8), signed_byte(word & 0xFF)

    @property
    def modes(self) -> tuple[Mode, ...]:
        return tuple(
            mode
            for mode, supported in (
                (Mode.FAN, self.fan),
                (Mode.HEAT, self.heat),
                (Mode.COOL, self.cool),
                (Mode.AUTO, self.auto and self.heat and self.cool),
                (Mode.DRY, self.dry),
            )
            if supported
        )

    @property
    def fan_speeds(self) -> tuple[int, ...]:
        if not self.fan_speed:
            return ()
        # Four-step capability is listed, but no command values are specified.
        return {1: (5,), 2: (0, 1, 5), 3: (0, 1, 3, 5), 5: (0, 1, 2, 3, 4, 5)}.get(
            self.fan_steps, ()
        )

    @property
    def fan_names(self) -> dict[int, str]:
        if self.fan_steps == 5:
            return {
                0: "auto",
                1: "very low",
                2: "low",
                3: "medium",
                4: "high",
                5: "very high",
            }
        return {0: "auto", 1: "low", 3: "medium", 5: "high"}

    @property
    def directions(self) -> tuple[int, ...]:
        if not self.direction or self.direction_steps not in (2, 3, 4, 5):
            return ()
        return (*range(self.direction_steps), 6, 7)


def signed_byte(value: int) -> int:
    """Decode an eight-bit two's-complement integer."""
    return value - 256 if value & 0x80 else value


class IndoorStatus(InputComponent):
    """Documented climate fields in the six-word stride (pages 25–28)."""

    power = bit(2000, 0, stride=6)
    forced_off = bit(2000, 2, stride=6)
    direction = bits(2000, 8, 3, stride=6)
    fan_speed = bits(2000, 12, 3, stride=6)
    mode = bits(2001, 0, 4, stride=6)
    filter_sign = bits(2001, 4, 4, stride=6)
    operation = bits(2001, 8, 4, stride=6)
    master = bits(2001, 14, 2, stride=6)
    setpoint = gauge(2002, 0.1, stride=6, unit="°C")
    temperature = gauge(2004, 0.1, stride=6, unit="°C")

    @property
    def room_temperature(self) -> float | None:
        """Return the reported suction or configured controller temperature."""
        return self.temperature


class FaultStatus(InputComponent):
    """ASCII fault code, subcode and severity (page 31)."""

    code = raw_register(3600, stride=2)
    unit_number = bits(3601, 12, 4, stride=2)
    warning = bit(3601, 10, stride=2)
    alarm = bit(3601, 9, stride=2)
    malfunction = bit(3601, 8, stride=2)
    subcode = bits(3601, 0, 6, stride=2)

    @property
    def error_code(self) -> str | None:
        """Decode two ASCII characters; 00 means no fault."""
        if self.code is None:
            return None
        characters = (self.code >> 8, self.code & 0xFF)
        if not all(32 <= value <= 126 for value in characters):
            return None
        return "".join(chr(value) for value in characters)
