def test_import_api():
    from api.main import app
    assert app.title == "Vessel Delay Prediction API"


def test_vessel_request_enforces_training_ranges():
    import pytest
    from pydantic import ValidationError

    from api.main import VesselRequest

    with pytest.raises(ValidationError):
        VesselRequest(
            arrival_hour=8,
            cargo_volume=1200,
            berth_wait_minutes=1441,
            port_congestion="high",
            weather="rain",
            previous_delay_hours=1.5,
            crane_available=1,
        )

    with pytest.raises(ValidationError):
        VesselRequest(
            arrival_hour=8,
            cargo_volume=1200,
            berth_wait_minutes=45,
            port_congestion="high",
            weather="rain",
            previous_delay_hours=169,
            crane_available=1,
        )


def test_predict_probability_uses_positive_class_probability():
    import pandas as pd

    from api.main import predict_probability

    class ProbabilityModel:
        def predict_proba(self, features):
            assert isinstance(features, pd.DataFrame)
            return [[0.63, 0.37]]

        def predict(self, features):
            return [0]

    assert predict_probability(ProbabilityModel(), pd.DataFrame([{"x": 1}])) == 0.37

