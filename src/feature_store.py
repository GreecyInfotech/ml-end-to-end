from __future__ import annotations

import hashlib
import json
from typing import Any

from .feature_engineering import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def feature_contract(version: str = "v2") -> dict[str, Any]:
    return {
        "feature_version": version,
        "numeric_features": list(NUMERIC_FEATURES),
        "categorical_features": list(CATEGORICAL_FEATURES),
        "derived_rules": {
            "is_peak_hour": "arrival_hour in 7-10 or 17-20",
            "high_berth_wait": "berth_wait_minutes > 60",
            "high_cargo_volume": "cargo_volume > 1000",
            "has_previous_delay": "previous_delay_hours > 1",
            "calendar_features": "event_timestamp",
        },
    }


def feature_contract_hash(version: str = "v2") -> str:
    payload = json.dumps(feature_contract(version), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
