"""DTA116A51 registers from EDMT721419, functional specification §§3–4.

Addresses here are zero-based wire addresses, not 3xxxx/4xxxx references.
Only documented input registers are read. The adapter does not support FC03.
"""

from enum import IntEnum

from modbus_connection.model import Component, bit, bits, gauge, raw_register


class Mode(IntEnum):
    """Operating modes in §4-1-5 and §4-2-2."""

    FAN = 0
    HEAT = 1
    COOL = 2
    AUTO = 3
    DEPENDENT = 6  # Write-only: setpoint control on a cool/heat slave.
    DRY = 7


class InputComponent(Component):
    """Constrain reads to the adapter's 32-register request limit (§2-2-4)."""

    register_space = "input"
    max_span = 32
    max_gap = 1


class AdapterStatus(InputComponent):
    """Ready flag and 16-unit bitmaps (§4-1-1 through §4-1-3)."""

    ready = bit(0, 0)
    connected = raw_register(1)
    communication_errors = raw_register(5)


class Capabilities(InputComponent):
    """Three registers per indoor unit (§4-1-4)."""

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
        return {1: (5,), 2: (1, 5), 3: (1, 3, 5)}.get(self.fan_steps, ())

    @property
    def directions(self) -> tuple[int, ...]:
        if not self.direction or self.direction_steps not in (2, 3, 4, 5):
            return ()
        return (*range(self.direction_steps), 6, 7)


def signed_byte(value: int) -> int:
    """Decode an eight-bit two's-complement integer."""
    return value - 256 if value & 0x80 else value


class IndoorStatus(InputComponent):
    """Six status words per indoor unit (§4-1-5)."""

    power = bit(2000, 0, stride=6)
    forced_off = bit(2000, 2, stride=6)
    direction = bits(2000, 8, 3, stride=6)
    fan_speed = bits(2000, 12, 3, stride=6)
    mode = bits(2001, 0, 4, stride=6)
    filter_sign = bits(2001, 4, 4, stride=6)
    operation = bits(2001, 8, 4, stride=6)
    master = bits(2001, 14, 2, stride=6)
    setpoint = gauge(2002, 0.1, stride=6, unit="°C")
    error_value1 = bits(2003, 0, 4, stride=6)
    error_value2 = bits(2003, 4, 5, stride=6)
    malfunction = bit(2003, 9, stride=6)
    warning = bit(2003, 10, stride=6)
    temperature = gauge(2004, 0.1, stride=6, unit="°C")
    sensor_error = bit(2005, 8, stride=6)
    sensor_received = bit(2005, 15, stride=6)

    @property
    def room_temperature(self) -> float | None:
        """Do not publish missing or faulty sensor readings as temperatures."""
        if not self.sensor_received or self.sensor_error:
            return None
        return self.temperature

    @property
    def error_code(self) -> str | None:
        """Decode §6, including its U4 example; value2=31 is undefined."""
        if self.error_value1 is None or self.error_value2 is None:
            return None
        if self.error_value2 == 31:
            return None
        return (
            "0ACEHFJLPU987654321GKMNRTVWXYZ*"[self.error_value2]
            + "0123456789ABCDEF"[self.error_value1]
        )
