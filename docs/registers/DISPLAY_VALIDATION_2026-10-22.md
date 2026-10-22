# Display validation, 2026-10-22 (DAI-IN-639 / DAI-IN-640)

The owner photographed the NUOS 400 B (VTC200, software **VT 15**) display between
18:28 and 18:42 CEST. Home Assistant's read-only values for the same minutes were
compared with each screen: **31 comparisons, 0 mismatches**. Photos are kept with
the owner and the Dual AI Mailbox record DAI-OUT-639; none are published here.

Address map and register spaces confirmed: parameters are holding registers (FC03),
datapoints are input registers (FC04), manual address = PDU address.

## Codes with display text (implemented as the `display_text` attribute)

| Register | Space / address | Raw | Display showed |
|---|---|---|---|
| wp_ls (fan speed in operation) | holding 15 | 1 | FanSpeed **High** (fan type AC) |
| fan_pause | holding 23 | 2 | FanPause **30m/30s** |
| language | holding 25 | 0 | Language **English** |
| defrost_type | holding 26 | 1 | Defrost **Gas** |
| status_bits | input 16 | 2 | InfoMode **Standby** |

The entity state stays the raw value. Only these codes have text; every other
raw value has `display_text: null`. The first four agree with the manufacturer
tables. Status 2 = Standby has display evidence only, because the manual has no
bit table. Status 4 (compressor running) was never photographed, so it is not
mapped.

## Other screens that matched (no code change needed)

T water 55 °C ↔ input 8 = 54.5 °C; T evapor 11 °C ↔ input 7 = 11.1–11.5 °C;
Tset DHW 55, T min 45, T2 min 10, T max 55, T.PV_WP 52, T.PV_EL 53 (holding 4, 5,
6, 28, 18, 19); Timer Off (7 = 0); WorkMode HP+EL (12 = 3); T.Legio Off (13 = 0);
VentMode Off (16 = 0); PV Mode Off (17 = 0); Holiday Off (20 = 0); Abs.Days 1
(21 = 1); Boost Off (22 = 0); Anode On (27 = 1); Fan type AC (29 = 0); LegiDays 7
(33 = 7); Modbus ID 1, BR 19K2, Par Even, RD&WR (114–117); ReDays 0 (input 17);
Message 0 0 0 (input 18 = 0); Software VT 15 (input 119 = 15, so the raw value
is the VT number and the catalogue's "decimals 1" does not apply).

The two panel LEDs were lit even while the compressor was off (smart plug 1.4 W),
so they do not indicate running state.

## Not covered

Clock/date, timer start/stop times, T min RL, T3, relays other than in standby,
EC fan levels and the 0–10 V output were not shown on the display.
