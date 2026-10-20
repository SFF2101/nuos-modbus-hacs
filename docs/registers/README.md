# Register catalogue conventions

`modbus.yaml` in this folder is **development provenance**, not Home Assistant
configuration. It records:
- every register the manufacturer documents, cited to manual, revision and page;
- what is known about each register;
- what is not known about each register;
- what has been validated on the installed appliance.

## Sources reviewed

| Source | Modbus content | Status |
|---|---|---|
| Domotec *8.6 NUOS II 300 & 400*, 09/2026, pp. 32–36 | §10.4 parameter table, RTC, communication; §10.5 ES1076 datapoints and protocol | Fully reviewed. **Only register source.** Applies to the NUOS II (R290) |
| Domotec *NUOS 400*, 11/2023, all 49 pages | p.24 CN11 wiring (B = port 3, A = port 4); p.34 menu: ID 1-247, BR 19K2/9K6, parity, RD&WR/Only RD | Fully reviewed. **No register table, function codes or scaling** |
| Redisage G13 web-configuration page | Gateway configuration only | No NUOS registers; no stated concurrent-client limit |
| NUOS-EXTRA manual | — | Excluded (different product) |

Manuals are identified by SHA-256 in `modbus.yaml` and are not redistributed.

## Counts

| Table (manual) | Registers |
|---|---|
| §10.4 parameters 005–034 (addresses 4–23, 25–33) | 29 |
| §10.4 RTC 104–110 (addresses 103–109) | 7 |
| §10.4 communication 115–118 (addresses 114–117) | 4 |
| §10.5 ES1076 datapoints | 16 |
| **Total documented addresses** | **56** (57 table rows; 016.WP_LS has AC and EC variants) |
| Semantics validated on the installed NUOS 400 B | **0** |
| Read successfully on site, semantics unvalidated | 1 (FC03 address 8 → raw 12) |

Undocumented addresses — for example 0–3 and 24 in the parameter space — are
never read and must not be scanned.

## Field meanings

- **address**: the manual's *Modbus Adresse*. For §10.4 it equals the display
  number − 1. It is assumed to be the 0-based PDU address, i.e. Home
  Assistant's `address`. This is **unverified**.
- **space / fc_read**: the candidate register space.
  - §10.4: `holding` / FC03.
  - §10.5: `input` / FC04.
  - This is an **inference**. The manual lists FC 3, 4, 6 and 17 without saying
    which table uses which. The basis for the inference is that the two tables
    overlap in address (e.g. 8), so they must be distinct spaces, and that
    parameters are writable (FC06).
- **fc_write**: `6` where the source implies a writable parameter. The
  integration **never** writes. See `write_policy.py`.
- **type**: 16-bit. The source never states signedness. Temperature datapoints
  are decoded as int16, an assumption made because evaporator temperatures can
  be below zero.
- **decimals / offset**: the manual's *Dezimal* / *Offset* columns. Value =
  raw / 10^decimals.
  - Entries whose columns are inconsistent are exposed **raw only**:
    026.Sprache has Dezimal 2 / Offset 2, and DA0 is printed with Dezimal 0
    yet says "1000 = 10 V".
- **enum**: printed value → label. Where the print is defective it is
  reproduced under `enum_as_printed`, with a separately labelled
  `enum_probable`. Example: 024.VenPause lists "1 =" six times.
- **bitfield**: `unknown` for *Status* and *Unit_Alarm*. The manual gives no bit
  table. Related display texts are recorded, but no mapping is invented.
- **sentinel**: no null or sentinel values are documented. None are applied.
- **validation**:
  - `not_validated` — documented only;
  - `read_ok_semantics_unvalidated` — read on site, meaning unconfirmed;
  - `validated` — confirmed against an independent on-site reference.
- **ha.enabled_default**: `false` for every catalogue entry. Only the pilot
  diagnostic (raw holding 8) is enabled.

## Source anomalies (reproduced, not corrected)

- 016.WP_LS: two rows on address 15 (AC 0–1, EC 0–3).
- 017.KWL: max 2 but enumeration 0–3; display id printed "0.17".
- 024.VenPause: enumeration printed "1 =" for values 1–6.
- 026.Sprache: Dezimal 2 / Offset 2 on an enumeration; max 10 but 12 languages.
- 027.Abtauart: "Bitte nicht verändern!" (do not change). Write-forbidden.
- 118.Modbus Allow Write: only value 1 described.
- RTC: unit, range and encoding not printed. "Tag" vs "Datum" is ambiguous.
- Datapoints: Relay5 is absent. DA0 scale conflicts with the Dezimal column.
  T3 location is not described. FW_Version is marked "Binär" with Dezimal 1.
