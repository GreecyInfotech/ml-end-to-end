from __future__ import annotations

import math
import numpy as np
import pandas as pd


def _psi_from_distributions(expected, actual, eps=1e-6):
    expected = np.asarray(expected, dtype=float) + eps
    actual = np.asarray(actual, dtype=float) + eps
    expected = expected / expected.sum()
    actual = actual / actual.sum()
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def numeric_psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    ref = pd.to_numeric(reference, errors="coerce").dropna()
    cur = pd.to_numeric(current, errors="coerce").dropna()
    if ref.empty or cur.empty:
        return math.nan
    edges = np.unique(np.nanquantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf
    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)
    return _psi_from_distributions(ref_counts, cur_counts)


def categorical_psi(reference: pd.Series, current: pd.Series) -> float:
    ref = reference.fillna("__MISSING__").astype(str)
    cur = current.fillna("__MISSING__").astype(str)
    cats = sorted(set(ref.unique()) | set(cur.unique()))
    ref_counts = [int((ref == c).sum()) for c in cats]
    cur_counts = [int((cur == c).sum()) for c in cats]
    return _psi_from_distributions(ref_counts, cur_counts)


def drift_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    numeric_features,
    categorical_features,
    psi_medium: float = 0.10,
    psi_high: float = 0.25,
    missing_medium: float = 0.10,
    missing_high: float = 0.25,
):
    rows = []
    for col, feature_type in [(col, "numeric") for col in numeric_features] + [(col, "categorical") for col in categorical_features]:
        if col not in reference or col not in current:
            rows.append({"feature": col, "type": feature_type, "psi": math.nan, "severity": "UNAVAILABLE", "missing_rate_delta": math.nan})
            continue
        psi = numeric_psi(reference[col], current[col]) if feature_type == "numeric" else categorical_psi(reference[col], current[col])
        reference_missing = float(reference[col].isna().mean())
        current_missing = float(current[col].isna().mean())
        missing_delta = abs(current_missing - reference_missing)
        if pd.isna(psi):
            severity = "UNAVAILABLE"
        elif psi >= psi_high or missing_delta >= missing_high:
            severity = "HIGH"
        elif psi >= psi_medium or missing_delta >= missing_medium:
            severity = "MEDIUM"
        else:
            severity = "LOW"
        rows.append({
            "feature": col,
            "type": feature_type,
            "psi": psi,
            "severity": severity,
            "reference_rows": int(reference[col].notna().sum()),
            "current_rows": int(current[col].notna().sum()),
            "reference_missing_rate": reference_missing,
            "current_missing_rate": current_missing,
            "missing_rate_delta": missing_delta,
        })
    result = pd.DataFrame(rows)
    return result.sort_values("psi", ascending=False).reset_index(drop=True)
