"""Unit tests for the HITL feedback store."""
from __future__ import annotations

from profile_system.hitl import HITLFeedback


def test_add_and_retrieve_validation():
    hitl = HITLFeedback()
    hitl.add_validation({"entity_id": "CUST-1", "validated": True, "notes": "ok"})
    hitl.add_validation({"entity_id": "CUST-2", "validated": False, "notes": "bad"})
    result = hitl.get_feedback_for_entity("CUST-1")
    assert len(result) == 1
    assert result[0]["validated"] is True


def test_apply_overrides():
    hitl = HITLFeedback()
    hitl.add_override({"rule": "anomaly_threshold", "override_value": 0.05})
    config = {"anomaly_threshold": 0.1, "other": "x"}
    out = hitl.apply_overrides(config)
    assert out["anomaly_threshold"] == 0.05
    assert out["other"] == "x"


def test_get_feedback_for_unknown_entity_returns_empty():
    hitl = HITLFeedback()
    assert hitl.get_feedback_for_entity("NOPE") == []
