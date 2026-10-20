# Domotec NUOS — Modbus (read only) for Home Assistant

A HACS custom integration for the Domotec NUOS hot-water heat pump. It connects
through a Modbus TCP gateway (developed against a Redisage/Spectra G13 at
`:1502`, NUOS on unit 1).

> **Status: development, not validated on the installed appliance.**
> No published register map exists for the installed **NUOS 400 B (VTC200,
> R134a)**. The only map available is for the newer **NUOS II (R290)**. Every
> mapped entity is therefore a *candidate*: it is **disabled by default** and
> labelled "(candidate)". Out of the box, the integration exposes exactly one
> enabled entity: *Holding register 8 raw (unverified)*. That is the single
> register already proven readable on site (raw 12). It is shown as a raw
> number, never as a temperature.

## Safety properties

- **Read only.** There are no number, switch, select, button or climate
  entities and no services. The only write path
  (`write_policy.async_guarded_write`) is inert: nothing calls it, and the
  only shipped profile (`read_only`) denies every register. Tests enforce all
  three points.
- **Never writes communication, RTC, defrost-type or fan-type registers**, even
  under a future profile.
- **Minimal gateway traffic.** Only enabled entities are polled (default:
  1 register every 120 s). Contiguous documented registers are coalesced, and a
  gap in the documented map is never bridged.
- **Only the configured unit id is ever addressed.** Other devices on the same
  gateway (for example a Dimplex heat pump on unit 2) are never touched.
- Rejected registers (exception "illegal data address") are isolated and stop
  being polled until reload. A gateway or link failure makes the entities
  unavailable, and they recover automatically.

## How it connects

The integration uses Home Assistant's official Modbus connection API,
**`homeassistant.components.modbus.async_get_unit`** (Home Assistant 2026.10+).
It does not use the deprecated `get_hub`, which breaks in 2027.10, and it does
not ship its own Modbus client.

- Home Assistant shares one connection per endpoint between integrations that
  use `async_get_unit`, and serialises their requests.
- The hold on that connection is released when the config entry unloads.
- The config flow uses `async_get_temporary_unit` for a single probe read of
  holding register 8.

**Gateway sessions.** These integrations each open their **own** TCP session to
the gateway, and those sessions are *not* shared with this one:
- Modbus YAML hubs (`modbus:` in `configuration.yaml`);
- custom integrations with their own pymodbus client (for example
  `dimplex_wpm`).

Installing this integration while the YAML pilot hub is still configured
therefore adds one more simultaneous session to the gateway. See
[docs/VALIDATION.md](docs/VALIDATION.md).

## Installation (HACS custom repository)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/SFF2101/nuos-modbus-hacs`
   with type **Integration**.
2. Install *Domotec NUOS (Modbus, read only)* and restart Home Assistant.
3. *Settings → Devices & services → Add integration → Domotec NUOS* and enter:
   - gateway host;
   - port (default 1502);
   - unit id (default 1);
   - model.

No YAML is needed.

### Options

| Option | Default | Meaning |
|---|---|---|
| Poll interval | 120 s | 30–3600 s |
| Datapoint register space | input (FC04) | Register space for the §10.5 ES1076 datapoints. **Unvalidated** — see below |
| Address correction | 0 | Applied to catalogue addresses only (not to the fixed holding‑8 diagnostic). **Unvalidated** |

## The open questions (deliberately not resolved in code)

1. **Map applicability.** The register tables come from the NUOS II manual
   (09/2026). The NUOS 400 manual (11/2023) documents only the Modbus wiring
   (CN11) and the service-menu settings: ID, baud rate, parity, and
   read/write vs read-only. It contains no register table.
2. **FC03 vs FC04.** The manual lists function codes 3, 4, 6 and 17, but does
   not say which table uses which.
   - The parameter table and the datapoint table claim the same addresses
     (for example 8) with different meanings, so they must be separate register
     spaces.
   - The inference is: parameters are holding registers (FC03/FC06) and
     datapoints are input registers (FC04).
   - Under that inference, the on-site FC03 address 8 = 12 would be
     *009.Start_HP_Hour = 12 h*, not tank temperature (T2 ×0.1 = 1.2 °C would
     be implausible).
3. **Address base.** The manual's "Modbus Adresse" is assumed to be the 0-based
   PDU address.

The full, cited catalogue is [docs/registers/modbus.yaml](docs/registers/modbus.yaml),
with its conventions in [docs/registers/README.md](docs/registers/README.md).
The on-site validation procedure is in [docs/VALIDATION.md](docs/VALIDATION.md).

## Development

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

The tests run a real Home Assistant (`pytest-homeassistant-custom-component`
pinned to HA 2026.10.2). The Modbus transport is the in-memory
`MockModbusConnection` from `modbus-connection`, swapped in underneath Home
Assistant's real `async_get_unit`. **No test talks to a real gateway or
appliance.**

Manufacturer manuals are not redistributed in this repository. They are
identified by title, revision and SHA-256 in the catalogue.
