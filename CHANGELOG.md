# Changelog

## 0.1.1 — display texts validated on site (DAI-IN-640)

- New `display_text` attribute for five registers, limited to the codes seen on the
  unit's own display on 2026-10-22: fan speed 1 = High, fan pause 2 = 30m/30s,
  language 0 = English, defrost 1 = Gas, status 2 = Standby. Other codes give
  `null`. Entity states stay raw; no unit, statistics, entity id or unique id change.
- `docs/registers/DISPLAY_VALIDATION_2026-10-22.md`: 31 display/register
  comparisons, 0 mismatches.
- Still read only: no write path added.

## 0.1.0 — initial development release (not validated on site)

- Read-only integration on Home Assistant's `modbus.async_get_unit` (HA 2026.10+).
- One enabled raw diagnostic (FC03 holding 8); 56 candidate entities from the NUOS II
  manual, all disabled by default.
- Cited register catalogue `docs/registers/modbus.yaml` (56 documented addresses, 0 validated).
- Inert, default-deny write guard; no write entities or services.
