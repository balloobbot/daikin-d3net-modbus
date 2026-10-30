# Daikin DIII-Net for Home Assistant

<p align="right">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=balloobbot&amp;repository=daikin-d3net-modbus&amp;category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open the repository in HACS">
  </a>
</p>

A Home Assistant custom integration for the Daikin EKMBDXB7V1 DIII-Net/Modbus adapter, built with `modbus-connection`.

The register map comes from Daikin's [EKMBDXB7V1 design guide, 4P642495-1A](docs/EKMBDXB-design-guide-4P642495-1A.pdf). See the [protocol reference](docs/protocol.md) for addresses and command sequencing, and the [document archive](docs/README.md) for related manuals.

## Features

- Discovers indoor groups 1-00 through 4-15 (64 addresses).
- Climate control for power, mode, temperature, fan speed and flap direction, according to each unit's capabilities.
- Auto fan and two-, three- or five-step speeds, when supported by the unit.
- Sensors for temperature, operating state, ASCII fault codes, subcodes and the affected unit number.
- Filter warning, forced-off, error, alarm and warning indicators.
- Filter reset button.
- Separate power switch, setpoint number and mode/fan/direction selects. These duplicate climate controls and are disabled by default. Enable them in entity settings if needed.

The adapter uses Modbus RTU over RS485. Connect it to a serial port on Home Assistant, a network serial proxy, or a Modbus TCP gateway. This version targets climate controls on EKMBDXB7V1. Ventilation, wall-controller locks, central forced-off commands and water-system controls are not implemented. Units with no supported climate modes are skipped. DTA116A51 and DCPA01 are not supported targets.

## Installation

Requires Home Assistant 2026.10.4 or later. No Modbus YAML configuration is needed.

1. Open this repository in HACS using the button at the top right, then download the integration. You can also add `https://github.com/balloobbot/daikin-d3net-modbus` as a custom **Integration** repository. For manual installation, copy `custom_components/daikin_d3net` into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add **Daikin DIII-Net (EKMBDXB7V1)** in Settings → Devices & services.
4. Choose **Modbus TCP** or **Serial port (Modbus RTU)**.
5. For TCP, enter the gateway's hostname or IP address and port (usually 502). For RTU, select a local or network serial port and set the baud rate and parity to match the adapter's DIP switches. The adapter uses eight data bits, with one stop bit for even/odd parity; no parity supports either one or two stop bits. Choose the matching no-parity option.
6. Enter the adapter's Modbus address (1–15).

A serial proxy carries RTU frames over the network and belongs under **Serial port (Modbus RTU)**. Choose **Modbus TCP** only for a gateway that converts between Modbus TCP and RTU. Existing RTU-over-TCP entries keep their connection settings.

Setup requires a ready adapter with at least one connected indoor unit. Reload the integration after adding or removing units. Commission the DIII-Net system using Daikin's installation instructions. Setup verifies communication, not the board model; confirm EKMBDXB7V1 on the adapter label.

### Upgrading from a DTA116A51 installation

Version 0.4.0 targets EKMBDXB7V1 and reads registers absent from the older DTA116A51 manual. Keep version 0.3.0 while using a DTA116A51. When replacing the adapter, remove its integration entry and configure the EKMBDXB7V1 with the new connection settings.

### Replacing the older integration

Both this integration and `martinstafford/daikin_d3net` use the `daikin_d3net` domain. Remove the old integration entry and custom-component directory before installing this one. Configure the adapter again, then update entity references in dashboards and automations. Device identifiers have changed, so existing entries cannot be migrated automatically.

## How controls work

State refreshes every 10 seconds from input registers. A disconnected indoor unit becomes unavailable while the others continue updating.

Holding registers contain commands for the same controls shown by the entities. Before changing a control, the integration reads the unit's three holding registers and compares them with fresh input status. It synchronizes affected registers when needed, preserves bits outside the control fields, then writes the command. Any read or write failure is reported to Home Assistant.

Writes to the same register are at least 0.51 seconds apart. Displayed state changes when the adapter reports it. Allow time for a command to appear before sending a conflicting one.

Temperature is the suction temperature, or the wall-controller temperature if configured on the Daikin system. Readings are used only while the adapter is ready and the unit is communicating. Temperature limits come from the unit's capabilities; Auto uses the overlap of its heating and cooling ranges. A cool/heat slave can change its setpoint but cannot change the system's heating/cooling mode.

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

The older integration is a cross-check for shared climate fields only. EKMBDXB7V1 discovery, fault reporting and writes follow its own design guide. The regression suite also covers signed temperatures, capability limits and command timing.

The integration has not been tested on physical hardware.
