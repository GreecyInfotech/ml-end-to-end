import pandas as pd

NUMERIC = [
    "arrival_hour", "cargo_volume", "berth_wait_minutes",
    "previous_delay_hours", "crane_available"
]
CATEGORICAL = ["port_congestion", "weather"]

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.drop_duplicates(subset=["vessel_id"])
    for col in NUMERIC:
        out[col] = pd.to_numeric(out[col], errors="coerce")
        out[col] = out[col].fillna(out[col].median())
    for col in CATEGORICAL:
        out[col] = out[col].fillna("Unknown").astype(str)
    return out
