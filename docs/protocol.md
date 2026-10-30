# DTA116A51 protocol reference

Primary source: [Daikin EDMT721419 engineering manual](EDMT721419-DTA116A51.pdf), containing functional specification CB13A033. Page references below are the functional specification's internal page numbers. Add 16 for the manual's printed page, or 18 for the PDF viewer's one-based page number.

Original source: [Daikin Comfort engineering manual](https://daikincomfort.com/docs/default-source/general/vrv/em-edmt721419.pdf).

The bundled PDF is an unmodified Daikin document. Its copyright remains with Daikin. The repository's software license does not apply to the PDF.

SHA-256: `bcef452141a2a02822d9868be33c2267dab75ff6108b5925ac7b40f1b06882c8`.

## Address map

For indoor index `i` from 0 through 15, group address is `1-ii`. The library's component index is one-based, so components receive `index=i+1`.

| Function | Manual reference | Zero-based wire address | Width | Specification page |
|---|---|---|---|---|
| Adapter readiness | 30001 | 0 | 1 | 15 |
| Connected units | 30002 | 1 | 1 | 16 |
| Communication errors | 30006 | 5 | 1 | 17 |
| Unit capabilities | 31001 + 3i | 1000 + 3i | 3 | 18–19 |
| Unit status | 32001 + 6i | 2000 + 6i | 6 | 20–23 |
| Unit commands | 42001 + 3i | 2000 + 3i | 3 | 25–27 |
| Adapter EEPROM settings | 40001 | 0, holding space | 1 | 24; not modified |

Input and holding addresses refer to different tables. Status reads use FC04. The adapter lists only FC04, FC06 and FC16; there is no FC03 holding-register read. This implementation sends FC16 commands, including single-word commands. Each read is limited to 32 registers and each write is below the 30-register limit (pages 4–6). Adjacent documented fields are pooled; reserved gaps between adapter status words are not read.

## Status and capabilities

Capability bitfields describe mode support, fan direction steps, fan speed steps, and signed eight-bit minimum/maximum temperatures. In the temperature-limit words, the low byte is the maximum and the high byte is the minimum (pages 18–19).

Status words expose power and forced-off bits; flap and fan values; requested mode; filter indication; current operation; and cool/heat master status. The master field occupies bits 14–15 of the second status word (pages 20–21).

Setpoint and room temperature are signed 16-bit integers in tenths of a degree Celsius. The sixth status word marks sensor error at bit 8 and data received at bit 15. A temperature is usable only after receipt and without the error flag (pages 21–23).

The fourth status word contains error mapping value 1 at bits 0–3 and value 2 at bits 4–8, plus malfunction and warning at bits 9 and 10. The table on page 31 maps these to error codes; value 1=4 and value 2=9 means `U4`. Value 2=31 has no defined code, so it returns unknown. No separate error register block is read.

## Command sequencing

1. Read adapter communication status and the unit's six input status words.
2. Validate capability support, temperatures and cool/heat role before any write.
3. Derive baseline control words from input status using only documented command bits.
4. Write the baseline for each affected register before writing a changed value. This handles changes made by a wall controller (pages 10 and 28–30).
5. Wait more than 0.5 seconds before writing the same register again (page 28). The implementation uses 0.51 seconds after completion of the preceding attempt, including failed attempts.
6. For a temperature command, synchronize the mode/operation register before changing the temperature register (page 27).
7. For filter reset, write reset nibble `15`, then clear it to `0`. If clearing fails or a request is cancelled, retain a pending clear and retry during a later poll or command (page 26).

The device requests 25 ms of message spacing from `ModbusUnit`, covering the 9600-baud silence interval plus response processing margin on page 8. The connection backend serializes Modbus requests; each indoor unit also has a lock around its complete control sequence.

The fan-control nibble must equal `6`. Fan speed is zero when the unit has no fan-speed capability. Fixed, two-step and three-step speeds are handled as specified; Auto fan speed and four/five-step fan speeds are not advertised by this manual (pages 18, 20 and 25).

For an Auto-mode temperature change, bits 8–11 of the command mode word select heating (`1`) or cooling (`2`). If current operation cannot select either, the command fails with a useful error. Cool/heat slaves use command mode `6` for setpoint control and cannot request a different heating/cooling system mode (page 26).

## Implementation choices

Synchronization happens before user commands. Routine polls do not write control registers. No-op commands are skipped. These choices reduce unnecessary commands while retaining the synchronization-before-change sequence.

Polling does not suppress live measurements after writes or invent optimistic state. Physical propagation delay remains visible until the adapter reports the new value. Unconfirmed commands are not automatically retried; a lost reply cannot prove whether a command reached the indoor unit.

The device code is bundled in the custom integration, as allowed by the [modbus-connection integration guide](https://home-assistant-libs.github.io/modbus-connection/home-assistant/integration/). Home Assistant owns connections through `async_get_unit` and `async_get_temporary_unit`. Packed-field write helpers are deliberately unused because their read-modify-write operation requires FC03.
