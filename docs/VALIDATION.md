# On-site validation plan (each step needs separate approval)

Nothing in this repository has been deployed to the live Home Assistant. These
steps are proposals for a governed pilot. They are ordered so that each step
adds the least possible risk.

## 0. Preconditions

- A current Home Assistant backup exists.
- Dimplex health baseline recorded from `dimplex_wpm` diagnostics:
  `consecutive_failures`, `failed_read_chunks`.
- The ≥24 h stability check of the existing two TCP sessions to the G13 is
  done. Those sessions are the YAML pilot hub `nuos_g13` and Dimplex.

## 1. Display references (no Modbus traffic)

At a recorded time, the owner reads these values on the NUOS display:
- **Software** version (for example VT10 or VT12), in the service menu;
- **T Wasser** (tank temperature);
- **Timer** on/off, and the timer **start hour** (if the timer is off, the
  stored value may still be shown);
- **Betr.Art**, **T Soll** and **T max**.

If the timer start hour is **12**, that supports *FC03 holding 8 = 009.Start_HP_Hour*.

## 2. Install this integration — replacing, not adding

Install it in place of the YAML pilot. That keeps the gateway at two TCP
sessions (Dimplex + this integration):

1. Remove the `modbus:` block from `configuration.yaml`, then call
   `modbus.reload`. No restart is needed in HA 2026.10.
2. Install from HACS and restart once.
3. Add the integration: host, port 1502, unit 1, model NUOS 400 B.
4. Default traffic is one FC03 read of holding 8 every 120 s, identical to
   the pilot.

## 3. One candidate at a time

Enable **only** *Tank temperature T2 (candidate)*.
- This adds one FC04 read of input 8.
- Compare it with the display T Wasser from step 1.
- If FC04 is rejected, the entity becomes unavailable and the address is logged
  as unsupported. **Do not** switch the datapoint space to holding to "make it
  work": FC03 holding 8 is already known to read 12.

Mark a register `validated` in `docs/registers/modbus.yaml` only after
agreement with an independent reference. Then, by a separate change, consider
enabling it by default.

## 4. Writes

Writes stay out of scope. A future tariff-optimisation profile needs all of
the following:
- validated registers;
- a `validated` `WriteProfile` with an explicit allow-list;
- confirmation that 118.Modbus Allow Write is set as intended;
- a separately approved change.

Communication, RTC, defrost-type and fan-type registers are never writable.
