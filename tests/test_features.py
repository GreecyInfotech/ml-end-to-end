import pandas as pd
from src.feature_engineering import create_features

def test_feature_creation():
    df = pd.DataFrame([{
        "arrival_hour": 18, "cargo_volume": 1200,
        "berth_wait_minutes": 70, "port_congestion": "High",
        "weather": "Rain", "previous_delay_hours": 2,
        "crane_available": 0
    }])
    out = create_features(df)
    assert out.loc[0, "is_peak_hour"] == 1
    assert out.loc[0, "high_berth_wait"] == 1
    assert out.loc[0, "high_cargo_volume"] == 1
    assert out.loc[0, "has_previous_delay"] == 1
