"""docs/registers/modbus.yaml completeness and agreement with the runtime table."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from custom_components.nuos_modbus.const import VALIDATION_READ_OK
from custom_components.nuos_modbus.registers import PILOT, REGISTERS

CATALOGUE = Path(__file__).parents[1] / "docs" / "registers" / "modbus.yaml"
SECTIONS = {
    "parameters": "parameter",
    "rtc": "rtc",
    "communication": "communication",
    "datapoints": "datapoint",
}


@pytest.fixture(scope="module")
def cat() -> dict:
    return yaml.safe_load(CATALOGUE.read_text(encoding="utf-8"))


def _entries(cat: dict) -> list[tuple[str, dict]]:
    return [(group, e) for section, group in SECTIONS.items() for e in cat[section]]


def test_counts_match_manual_tables(cat: dict) -> None:
    """Every source-documented register present, once."""
    assert [e["address"] for e in cat["parameters"]] == [*range(4, 24), *range(25, 34)]
    assert [e["address"] for e in cat["rtc"]] == list(range(103, 110))
    assert [e["address"] for e in cat["communication"]] == list(range(114, 118))
    assert [e["address"] for e in cat["datapoints"]] == [0, 1, *range(7, 20), 119]
    total = sum(len(cat[s]) for s in SECTIONS)
    assert total == cat["summary"]["documented_addresses_total"] == 56
    assert sum(cat["summary"]["by_table"].values()) == 56
    wp_ls = next(e for e in cat["parameters"] if e["key"] == "wp_ls")
    assert len(wp_ls["variants"]) == 2  # 57 table rows
    assert cat["summary"]["documented_table_rows_total"] == 57


def test_every_entry_has_provenance(cat: dict) -> None:
    for _, e in _entries(cat):
        assert e["source"]["doc"] == "nuos_ii_2026_09", e["key"]
        assert e["source"]["page"] in (33, 34, 35), e["key"]
        for field in ("key", "display", "address", "space", "fc_read", "type", "ha"):
            assert field in e, (e["key"], field)
        assert "enabled_default" in e["ha"], e["key"]
        assert e["ha"]["enabled_default"] is False, e["key"]


def test_spaces_overlap_only_across_tables(cat: dict) -> None:
    """Parameters and datapoints share addresses -> they must be distinct spaces."""
    holding = [e["address"] for g, e in _entries(cat) if g != "datapoint"]
    inputs = [e["address"] for g, e in _entries(cat) if g == "datapoint"]
    assert len(holding) == len(set(holding))
    assert len(inputs) == len(set(inputs))
    assert set(holding) & set(inputs)  # e.g. 8, the reason the spaces differ
    assert cat["protocol"]["function_code_per_table"] == "unknown"
    assert cat["register_space_inference"]["status"] == "inference_not_validated"


def test_validation_state_is_honest(cat: dict) -> None:
    validated = [e["key"] for _, e in _entries(cat) if e.get("validation") == "validated"]
    read_ok = [e["key"] for _, e in _entries(cat) if e.get("validation") == VALIDATION_READ_OK]
    assert validated == []
    assert read_ok == ["start_hp_hour"]
    assert cat["summary"]["validated_semantics_on_installed_appliance"] == 0
    assert cat["defaults"]["model_compatibility"]["nuos_400_b_r134a_vtc200"] == "undocumented_candidate"
    t2 = next(e for e in cat["datapoints"] if e["key"] == "t2_tank")
    assert "must not be used as T2" in t2["onsite_evidence"]


def test_runtime_table_matches_catalogue(cat: dict) -> None:
    runtime = {r.key: r for r in REGISTERS if r is not PILOT}
    catalogue = {e["key"]: (g, e) for g, e in _entries(cat)}
    assert set(runtime) == set(catalogue)
    for key, (group, e) in catalogue.items():
        r = runtime[key]
        assert r.group == group, key
        assert r.address == e["address"], key
        assert r.space == e["space"], key
        assert r.enabled_default is False, key
        assert r.platform == e["ha"]["platform"], key
        assert r.writable_documented == (e.get("fc_write") == 6), key
        if e.get("decimals") is not None and not r.raw_only:
            assert r.decimals == e["decimals"], key
        if e.get("min") is not None:
            assert (r.minimum, r.maximum) == (e["min"], e["max"]), key
        if e["ha"].get("raw_only"):
            assert r.raw_only, key
        if group == "communication" or e.get("do_not_change"):
            assert r.write_forbidden, key
        if e.get("unit") in ("°C",) and not r.raw_only:
            assert r.unit == "°C", key


def test_pilot_matches_catalogue(cat: dict) -> None:
    p = cat["pilot_diagnostic"]
    assert (PILOT.space, PILOT.address) == ("holding", p["read"]["address"])
    assert p["read"]["fc"] == 3
    assert PILOT.enabled_default is True and p["ha"]["enabled_default"] is True
    assert PILOT.raw_only and PILOT.unit is None and PILOT.device_class is None


def test_excluded_and_reviewed_sources(cat: dict) -> None:
    src = cat["sources"]
    assert src["nuos_400_2023_11"]["review_status"] == "fully_reviewed_for_modbus"
    assert "NO register" in src["nuos_400_2023_11"]["finding"]
    assert src["excluded"][0]["file"].startswith("NUOS-EXTRA")
