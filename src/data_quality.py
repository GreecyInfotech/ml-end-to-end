from __future__ import annotations

import pandas as pd

from .data_validation import NUMERIC_RANGES, REQUIRED_COLUMNS


def quality_report(df: pd.DataFrame):
    missing = {c: int(df[c].isna().sum()) for c in df.columns}
    schema_missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    invalid_numeric = {}
    out_of_range = {}
    for col, (low, high) in NUMERIC_RANGES.items():
        if col not in df:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        invalid_numeric[col] = int(values.isna().sum())
        invalid = pd.Series(False, index=df.index)
        if low is not None:
            invalid |= values < low
        if high is not None:
            invalid |= values > high
        out_of_range[col] = int(invalid.fillna(False).sum())

    invalid_target = None
    if "delayed" in df:
        invalid_target = int((~df["delayed"].isin([0, 1])).sum())
    duplicate_vessels = int(df["vessel_id"].duplicated().sum()) if "vessel_id" in df else None
    delay_rate = float(pd.to_numeric(df["delayed"], errors="coerce").mean()) if "delayed" in df else None
    issue_count = (
        len(schema_missing)
        + sum(missing.values())
        + sum(invalid_numeric.values())
        + sum(out_of_range.values())
        + (invalid_target or 0)
        + (duplicate_vessels or 0)
        + int(df.empty)
    )
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "schema_missing": schema_missing,
        "missing_by_column": missing,
        "duplicate_vessels": duplicate_vessels,
        "delay_rate": delay_rate,
        "invalid_numeric": invalid_numeric,
        "invalid_target": invalid_target,
        "out_of_range": out_of_range,
        "status": "PASS" if issue_count == 0 else "WARN",
    }
