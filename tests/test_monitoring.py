import pandas as pd

from src.data_quality import quality_report
from src.drift import drift_report


def test_drift_report_marks_missing_features_unavailable():
    reference = pd.DataFrame({"arrival_hour": [1, 2], "weather": ["Clear", "Rain"]})
    current = pd.DataFrame({"arrival_hour": [1, 2]})

    report = drift_report(reference, current, ["arrival_hour"], ["weather"])

    weather = report.loc[report["feature"] == "weather"].iloc[0]
    assert weather["severity"] == "UNAVAILABLE"
    assert pd.isna(weather["psi"])


def test_quality_report_is_pass_for_valid_monitoring_data():
    data = pd.DataFrame(
        {
            "vessel_id": ["V1"],
            "arrival_hour": [8],
            "cargo_volume": [100.0],
            "berth_wait_minutes": [20.0],
            "port_congestion": ["Low"],
            "weather": ["Clear"],
            "previous_delay_hours": [0.0],
            "crane_available": [1],
            "delayed": [0],
        }
    )

    assert quality_report(data)["status"] == "PASS"