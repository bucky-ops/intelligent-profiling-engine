"""Unit tests for the config loader and orchestrator.

These guard against the YAML structural regression flagged in the audit
(domains wrongly nested under ``regions:``).
"""
from __future__ import annotations

import pytest

from generator.config import ConfigLoader
from generator.orchestrator import SyntheticDataOrchestrator


CONFIG_PATH = "config/global_synthetic_config.yaml"


def test_config_regions_does_not_contain_domain_keys():
    cfg = ConfigLoader(CONFIG_PATH).config
    regions = cfg["regions"]
    for domain in ("finance", "ngo", "telecom", "traffic"):
        # Regression: these used to be incorrectly nested under `regions:`.
        assert domain not in regions, (
            f"Domain '{domain}' must not be a key under 'regions:' "
            "(audit regression)."
        )


def test_config_has_top_level_domains_key():
    cfg = ConfigLoader(CONFIG_PATH).config
    assert "domains" in cfg
    assert set(cfg["domains"]) == {"finance", "ngo", "telecom", "traffic"}


@pytest.mark.parametrize(
    "domain,region",
    [
        ("finance", "NA"),
        ("ngo", "EU"),
        ("telecom", "SSA"),
        ("traffic", "EA"),
    ],
)
def test_orchestrator_generates_record_for_each_domain(domain, region):
    orch = SyntheticDataOrchestrator(CONFIG_PATH)
    rec = orch.generate_record(domain, region)
    assert rec["domain"] == domain
    assert rec["region"] == region
    assert "entity_id" in rec
    assert "numeric_metrics" in rec


def test_orchestrator_rejects_unknown_region():
    orch = SyntheticDataOrchestrator(CONFIG_PATH)
    with pytest.raises(KeyError):
        orch.generate_record("finance", "ATLANTIS")


def test_orchestrator_rejects_unknown_domain():
    orch = SyntheticDataOrchestrator(CONFIG_PATH)
    with pytest.raises(KeyError):
        orch.generate_record("agriculture", "NA")


def test_orchestrator_batch_size():
    orch = SyntheticDataOrchestrator(CONFIG_PATH)
    records = orch.generate_batch("finance", "NA", 5)
    assert len(records) == 5
    assert all(r["domain"] == "finance" for r in records)
