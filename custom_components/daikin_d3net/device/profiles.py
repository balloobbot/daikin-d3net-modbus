"""Adapter-specific register layouts and controls."""

from dataclasses import dataclass
from enum import StrEnum

from modbus_connection.model import bit, bits, raw_register

from .models import (
    AdapterStatus,
    Capabilities,
    FaultStatus,
    IndoorStatus,
    InputComponent,
)


class Board(StrEnum):
    DTA116A51 = "DTA116A51"
    EKMBDXB7V1 = "EKMBDXB7V1"


class DtaAdapterStatus(InputComponent):
    """DTA116A51 ready flag and 16-unit bitmaps (CB13A033 §4-1)."""

    ready = bit(0, 0)
    connected = raw_register(1)
    communication_errors = raw_register(5)


class DtaCapabilities(Capabilities):
    """DTA116A51 fan mappings (CB13A033 §4-1-4)."""

    @property
    def fan_speeds(self) -> tuple[int, ...]:
        if not self.fan_speed:
            return ()
        return {1: (5,), 2: (1, 5), 3: (1, 3, 5)}.get(self.fan_steps, ())

    @property
    def fan_names(self) -> dict[int, str]:
        return {1: "low", 3: "medium", 5: "high"}


class DtaIndoorStatus(IndoorStatus):
    """DTA116A51 fault encoding and sensor flags (CB13A033 §4-1-5)."""

    error_value1 = bits(2003, 0, 4, stride=6)
    error_value2 = bits(2003, 4, 5, stride=6)
    malfunction = bit(2003, 9, stride=6)
    warning = bit(2003, 10, stride=6)
    sensor_error = bit(2005, 8, stride=6)
    sensor_received = bit(2005, 15, stride=6)

    @property
    def room_temperature(self) -> float | None:
        if not self.sensor_received or self.sensor_error:
            return None
        return self.temperature

    @property
    def error_code(self) -> str | None:
        if (
            self.error_value1 is None
            or self.error_value2 is None
            or self.error_value2 == 31
        ):
            return None
        return (
            "0ACEHFJLPU987654321GKMNRTVWXYZ*"[self.error_value2]
            + "0123456789ABCDEF"[self.error_value1]
        )


@dataclass(frozen=True)
class AdapterProfile:
    model: Board
    unit_count: int
    adapter_type: type[InputComponent]
    capabilities_type: type[Capabilities]
    status_type: type[IndoorStatus]
    fault_type: type[FaultStatus] | None
    auto_operation_selector: bool
    mode_mask: int
    sensor_keys: tuple[str, ...]
    binary_sensor_keys: tuple[str, ...]


PROFILES = {
    Board.DTA116A51: AdapterProfile(
        model=Board.DTA116A51,
        unit_count=16,
        adapter_type=DtaAdapterStatus,
        capabilities_type=DtaCapabilities,
        status_type=DtaIndoorStatus,
        fault_type=None,
        auto_operation_selector=True,
        mode_mask=0x0FFF,
        sensor_keys=("temperature", "state", "error_code"),
        binary_sensor_keys=(
            "filter_sign",
            "forced_off",
            "malfunction",
            "warning",
            "sensor_error",
        ),
    ),
    Board.EKMBDXB7V1: AdapterProfile(
        model=Board.EKMBDXB7V1,
        unit_count=64,
        adapter_type=AdapterStatus,
        capabilities_type=Capabilities,
        status_type=IndoorStatus,
        fault_type=FaultStatus,
        auto_operation_selector=False,
        mode_mask=0x00FF,
        sensor_keys=(
            "temperature",
            "state",
            "error_code",
            "error_subcode",
            "error_unit",
        ),
        binary_sensor_keys=(
            "filter_sign",
            "forced_off",
            "malfunction",
            "warning",
            "alarm",
        ),
    ),
}
