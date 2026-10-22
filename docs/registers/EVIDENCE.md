# Evidence matrix, 2026-10-22 (DAI-IN-636)

`evidence_matrix_2026-10-22.yaml` classifies all 57 registers (56 manufacturer
rows + the FC03 holding 8 pilot) as PROVEN / PLAUSIBLE / UNKNOWN against the
installed NUOS 400 B (VTC200). It is **documentation only**: no runtime table,
entity name, `entity_id` or `unique_id` changed, and nothing here is deployed.

Basis: Home Assistant recorder history (20-22 Oct 2026) of the read-only
entities and the independent smart-plug power sensor. No extra Modbus traffic.
Absolute temperature accuracy and display-dependent items stay PENDING until
the owner reads the display (see the YAML `pending_owner_display_reading`).

Key results: parameters are holding registers and datapoints input registers;
manual address = PDU address; the compressor relay (input 9) matches the power
meter; T1/T2 respond as expected; the controller clock runs but is set wrongly;
T3 (input 19) is a constant 0.0 and is not treated as a temperature. Nothing
is marked `validated` in `modbus.yaml`.
