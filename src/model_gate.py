from __future__ import annotations


def promotion_gate(candidate, production, thresholds):
    reasons = []
    checks = {
        "f1": candidate["f1"] >= production["f1"],
        "recall": candidate["recall"] >= thresholds["min_recall"],
        "roc_auc": candidate["roc_auc"] >= production["roc_auc"],
        "pr_auc": candidate["pr_auc"] >= production["pr_auc"],
        "business_cost": candidate["business_cost"] <= production["business_cost"],
        "p95_latency_ms": candidate["p95_latency_ms"] <= thresholds["max_p95_latency_ms"],
    }
    for key, ok in checks.items():
        if not ok:
            reasons.append(key)
    return {"passed": not reasons, "checks": checks, "reasons": reasons}
