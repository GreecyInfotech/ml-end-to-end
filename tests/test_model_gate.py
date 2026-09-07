from src.model_gate import promotion_gate


def production_metrics():
    return {
        "f1": 0.65,
        "recall": 0.87,
        "roc_auc": 0.80,
        "pr_auc": 0.70,
        "business_cost": 508.0,
    }


def test_promotion_gate_requires_all_production_constraints():
    candidate = {
        **production_metrics(),
        "p95_latency_ms": 50.0,
    }
    result = promotion_gate(candidate, production_metrics(), {"min_recall": 0.85, "max_p95_latency_ms": 200.0})

    assert result["passed"] is True
    assert result["reasons"] == []


def test_promotion_gate_reports_failed_constraints():
    candidate = {
        "f1": 0.60,
        "recall": 0.80,
        "roc_auc": 0.75,
        "pr_auc": 0.65,
        "business_cost": 600.0,
        "p95_latency_ms": 250.0,
    }
    result = promotion_gate(candidate, production_metrics(), {"min_recall": 0.85, "max_p95_latency_ms": 200.0})

    assert result["passed"] is False
    assert set(result["reasons"]) == {"f1", "recall", "roc_auc", "pr_auc", "business_cost", "p95_latency_ms"}