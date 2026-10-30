"""Compare common wire fixtures with an explicitly supplied upstream checkout.

Run with: uv run python tools/compare_reference.py ../daikin_d3net
No upstream source is copied into this repository. The fixed, inspected revision
is extracted to a temporary package and used only as a regression reference.
"""

import asyncio
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from modbus_connection.mock import MockModbusConnection

# This script works from a checkout without installing the integration.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.daikin_d3net.device.models import Capabilities, IndoorStatus  # noqa: E402

REFERENCE = "92ae9ab46c6ce6d737f1bfb7af6fd128983cbe2a"


async def compare(reference):
    unit = MockModbusConnection().for_unit(1)
    status_words = [0x5201, 0x8202, 225, 0x294, 234, 0x8000]
    caps_words = [0xBD1F, 0x1020, 0x0A1E]
    unit.input.update({1000: caps_words, 2000: status_words})
    current = IndoorStatus(unit)
    caps = Capabilities(unit)
    await current.async_update()
    await caps.async_update()
    old = reference.UnitStatus(status_words.copy())
    old_caps = reference.UnitCapability(caps_words.copy())
    pairs = {
        "power": (current.power, old.power),
        "mode": (current.mode, old.operating_mode.value),
        "fan_speed": (current.fan_speed, old.fan_speed.value),
        "direction": (current.direction, old.fan_direct.value),
        "setpoint": (current.setpoint, old.temp_setpoint),
        "temperature": (current.temperature, old.temp_current),
        "cooling_limits": (
            caps.temperature_limits(2),
            (old_caps.cool_setpoint_lowerlimit, old_caps.cool_setpoint_upperlimit),
        ),
    }
    assert all(new == old for new, old in pairs.values()), pairs
    negative_words = [0x5201, 0x8202, 0xFFF6, 0, 0xFF85, 0x8000]
    unit.input[2000] = negative_words
    await current.async_update()
    negative_old = reference.UnitStatus(negative_words.copy())
    try:
        _ = old_caps.heat_setpoint_lowerlimit
    except IndexError:
        heating_result = "IndexError: sign bit reads beyond the capability block"
    else:
        raise AssertionError("Expected the reference decoder bounds error")
    result = {
        "reference": REFERENCE,
        "matching_fields": sorted(pairs),
        "heating_limit_correction": {
            "manual_and_new": caps.temperature_limits(1),
            "reference": heating_result,
        },
        "intentional_signed_temperature_correction": {
            "setpoint": {
                "manual_and_new": current.setpoint,
                "reference": negative_old.temp_setpoint,
            },
            "room": {
                "manual_and_new": current.temperature,
                "reference": negative_old.temp_current,
            },
        },
    }
    assert current.setpoint == -1.0 and current.temperature == -12.3
    print(json.dumps(result, indent=2))


def main():
    checkout = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary) / "reference_d3net"
        package.mkdir()
        (package / "__init__.py").touch()
        for name in ("const.py", "encoding.py"):
            source = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "show",
                    f"{REFERENCE}:custom_components/daikin_d3net/d3net/{name}",
                ]
            )
            (package / name).write_bytes(source)
        sys.path.insert(0, temporary)
        reference = importlib.import_module("reference_d3net.encoding")
        asyncio.run(compare(reference))


if __name__ == "__main__":
    main()
