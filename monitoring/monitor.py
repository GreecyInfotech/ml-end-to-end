from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import pandas as pd

from src.config import ROOT, load_config
from src.data_quality import quality_report
from src.drift import drift_report
from src.feature_engineering import CATEGORICAL_FEATURES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default=None)
    parser.add_argument("--current", default=None)
    parser.add_argument("--fail-on-alert", action="store_true")
    args = parser.parse_args()
    cfg = load_config()
    reference_path = ROOT / (args.reference or cfg["data"]["reference_path"])
    current_path = ROOT / (args.current or cfg["data"]["raw_path"])
    reference = pd.read_csv(reference_path)
    current = pd.read_csv(current_path)
    raw_numeric = ["arrival_hour", "cargo_volume", "berth_wait_minutes", "previous_delay_hours", "crane_available"]
    quality = quality_report(current)
    drift_cfg = cfg.get("drift", {})
    drift = drift_report(
        reference,
        current,
        raw_numeric,
        CATEGORICAL_FEATURES,
        psi_medium=float(drift_cfg.get("psi_medium", 0.10)),
        psi_high=float(drift_cfg.get("psi_high", 0.25)),
        missing_medium=float(drift_cfg.get("missing_medium", 0.10)),
        missing_high=float(drift_cfg.get("missing_high", 0.25)),
    ).to_dict(orient="records")
    severities = {row["severity"] for row in drift}
    if quality["status"] != "PASS" or "UNAVAILABLE" in severities or "HIGH" in severities:
        status = "ALERT"
    elif "MEDIUM" in severities:
        status = "WARN"
    else:
        status = "PASS"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reference_path": str(reference_path),
        "current_path": str(current_path),
        "data_quality": quality,
        "drift": drift,
        "summary": {
            "high_drift_features": [row["feature"] for row in drift if row["severity"] == "HIGH"],
            "medium_drift_features": [row["feature"] for row in drift if row["severity"] == "MEDIUM"],
            "unavailable_features": [row["feature"] for row in drift if row["severity"] == "UNAVAILABLE"],
        },
    }
    out = ROOT / "data" / "predictions" / "monitoring_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    if args.fail_on_alert and status == "ALERT":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
