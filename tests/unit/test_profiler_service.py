"""Tests for the Profiler service methods backing the new CLI commands."""
from __future__ import annotations

from profile_system.cli import Profiler


def test_stats_empty(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    s = p.stats()
    assert s["profile_count"] == 0
    assert s["total_behavioral_signals"] == 0
    assert s["avg_signals_per_profile"] == 0
    assert s["hitl_validations"] == 0


def test_stats_with_data(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    p.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    p.update_profile("CUST-2", {"behavioral": {"amount": 200.0}})
    s = p.stats()
    assert s["profile_count"] == 2
    assert s["total_behavioral_signals"] == 2
    assert s["avg_signals_per_profile"] == 1.0


def test_list_profiles(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    p.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    p.update_profile("CUST-2", {"behavioral": {"amount": 200.0}})
    rows = p.list_profiles()
    assert len(rows) == 2
    ids = {r["entity_id"] for r in rows}
    assert ids == {"CUST-1", "CUST-2"}
    for r in rows:
        assert r["signals"] == 1
        assert "updated_at" in r


def test_reset(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    p.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    p.update_profile("CUST-2", {"behavioral": {"amount": 200.0}})
    count = p.reset()
    assert count == 2
    assert len(p.tracker.profiles) == 0


def test_export_then_import_json_round_trip(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    for i in range(3):
        p.update_profile(f"CUST-{i}", {"behavioral": {"amount": float(i * 100)}})
    export_path = tmp_path / "export.json"
    count = p.export_profiles(str(export_path))
    assert count == 3
    assert export_path.exists()
    # Reset and re-import
    p.reset()
    assert len(p.tracker.profiles) == 0
    imported = p.import_profiles(str(export_path))
    assert imported == 3
    assert len(p.tracker.profiles) == 3


def test_export_csv_format(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    p.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    export_path = tmp_path / "export.csv"
    count = p.export_profiles(str(export_path))
    assert count == 1
    content = export_path.read_text()
    assert "entity_id" in content
    assert "signal_count" in content
    assert "CUST-1" in content


def test_import_csv(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("entity_id,amount,frequency\nA,100,5\nB,200,10\n")
    count = p.import_profiles(str(csv_path))
    assert count == 2
    assert "A" in p.tracker.profiles
    assert "B" in p.tracker.profiles
    assert p.tracker.profiles["A"].behavioral_signals[0]["amount"] == 100.0


def test_import_unsupported_format(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    path = tmp_path / "data.txt"
    path.write_text("hello")
    try:
        p.import_profiles(str(path))
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unsupported import format" in str(e)


def test_import_nonexistent_file(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    try:
        p.import_profiles("/nonexistent/file.csv")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_analyze_text_attaches_insight(tmp_path):
    p = Profiler(storage_file=str(tmp_path / "p.json"))
    insight = p.analyze_text("CUST-1", "Great transaction with positive feedback")
    assert "sentiment" in insight
    assert "polarity" in insight["sentiment"]
    assert "entities" in insight
    profile = p.tracker.profiles["CUST-1"]
    assert "sentiment" in profile.text_insights
