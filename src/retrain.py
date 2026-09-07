from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT
from .feature_store import feature_contract_hash

TRIGGER_NAMES = (
    "data_drift",
    "performance_degradation",
    "business_requirement_change",
    "new_data",
    "scheduled",
    "feature_change",
    "label_change",
    "manual",
)


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def _file_fingerprint(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metric(report: dict[str, Any], name: str, section: str) -> float | None:
    value = report.get(section, {}).get(name) if isinstance(report.get(section), dict) else None
    if value is None:
        value = report.get(f"{section}_{name}")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _performance_degradation(performance: dict[str, Any], cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    policy = cfg.get("retraining", {})
    evidence: dict[str, Any] = {}
    current = performance.get("current", performance)
    baseline = performance.get("baseline", {})
    if not isinstance(current, dict) or not isinstance(baseline, dict) or not baseline:
        return False, evidence
    checks = {
        "recall_drop": ("recall", float(policy.get("min_recall_drop", 0.05)), "drop"),
        "business_cost_increase": ("business_cost", float(policy.get("max_business_cost_increase", 0.10)), "relative_increase"),
        "latency_increase": ("p95_latency_ms", float(policy.get("max_latency_increase_ratio", 0.20)), "relative_increase"),
    }
    degraded = False
    for check_name, (metric_name, threshold, mode) in checks.items():
        try:
            before = float(baseline[metric_name])
            after = float(current[metric_name])
        except (KeyError, TypeError, ValueError):
            continue
        change = (before - after) / max(abs(before), 1e-9) if mode == "drop" else (after - before) / max(abs(before), 1e-9)
        evidence[check_name] = {"before": before, "after": after, "change": change, "threshold": threshold}
        if change >= threshold:
            degraded = True
    return degraded, evidence


def evaluate_retraining_triggers(
    report: dict[str, Any],
    performance_report: dict[str, Any],
    cfg: dict[str, Any],
    previous_audit: dict[str, Any],
    dataset_path: Path,
    explicit_triggers: list[str] | None = None,
) -> dict[str, Any]:
    policy = cfg.get("retraining", {})
    explicit = set(explicit_triggers or [])
    feature_version = cfg.get("project", {}).get("feature_version", "unknown")
    label_version = cfg.get("model", {}).get("label_version", "v1")
    business_version = cfg.get("business", {}).get("requirements_version", "v1")
    fingerprint = _file_fingerprint(dataset_path)
    row_count = int(dataset_path.read_text(encoding="utf-8", errors="ignore").count("\n")) - 1 if dataset_path.exists() else 0
    drift_detected = report.get("status") in {"WARN", "ALERT"} or bool(
        report.get("summary", {}).get("high_drift_features") or report.get("summary", {}).get("medium_drift_features")
    )
    performance_detected, performance_evidence = _performance_degradation(performance_report, cfg)
    previous_rows = int(previous_audit.get("data_rows", 0) or 0)
    new_data_detected = bool(
        previous_audit
        and row_count - previous_rows >= int(policy.get("min_new_rows", 100))
        and fingerprint != previous_audit.get("data_fingerprint")
    )
    current_feature_hash = feature_contract_hash(feature_version)
    detected = {
        "data_drift": (drift_detected, {"status": report.get("status"), "summary": report.get("summary", {})}),
        "performance_degradation": (performance_detected, performance_evidence),
        "business_requirement_change": ("business_requirement_change" in explicit or business_version != previous_audit.get("business_requirements_version", business_version), {"version": business_version}),
        "new_data": (new_data_detected, {"rows": row_count, "previous_rows": previous_rows, "fingerprint": fingerprint}),
        "scheduled": ("scheduled" in explicit, {"schedule": policy.get("schedule", "external")}),
        "feature_change": ("feature_change" in explicit or feature_version != previous_audit.get("feature_version", feature_version) or current_feature_hash != previous_audit.get("feature_contract_hash", current_feature_hash), {"version": feature_version, "contract_hash": current_feature_hash}),
        "label_change": ("label_change" in explicit or label_version != previous_audit.get("label_version", label_version), {"version": label_version}),
        "manual": ("manual" in explicit or not explicit, {"reason": "operator_requested"}),
    }
    triggers = [{"name": name, "detected": bool(found), "evidence": evidence} for name, (found, evidence) in detected.items()]
    return {
        "triggered": [item["name"] for item in triggers if item["detected"]],
        "triggers": triggers,
        "data_rows": row_count,
        "data_fingerprint": fingerprint,
        "feature_version": feature_version,
        "feature_contract_hash": current_feature_hash,
        "label_version": label_version,
        "business_requirements_version": business_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled vessel-delay retraining")
    parser.add_argument("--monitoring-report", default="data/predictions/monitoring_report.json")
    parser.add_argument("--performance-report", default="data/predictions/performance_report.json")
    parser.add_argument("--trigger", action="append", choices=TRIGGER_NAMES, default=[])
    parser.add_argument("--allow-alert", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    report_path = ROOT / args.monitoring_report
    report = _read_json(report_path, {"status": "UNAVAILABLE"})
    status = report.get("status", "UNAVAILABLE")
    if status == "ALERT" and not args.allow_alert:
        raise SystemExit("Retraining blocked: monitoring status is ALERT; use --allow-alert with an approved reason")

    cfg = _read_json(ROOT / "configs" / "config.json", {})
    if not cfg:
        import yaml
        cfg = yaml.safe_load((ROOT / "configs" / "config.yaml").read_text(encoding="utf-8"))
    previous_audit = _read_json(ROOT / "models" / "retraining_audit.json", {})
    decision = evaluate_retraining_triggers(
        report,
        _read_json(ROOT / args.performance_report, {}),
        cfg,
        previous_audit,
        ROOT / cfg["data"]["raw_path"],
        args.trigger,
    )
    audit = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "reason": args.reason,
        "monitoring_status": status,
        "allow_alert": args.allow_alert,
        "decision": decision,
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        print(json.dumps(audit, indent=2))
        return

    result = subprocess.run([sys.executable, "-m", "src.train"], cwd=ROOT, check=False)
    audit["exit_code"] = result.returncode
    audit_path = ROOT / "models" / "retraining_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()