"""Unit tests for ``profile_system.profile``.

Covers the round-trip serialization and the batched-persistence behaviour
introduced by the audit fix.
"""
from __future__ import annotations

import json

from profile_system.profile import EntityTracker, Profile


def test_profile_to_dict_from_dict_round_trip():
    p = Profile("CUST-1")
    p.update_static({"age": 30})
    p.add_behavioral_signal({"amount": 100.0})
    p.add_text_insight({"sentiment": {"polarity": 0.4}})

    d = p.to_dict()
    p2 = Profile.from_dict(d)

    assert p2.entity_id == "CUST-1"
    assert p2.static_attributes == {"age": 30}
    assert p2.behavioral_signals == [{"amount": 100.0, "timestamp": p.behavioral_signals[0]["timestamp"]}]
    assert p2.text_insights == {"sentiment": {"polarity": 0.4}}


def test_profile_from_dict_handles_missing_optional_fields():
    p = Profile.from_dict({"entity_id": "CUST-2"})
    assert p.entity_id == "CUST-2"
    assert p.static_attributes == {}
    assert p.behavioral_signals == []


def test_entity_tracker_get_or_create_is_idempotent(tmp_path):
    store = tmp_path / "profiles.json"
    tracker = EntityTracker(storage_file=str(store))
    p1 = tracker.get_or_create_profile("CUST-1")
    p2 = tracker.get_or_create_profile("CUST-1")
    assert p1 is p2
    assert len(tracker.profiles) == 1


def test_entity_tracker_update_profile_persists(tmp_path):
    store = tmp_path / "profiles.json"
    tracker = EntityTracker(storage_file=str(store), debounce_seconds=0.05)
    tracker.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    tracker.save_profiles()  # force flush

    assert store.exists()
    with open(store) as f:
        data = json.load(f)
    assert "CUST-1" in data
    assert data["CUST-1"]["behavioral_signals"][0]["amount"] == 100.0


def test_entity_tracker_batched_persistence_does_not_write_every_update(tmp_path):
    """The audit explicitly flagged that the original ``save_profiles`` rewrote
    the entire file on every single update. The new implementation debounces
    writes, so a single update should NOT immediately touch the disk.
    """
    store = tmp_path / "profiles.json"
    tracker = EntityTracker(
        storage_file=str(store), debounce_seconds=5.0, flush_threshold=1000
    )
    tracker.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    # No flush yet (debounce is 5s and we are well below the threshold).
    assert not store.exists()


def test_entity_tracker_detect_changes(tmp_path):
    store = tmp_path / "profiles.json"
    tracker = EntityTracker(storage_file=str(store), debounce_seconds=5.0)
    # Add 11 recent signals -> anomaly flag should be True.
    for _ in range(11):
        tracker.update_profile("CUST-1", {"behavioral": {"amount": 1.0}})

    result = tracker.detect_changes("CUST-1")
    assert result["recent_signals"] >= 11
    assert result["anomalies"] is True


def test_entity_tracker_detect_changes_unknown_entity(tmp_path):
    tracker = EntityTracker(storage_file=str(tmp_path / "x.json"), debounce_seconds=5.0)
    assert tracker.detect_changes("NOPE") == {}


def test_get_profiles_df_columns(tmp_path):
    tracker = EntityTracker(storage_file=str(tmp_path / "x.json"), debounce_seconds=5.0)
    tracker.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    tracker.update_profile(
        "CUST-1", {"text": {"sentiment": {"polarity": 0.5, "subjectivity": 0.7}}}
    )
    df = tracker.get_profiles_df()
    expected_cols = {
        "entity_id", "total_amount", "avg_amount", "signal_count",
        "sentiment_polarity", "sentiment_subjectivity",
    }
    assert expected_cols.issubset(set(df.columns))
    assert len(df) == 1
    assert df.iloc[0]["signal_count"] == 1
