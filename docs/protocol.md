# EKMBDXB7V1 protocol reference

Primary source: [Daikin design guide 4P642495-1A, February 2022](EKMBDXB-design-guide-4P642495-1A.pdf). Page numbers below are printed guide pages; add one for the PDF viewer. This is the public revision available to us, not confirmation of the latest firmware's capabilities. Daikin directs installers to its Business Portal for software releases (page 40).

## Address map

The adapter supports 64 DIII addresses, `1-00` through `4-15`. For zero-based indoor index `i`, the group address is `(i // 16 + 1)-(i % 16)`. Components receive the one-based index `i + 1`.

| Function | Manual reference | Zero-based wire address | Width | Guide page |
| --- | --- | --- | --- | --- |
| Readiness and other central controller | 30001 | 0 | 1 | 21 |
| Connected units, groups 1–4 | 30002–30005 | 1–4 | 4 | 21 |
| Communication errors, groups 1–4 | 30006–30009 | 5–8 | 4 | 21 |
| Climate capabilities | 31001 + 3i | 1000 + 3i | 3 | 22–23 |
| Power/fan, mode/filter, setpoint | 32001 + 6i | 2000 + 6i | 3 | 25–27 |
| Suction/controller temperature | 32005 + 6i | 2004 + 6i | 1 | 28 |
| ASCII fault code and detail | 33601 + 2i | 3600 + 2i | 2 | 31 |
| Climate commands | 42001 + 3i | 2000 + 3i | 3 | 33–35 |

Input registers report live state (FC04). Holding registers store commands (FC03 reads, FC16 writes). Both read functions are explicitly listed on page 10. Holding values are initialized at discovery and can become stale after wall-controller changes.

Each read is limited to 32 registers and writes to 30 (pages 11–13). The implementation reads only documented fields, merging adjacent addresses. In particular, it does not read the older DTA116A51 error word at `32004` or sensor flags at `32006`, which are absent from this guide.

## Capabilities and status

Climate capabilities describe supported modes, fan speeds, flap positions and signed eight-bit temperature limits. The limit words store the minimum in the high byte and maximum in the low byte.

Fan speeds depend on the capability value (pages 25 and 33):

| Capability | Supported command values |
| --- | --- |
| Fixed | 5: high |
| Two steps | 0: Auto, 1: low, 5: high |
| Three steps | 0: Auto, 1: low, 3: medium, 5: high |
| Five steps | 0: Auto, 1: very low, 2: low, 3: medium, 4: high, 5: very high |

The guide lists a four-step capability but gives no corresponding command mapping. The integration does not offer speed control for that value. Ventilation units use a separate fan encoding and are outside the current climate implementation; units without supported climate modes are skipped.

Setpoint and measured temperature are signed 16-bit values in tenths of a degree Celsius. The measured value is suction temperature unless the installer configures a controller sensor as described on page 28. There is no documented sensor-received flag in this map. Adapter readiness and per-unit communication status govern availability; the adapter can take up to ten minutes to detect a DIII communication failure.

Fault codes are two ASCII characters, high byte first. `0x4337` means `C7`; `0x3030` means no fault (`00`). Non-printable values are reported as unknown. The following word contains the affected unit number in bits 12–15, warning/alarm/error flags in bits 10/9/8, and a six-bit subcode. A subcode is meaningful only for codes that define one (page 31).

## Command sequencing

1. Read adapter communication status and the unit's live climate fields.
2. Validate capabilities, setpoint limits and cool/heat role before writing.
3. Skip unchanged commands. Otherwise read all three holding words and build baseline values from live status, preserving bits outside masks `0x77F1`, `0x00FF` and `0xFFFF`.
4. Synchronize affected holding words when they differ from live status, then write the requested changes. A command must change the stored value to trigger an operation after a wall-controller change (pages 16–19).
5. Wait at least 0.51 seconds between attempts to write the same register, including failed attempts. The guide requires more than 0.5 seconds.
6. Synchronize the mode before setting temperature. Cool/heat slaves use mode `6` for dependent setpoint control and cannot request a different system heating/cooling mode.
7. Pulse the filter-reset nibble to `15`, then clear it to `0`. If clearing fails or is cancelled, retry the pending clear during the next poll or command (page 34).

The upper byte of command register `42002` is reserved in this guide. The integration preserves it and does not write the older DTA116A51 Auto heating/cooling selector there. Auto setpoints use the intersection of the unit's heating and cooling limits.

The fan-control nibble is `6` when the unit has fan-speed or direction control, otherwise `0` (pages 33–34). The connection has 25 ms message spacing and a 10-second timeout. Each unit serializes its full command sequence; Home Assistant owns and shares the underlying connection through `modbus-connection`.

State refreshes from input registers every ten seconds. A write acknowledgement does not update displayed state. Failed commands are not automatically repeated, since the adapter may have accepted a write whose response was lost.

## Connection and scope

EKMBDXB7V1 uses RS485 Modbus RTU at 9600 or 19200 baud, with a DIP-switch address of 1–15. Even/odd parity uses one stop bit; no parity supports one or two (page 10). Setup offers a serial port, including a serial proxy, or a Modbus TCP gateway that converts TCP to RTU.

The current implementation covers climate controls and diagnostics. The guide also documents ventilation, controller locks, central forced-off and water-system functions; these are not implemented. Controller locks and central forced-off are available only when no other central DIII device is detected (pages 20, 32 and 38). No compatibility with DTA116A51 or DCPA01 is inferred from shared addresses.

Daikin limits control commands to 7,000 per unit per year (page 4). Unchanged commands are skipped, but this limit is not counted or enforced.

Hardware validation and Daikin's current firmware-specific specification are still needed. The older integration is used only to cross-check shared climate decoding, not to define EKMBDXB7V1 behavior.
