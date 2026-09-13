"""Integration test: synthetic data → EntityTracker → cluster → anomalies."""
from __future__ import annotations

from generator.orchestrator import SyntheticDataOrchestrator
from profile_system.cli import Profiler


CONFIG_PATH = "config/global_synthetic_config.yaml"


def test_full_pipeline_from_synthetic_data(tmp_path):
    """Generate 30 synthetic records, ingest them into the profiler, then
    run clustering + anomaly detection and assert the results have the
    expected shape.
    """
    profiler = Profiler(storage_file=str(tmp_path / "p.json"))

    orch = SyntheticDataOrchestrator(CONFIG_PATH)
    records = orch.generate_batch("finance", "NA", 30)
    assert len(records) == 30

    for rec in records:
        metrics = rec["numeric_metrics"]
        profiler.update_profile(
            rec["entity_id"],
            {"behavioral": {"amount": metrics["transaction_amount"]}},
        )

    # Clustering should now succeed.
    labels, summary_df = profiler.cluster(n_clusters=3)
    assert len(labels) == 30
    assert "cluster" in summary_df.columns

    # Anomaly detection should produce a score per entity.
    scores, anomalies_df = profiler.detect_anomalies()
    assert len(scores) == 30


def test_hitl_override_workflow(tmp_path):
    profiler = Profiler(storage_file=str(tmp_path / "p.json"))
    profiler.update_profile("CUST-1", {"behavioral": {"amount": 100.0}})
    profiler.add_validation("CUST-1", "looks legit")
    assert len(profiler.hitl.validations) == 1
    assert profiler.hitl.get_feedback_for_entity("CUST-1")[0]["notes"] == "looks legit"
