from pathlib import Path

from src.retrain import evaluate_retraining_triggers


def _config():
    return {
        "data": {"raw_path": "data/raw/vessels.csv"},
        "project": {"feature_version": "v2"},
        "model": {"label_version": "v1"},
        "business": {"requirements_version": "v1"},
        "retraining": {
            "min_new_rows": 2,
            "min_recall_drop": 0.05,
            "max_business_cost_increase": 0.10,
            "max_latency_increase_ratio": 0.20,
        },
    }


def test_retraining_detects_drift_and_performance_degradation(tmp_path: Path):
    dataset = tmp_path / "data.csv"
    dataset.write_text("x\n1\n2\n3\n", encoding="utf-8")
    decision = evaluate_retraining_triggers(
        {"status": "ALERT", "summary": {"high_drift_features": ["cargo_volume"]}},
        {"current": {"recall": 0.80, "business_cost": 14, "p95_latency_ms": 150}, "baseline": {"recall": 0.90, "business_cost": 10, "p95_latency_ms": 100}},
        _config(),
        {"data_rows": 0},
        dataset,
        [],
    )

    assert "data_drift" in decision["triggered"]
    assert "performance_degradation" in decision["triggered"]


def test_retraining_detects_explicit_operational_changes(tmp_path: Path):
    dataset = tmp_path / "data.csv"
    dataset.write_text("x\n1\n2\n3\n", encoding="utf-8")
    decision = evaluate_retraining_triggers(
        {"status": "PASS", "summary": {}},
        {},
        _config(),
        {"data_rows": 1, "data_fingerprint": "old", "feature_version": "v1", "label_version": "v0"},
        dataset,
        ["scheduled", "business_requirement_change", "feature_change", "label_change"],
    )

    assert {"scheduled", "business_requirement_change", "feature_change", "label_change"}.issubset(decision["triggered"])
    assert decision["data_rows"] == 3
    assert decision["data_fingerprint"]
