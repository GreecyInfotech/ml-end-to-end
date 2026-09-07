import pandas as pd

from src.data_quality import quality_report


def valid_rows():
    return pd.DataFrame(
        {
            "vessel_id": ["V1", "V2"],
            "arrival_hour": [8, 18],
            "cargo_volume": [100.0, 200.0],
            "berth_wait_minutes": [20.0, 40.0],
            "port_congestion": ["Low", "High"],
            "weather": ["Clear", "Rain"],
            "previous_delay_hours": [0.0, 1.0],
            "crane_available": [1, 0],
            "delayed": [0, 1],
        }
    )


def test_quality_report_passes_valid_data():
    report = quality_report(valid_rows())

    assert report["status"] == "PASS"
    assert report["invalid_numeric"]["berth_wait_minutes"] == 0
    assert report["invalid_target"] == 0


def test_quality_report_reports_malformed_data_without_crashing():
    data = valid_rows().drop(columns="weather")
    data["arrival_hour"] = data["arrival_hour"].astype(object)
    data.loc[0, "arrival_hour"] = "not-a-number"
    data.loc[1, "berth_wait_minutes"] = 1441
    data.loc[0, "delayed"] = 2
    data.loc[1, "vessel_id"] = "V1"

    report = quality_report(data)

    assert report["status"] == "WARN"
    assert report["schema_missing"] == ["weather"]
    assert report["invalid_numeric"]["arrival_hour"] == 1
    assert report["out_of_range"]["berth_wait_minutes"] == 1
    assert report["invalid_target"] == 1
    assert report["duplicate_vessels"] == 1