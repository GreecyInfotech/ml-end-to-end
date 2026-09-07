from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Run controlled vessel-delay retraining")
    parser.add_argument("--monitoring-report", default="data/predictions/monitoring_report.json")
    parser.add_argument("--allow-alert", action="store_true")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    report_path = ROOT / args.monitoring_report
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"status": "UNAVAILABLE"}
    status = report.get("status", "UNAVAILABLE")
    if status == "ALERT" and not args.allow_alert:
        raise SystemExit("Retraining blocked: monitoring status is ALERT; use --allow-alert with an approved reason")

    result = subprocess.run([sys.executable, "-m", "src.train"], cwd=ROOT, check=False)
    audit = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "reason": args.reason,
        "monitoring_status": status,
        "allow_alert": args.allow_alert,
        "exit_code": result.returncode,
    }
    audit_path = ROOT / "models" / "retraining_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()