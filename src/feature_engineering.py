import pandas as pd

NUMERIC_FEATURES = [
    "arrival_hour", "cargo_volume", "berth_wait_minutes",
    "previous_delay_hours", "crane_available", "month", "day_of_week",
    "is_weekend", "is_peak_hour", "high_berth_wait", "high_cargo_volume",
    "has_previous_delay"
]
CATEGORICAL_FEATURES = ["port_congestion", "weather"]


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "event_timestamp" in out.columns:
        ts = pd.to_datetime(out["event_timestamp"], errors="coerce")
        out["month"] = ts.dt.month.fillna(0).astype(int)
        out["day_of_week"] = ts.dt.dayofweek.fillna(0).astype(int)
        out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)
    else:
        out["month"] = 0
        out["day_of_week"] = 0
        out["is_weekend"] = 0
    out["is_peak_hour"] = (out["arrival_hour"].between(7, 10) | out["arrival_hour"].between(17, 20)).astype(int)
    out["high_berth_wait"] = (out["berth_wait_minutes"] > 60).astype(int)
    out["high_cargo_volume"] = (out["cargo_volume"] > 1000).astype(int)
    out["has_previous_delay"] = (out["previous_delay_hours"] > 1).astype(int)
    return out


def model_columns():
    return NUMERIC_FEATURES + CATEGORICAL_FEATURES
