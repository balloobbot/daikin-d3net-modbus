# Daikin DIII-Net for Home Assistant

A new custom integration for the **Daikin DTA116A51 DIII-Net/Modbus adapter**, implemented from Daikin engineering manual **EDMT721419 / CB13A033**. It uses `modbus-connection` and Home Assistant's shared Modbus connection API.

The [engineering manual](docs/EDMT721419-DTA116A51.pdf) is included in this repository. See the [register and command reference](docs/protocol.md) for implementation details and page references.

## Supported functions

- Discover indoor groups **1-00 through 1-15** from the adapter's connection bitmap.
- Climate control: power, cooling, heating, fan-only, dry, Auto, temperature, fan speed and flap direction, according to each unit's capabilities.
- Temperature, operating state and decoded error-code sensors.
- Filter warning, forced-off, malfunction, warning and temperature-sensor fault indicators.
- Filter reset with an explicit reset-pulse clear.
- Separate power switch, setpoint number, and mode/fan/direction selects. These duplicate climate controls and are disabled by default; enable them in the entity settings if needed.

Supports a **Modbus TCP gateway** or an **RTU-over-TCP bridge** in front of the adapter. The adapter itself speaks serial Modbus RTU. Configure the bridge's physical serial settings to match the adapter's DIP switches.

This implementation targets the DTA116A51 manual. It does not claim support for the 64-unit EKMBDXB model, DCPA01, or hot-water functions.

## Installation

Requires **Home Assistant 2026.10.4 or later**. Home Assistant's `modbus` integration provides the backend and its compatible library dependencies; no Modbus YAML configuration is needed.

1. Add `https://github.com/balloobbot/daikin-d3net-modbus` as a custom **Integration** repository in HACS, then install it. Alternatively, copy `custom_components/daikin_d3net` into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add **Daikin DIII-Net (DTA116A51)** in Settings → Devices & services.
4. Enter the gateway host/port, connection type, and the adapter's Modbus address (1–15).

After installing the custom integration and restarting Home Assistant, use this button to open its setup flow:

[![Add the integration to your Home Assistant instance.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=daikin_d3net)

Configuration performs read-only discovery before creating an entry. An unready adapter or an installation without a communicating indoor unit cannot complete setup. Home Assistant retries failed startup reads automatically.

### Replacing the older custom integration

This is a fresh implementation, not an in-place upgrade of `martinstafford/daikin_d3net`. Both use the `daikin_d3net` domain, so they cannot be installed together. Remove the old integration entry and old custom-component directory before installing this one. Configure the adapter again and update entity references in dashboards and automations. Device identifiers now use the gateway endpoint, Modbus address and indoor group, rather than a display name.

## Polling and commands

Status refreshes every 10 seconds. A disconnected indoor unit becomes unavailable while other units continue updating. Connections are shared and released by Home Assistant; the integration does not close the socket after every poll.

Commands use fresh input status to synchronize affected holding words before changing them. Writes to the same register are separated by at least 0.51 seconds. No-op commands produce no writes. All Modbus exception responses propagate to Home Assistant.

Entity state follows device readback. A write acknowledgement does not immediately change the displayed state; propagation through DIII-Net can take time. Status polling continues during that period. Avoid sending rapid conflicting commands before the previous change appears in the unit's status.

Temperature readings remain unknown until the adapter reports valid sensor data. Cooling/heating limits come from the capability registers. Auto-mode temperature changes require a reported heating or cooling operation. A cool/heat slave cannot change the system's heating/cooling mode; setpoint writes use the documented dependent-mode command.

Daikin specifies a limit of **7,000 control commands per indoor unit per year**. This integration does not persist or enforce an annual command budget. Avoid automation that repeatedly changes controls. Synchronization can itself send commands when the holding value changes.

Adding or removing indoor units requires reloading the integration. Adapter EEPROM settings and DIII master/start configuration remain installer responsibilities.

## Development and verification

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests use `modbus-connection`'s mock backend and the real Home Assistant custom-integration test harness. The locked environment matches Home Assistant 2026.10.4's Modbus dependencies.

The device implementation under `custom_components/daikin_d3net/device` contains no Home Assistant imports. It consumes a caller-owned `ModbusUnit`, declares typed `Component` register maps, and returns `UpdateReport` for partial failures. It is bundled with this custom integration; no separate PyPI publication is required.

The older integration was used only as a secondary comparison after implementing the manual's register map. An optional script compares common register fixtures with its original decoder at a fixed revision:

```sh
uv run python tools/compare_reference.py /path/to/daikin_d3net-checkout
```

The comparison covers ordinary power, modes, fan controls, temperature and limits. Intentional differences include signed-integer correction, temperature validity, the documented 16-unit map, error decoding from input status, no FC03 reads, and register write timing. The manual takes precedence over the reference implementation.

**Hardware validation is still required.** Tests validate protocol encoding, sequencing, failures and Home Assistant behavior; they do not establish behavior on a physical DTA116A51 installation.
