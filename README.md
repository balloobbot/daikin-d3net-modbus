# Daikin DIII-Net for Home Assistant

<p align="right">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=balloobbot&amp;repository=daikin-d3net-modbus&amp;category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open the repository in HACS">
  </a>
</p>

A Home Assistant custom integration for the Daikin DTA116A51 and EKMBDXB7V1 DIII-Net/Modbus adapters, built with `modbus-connection`.

Setup asks which adapter you have. Each profile follows its own manual: [DTA116A51 engineering manual](docs/EDMT721419-DTA116A51.pdf) or [EKMBDXB7V1 design guide](docs/EKMBDXB-design-guide-4P642495-1A.pdf). See the [protocol reference](docs/protocol.md) for addresses and command sequencing, and the [document archive](docs/README.md) for related manuals.

## Features

- Discovers indoor units within the selected adapter's address range.
- Climate control for power, mode, temperature, fan speed and flap direction, according to each unit's capabilities.
- Fan speeds and flap positions follow both the adapter profile and the indoor unit's capabilities.
- Temperature, operating state and fault sensors.
- Filter warning, forced-off and fault indicators.
- Filter reset button.
- Separate power switch, setpoint number and mode/fan/direction selects. These duplicate climate controls and are disabled by default. Enable them in entity settings if needed.

| Adapter | DIII addresses | Fan controls | Additional diagnostics |
| --- | --- | --- | --- |
| DTA116A51 | 1-00 through 1-15 (16) | Fixed, two- or three-step | Encoded fault code and temperature-sensor fault |
| EKMBDXB7V1 | 1-00 through 4-15 (64) | Fixed, two-, three- or five-step; Auto on variable-speed units | ASCII fault code, subcode, affected unit number and alarm |

Both adapters use Modbus RTU over RS485. Connect through a serial port, network serial proxy or Modbus TCP gateway. Ventilation, wall-controller locks, central forced-off commands and water-system controls are not implemented. Units with no supported climate modes are skipped. DCPA01 is not supported.

## Installation

Requires Home Assistant 2026.10.4 or later. No Modbus YAML configuration is needed.

1. Open this repository in HACS using the button at the top right, then download the integration. You can also add `https://github.com/balloobbot/daikin-d3net-modbus` as a custom **Integration** repository. For manual installation, copy `custom_components/daikin_d3net` into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.
3. Add **Daikin DIII-Net** in Settings → Devices & services.
4. Choose **Modbus TCP** or **Serial port (Modbus RTU)**.
5. For TCP, enter the gateway's hostname or IP address and port (usually 502). For RTU, select a local or network serial port and set the baud rate and parity to match the adapter's DIP switches. The adapter uses eight data bits, with one stop bit for even/odd parity; no parity uses two stop bits on DTA116A51, or one or two on EKMBDXB7V1. Choose the matching no-parity option.
6. Select **DTA116A51** or **EKMBDXB7V1** from the adapter label and enter its Modbus address (1–15).

A serial proxy carries RTU frames over the network and belongs under **Serial port (Modbus RTU)**. Choose **Modbus TCP** only for a gateway that converts between Modbus TCP and RTU. Existing RTU-over-TCP entries keep their connection settings.

Setup requires a ready adapter with at least one connected indoor unit. Reload the integration after adding or removing units. Commission the DIII-Net system using Daikin's installation instructions. Setup verifies communication, not the board model; select the model from the adapter label. A successful read does not identify the model, and the integration does not switch profiles automatically.

### Upgrading an existing installation

Versions before 0.5.0 did not store an adapter model. After updating, open the integration's menu in Settings → Devices & services and choose **Reconfigure** to select it. Setup waits for this choice before reading registers. Both older DTA116A51 entries and EKMBDXB7V1 entries need this one-time selection.

You can also use **Reconfigure** when changing boards. It checks the selected profile before saving, keeps connection settings and shared entity IDs, and removes diagnostics or addresses that the new profile does not support. Serial entries also let you adjust parity to match the board.

### Replacing the older integration

Both this integration and `martinstafford/daikin_d3net` use the `daikin_d3net` domain. Remove the old integration entry and custom-component directory before installing this one. Configure the adapter again, then update entity references in dashboards and automations. Device identifiers have changed, so existing entries cannot be migrated automatically.

## How controls work

State refreshes every 10 seconds from input registers. A disconnected indoor unit becomes unavailable while the others continue updating.

Holding registers contain commands for the same controls shown by the entities. Before changing a control, the integration reads the unit's three holding registers and compares them with fresh input status. It synchronizes affected registers when needed, preserves bits outside the control fields, then writes the command. Any read or write failure is reported to Home Assistant. FC03 holding reads are documented for EKMBDXB7V1. The DTA116A51 manual omits FC03; its profile retains the reads used by the original integration. A failed read aborts the command, with no fallback.

Writes to the same register are at least 0.51 seconds apart. Displayed state changes when the adapter reports it. Allow time for a command to appear before sending a conflicting one.

Temperature is the suction temperature, or the wall-controller temperature if configured on the Daikin system. Readings are used only while the adapter is ready and the unit is communicating. DTA116A51 additionally checks its sensor-validity flags. Temperature limits come from the unit's capabilities. For Auto setpoints, DTA116A51 requires an active heating/cooling operation; EKMBDXB7V1 uses the overlap of both ranges. A cool/heat slave can change its setpoint but cannot change the system's heating/cooling mode.

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

The older integration is a cross-check for shared climate fields only. Each adapter's discovery, fault reporting and writes follow its own manual. The regression suite also covers signed temperatures, capability limits and command timing.

The integration has not been tested on physical hardware.
