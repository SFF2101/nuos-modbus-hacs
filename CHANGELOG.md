# Changelog

## 0.1.0 — initial development release (not validated on site)

- Read-only integration on Home Assistant's `modbus.async_get_unit` (HA 2026.10+).
- One enabled raw diagnostic (FC03 holding 8); 56 candidate entities from the NUOS II
  manual, all disabled by default.
- Cited register catalogue `docs/registers/modbus.yaml` (56 documented addresses, 0 validated).
- Inert, default-deny write guard; no write entities or services.
