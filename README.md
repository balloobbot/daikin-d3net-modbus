# Daikin DIII-Net for Home Assistant

<p align="right">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=balloobbot&amp;repository=daikin-d3net-modbus&amp;category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open the repository in HACS">
  </a>
</p>

A Home Assistant custom integration for the Daikin DTA116A51 DIII-Net/Modbus adapter, built with `modbus-connection`.

The register map comes from Daikin's [EDMT721419 engineering manual](docs/EDMT721419-DTA116A51.pdf). Command preparation also reads holding registers, as the older integration does. The DTA116A51 manual omits this read function (FC03); hardware testing is still needed. See the [protocol reference](docs/protocol.md) for addresses and command sequencing.

## Features

- Discovers indoor groups 1-00 through 1-15.
- Climate control for power, mode, temperature, fan speed and flap direction, according to each unit's capabilities.
- Sensors for room temperature, operating state, error codes, filter warning and faults.
- Filter reset button.
- Separate power switch, setpoint number and mode/fan/direction selects. These duplicate climate controls and are disabled by default. Enable them in entity settings if needed.

The adapter uses Modbus RTU over RS485. Connect it to a serial port on Home Assistant, a network serial proxy, or a Modbus TCP gateway. The 64-unit EKMBDXB model, DCPA01 and hot-water functions are outside the current scope.

## Installation

Requires Home Assistant 2026.10.4 or later. No Modbus YAML configuration is needed.

1. Open this repository in HACS using the button at the top right, then download the integration. You can also add `https://github.com/balloobbot/daikin-d3net-modbus` as a custom **Integration** repository. For manual installation, copy `custom_components/daikin_d3net` into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add **Daikin DIII-Net (DTA116A51)** in Settings → Devices & services.
4. Choose **Modbus TCP** or **Serial port (Modbus RTU)**.
5. For TCP, enter the gateway's hostname or IP address and port (usually 502). For RTU, select a local or network serial port and set the baud rate and parity to match the adapter's DIP switches. The adapter uses eight data bits, with one stop bit for even/odd parity or two for no parity.
6. Enter the adapter's Modbus address (1–15).

A serial proxy carries RTU frames over the network and belongs under **Serial port (Modbus RTU)**. Choose **Modbus TCP** only for a gateway that converts between Modbus TCP and RTU. Existing RTU-over-TCP entries keep their connection settings.

Setup requires a ready adapter with at least one connected indoor unit. Reload the integration after adding or removing units. Configure adapter EEPROM settings and DIII master/start settings using the installer's tools.

### Replacing the older integration

Both this integration and `martinstafford/daikin_d3net` use the `daikin_d3net` domain. Remove the old integration entry and custom-component directory before installing this one. Configure the adapter again, then update entity references in dashboards and automations. Device identifiers have changed, so existing entries cannot be migrated automatically.

## How controls work

State refreshes every 10 seconds from input registers. A disconnected indoor unit becomes unavailable while the others continue updating.

Holding registers contain commands for the same controls shown by the entities. Before changing a control, the integration reads the unit's three holding registers and compares them with fresh input status. It synchronizes affected registers when needed, preserves bits outside the control fields, then writes the command. Any read or write failure is reported to Home Assistant.

Writes to the same register are at least 0.51 seconds apart. Displayed state changes when the adapter reports it. Allow time for a command to appear before sending a conflicting one.

Temperature readings stay unknown until the adapter reports valid sensor data. Temperature limits come from the unit's capabilities. Auto-mode temperature changes require a reported heating or cooling operation. A cool/heat slave can change its setpoint but cannot change the system's heating/cooling mode.

Daikin specifies a limit of 7,000 control commands per indoor unit per year. The integration skips unchanged commands and unnecessary synchronization writes, but does not count or enforce this limit. Avoid automations that repeatedly change controls.

## Development

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests use the `modbus-connection` mock backend and Home Assistant's custom-integration test harness. The locked dependencies match Home Assistant 2026.10.4. The device code in `custom_components/daikin_d3net/device` is bundled with the integration and has no Home Assistant imports.

To compare register decoding with the original `martinstafford/daikin_d3net` at a fixed revision:

```sh
uv run python tools/compare_reference.py /path/to/daikin_d3net-checkout
```

Common power, mode, fan and temperature values agree. This implementation fixes signed temperatures and heating-limit decoding, checks sensor validity, and applies the DTA116A51's 16-unit map and register write timing.

The integration has not been tested on physical hardware.
