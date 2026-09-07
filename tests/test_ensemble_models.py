import numpy as np
import pandas as pd

from src.config import load_config
from src.ensemble_models import build_random_forest, build_xgboost
from src.feature_engineering import create_features, model_columns
from src.pipeline import make_preprocessor
from sklearn.pipeline import Pipeline


def training_data():
    raw = pd.DataFrame(
        [
            {"arrival_hour": 8, "cargo_volume": 1200.0, "berth_wait_minutes": 70.0, "port_congestion": "High", "weather": "Rain", "previous_delay_hours": 2.0, "crane_available": 0},
            {"arrival_hour": 14, "cargo_volume": 300.0, "berth_wait_minutes": 10.0, "port_congestion": "Low", "weather": "Clear", "previous_delay_hours": 0.0, "crane_available": 1},
            {"arrival_hour": 18, "cargo_volume": 1400.0, "berth_wait_minutes": 90.0, "port_congestion": "High", "weather": "Storm", "previous_delay_hours": 3.0, "crane_available": 0},
            {"arrival_hour": 4, "cargo_volume": 200.0, "berth_wait_minutes": 5.0, "port_congestion": "Low", "weather": "Clear", "previous_delay_hours": 0.0, "crane_available": 1},
            {"arrival_hour": 10, "cargo_volume": 900.0, "berth_wait_minutes": 65.0, "port_congestion": "Medium", "weather": "Cloudy", "previous_delay_hours": 1.2, "crane_available": 1},
            {"arrival_hour": 20, "cargo_volume": 500.0, "berth_wait_minutes": 15.0, "port_congestion": "Low", "weather": "Clear", "previous_delay_hours": 0.2, "crane_available": 1},
        ]
    )
    return create_features(raw)[model_columns()], np.array([1, 0, 1, 0, 1, 0])


def test_ensemble_models_fit_and_return_probabilities():
    cfg = load_config()
    features, target = training_data()

    for estimator in (build_random_forest(cfg), build_xgboost(cfg)):
        model = Pipeline([("preprocessor", make_preprocessor()), ("model", estimator)])
        model.fit(features, target)
        probabilities = model.predict_proba(features)[:, 1]

        assert probabilities.shape == (6,)
        assert np.isfinite(probabilities).all()
        assert ((probabilities >= 0) & (probabilities <= 1)).all()