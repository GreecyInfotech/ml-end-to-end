import pandas as pd

REQUIRED_COLUMNS = [
    "vessel_id", "arrival_hour", "cargo_volume", "berth_wait_minutes",
    "port_congestion", "weather", "previous_delay_hours", "crane_available", "delayed"
]

NUMERIC_RANGES = {
    "arrival_hour": (0, 23),
    "cargo_volume": (0, None),
    "berth_wait_minutes": (0, 1440),
    "previous_delay_hours": (0, 168),
    "crane_available": (0, 1),
}


def validate_data(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    if df.empty:
        raise ValueError("Dataset is empty")
    if df["vessel_id"].isna().any():
        raise ValueError("vessel_id cannot be null")
    if df["delayed"].isna().any() or not df["delayed"].isin([0, 1]).all():
        raise ValueError("Target delayed must contain only 0/1")
    for col, (low, high) in NUMERIC_RANGES.items():
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{col} contains non-numeric values")
        if low is not None and (values < low).any():
            raise ValueError(f"{col} below allowed minimum {low}")
        if high is not None and (values > high).any():
            raise ValueError(f"{col} above allowed maximum {high}")
