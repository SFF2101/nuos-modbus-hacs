"""Constants for the Domotec NUOS Modbus integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "nuos_modbus"
MANUFACTURER: Final = "Domotec"

CONF_UNIT_ID: Final = "unit_id"
CONF_MODEL: Final = "model"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_DATAPOINT_SPACE: Final = "datapoint_register_space"
CONF_ADDRESS_OFFSET: Final = "address_offset"

DEFAULT_PORT: Final = 1502
DEFAULT_UNIT_ID: Final = 1
DEFAULT_SCAN_INTERVAL: Final = 120  # seconds; same cadence as the proven YAML pilot
MIN_SCAN_INTERVAL: Final = 30
MAX_SCAN_INTERVAL: Final = 3600
REQUEST_TIMEOUT: Final = 5.0  # seconds per Modbus request
MAX_BLOCK_LENGTH: Final = 16  # registers per read request

MODEL_NUOS_400_B: Final = "nuos_400_b_vtc200"
MODEL_NUOS_II: Final = "nuos_ii"
MODEL_NAMES: Final = {
    MODEL_NUOS_400_B: "NUOS 400 B (VTC200, R134a)",
    MODEL_NUOS_II: "NUOS II 300/400 (R290)",
}
SUPPORTED_MODELS: Final = tuple(MODEL_NAMES)

# §10.5 datapoints: FC04 (input) is the inferred default, FC03 (holding) the
# alternative. Neither is validated; see docs/registers/README.md.
SPACE_INPUT: Final = "input"
SPACE_HOLDING: Final = "holding"
DATAPOINT_SPACES: Final = (SPACE_INPUT, SPACE_HOLDING)
DEFAULT_DATAPOINT_SPACE: Final = SPACE_INPUT

# Correction applied to manual addresses of catalogue registers only (not to the
# fixed pilot diagnostic). 0 = manual address is the PDU address (assumed).
ADDRESS_OFFSETS: Final = {"minus_1": -1, "zero": 0, "plus_1": 1}
DEFAULT_ADDRESS_OFFSET: Final = 0

VALIDATION_NOT_VALIDATED: Final = "not_validated"
VALIDATION_READ_OK: Final = "read_ok_semantics_unvalidated"
VALIDATION_VALIDATED: Final = "validated"
