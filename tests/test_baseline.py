import numpy as np
import pandas as pd

from src.baseline import build_baseline_model
from src.config import load_config
from src.feature_engineering import create_features, model_columns


def test_baseline_model_fits_and_returns_probabilities():
    cfg = load_config()
    raw = pd.DataFrame(
        [
            {
                "arrival_hour": 8,
                "cargo_volume": 1200.0,
                "berth_wait_minutes": 70.0,
                "port_congestion": "High",
                "weather": "Rain",
                "previous_delay_hours": 2.0,
                "crane_available": 0,
            },
            {
                "arrival_hour": 14,
                "cargo_volume": 300.0,
                "berth_wait_minutes": 10.0,
                "port_congestion": "Low",
                "weather": "Clear",
                "previous_delay_hours": 0.0,
                "crane_available": 1,
            },
            {
                "arrival_hour": 18,
                "cargo_volume": 1400.0,
                "berth_wait_minutes": 90.0,
                "port_congestion": "High",
                "weather": "Storm",
                "previous_delay_hours": 3.0,
                "crane_available": 0,
            },
            {
                "arrival_hour": 4,
                "cargo_volume": 200.0,
                "berth_wait_minutes": 5.0,
                "port_congestion": "Low",
                "weather": "Clear",
                "previous_delay_hours": 0.0,
                "crane_available": 1,
            },
        ]
    )
    features = create_features(raw)
    model = build_baseline_model(cfg)
    model.fit(features[model_columns()], np.array([1, 0, 1, 0]))

    probabilities = model.predict_proba(features[model_columns()])[:, 1]

    assert probabilities.shape == (4,)
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0) & (probabilities <= 1)).all()