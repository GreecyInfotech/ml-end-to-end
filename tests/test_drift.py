import pandas as pd
from src.drift import drift_report


def test_drift_report_detects_shift():
    ref = pd.DataFrame({"x": [1,2,3,4,5], "c": ["A","A","B","B","B"]})
    cur = pd.DataFrame({"x": [100,101,102,103,104], "c": ["C","C","C","C","C"]})
    report = drift_report(ref, cur, ["x"], ["c"])
    assert report.iloc[0]["psi"] > 0.1


def test_drift_report_detects_missingness_drift():
    ref = pd.DataFrame({"x": [1.0] * 10})
    cur = pd.DataFrame({"x": [None] * 3 + [1.0] * 7})

    report = drift_report(ref, cur, ["x"], [], missing_medium=0.10, missing_high=0.25)

    row = report.iloc[0]
    assert row["psi"] == 0.0
    assert row["missing_rate_delta"] == 0.3
    assert row["severity"] == "HIGH"


def test_drift_report_records_feature_sample_counts():
    ref = pd.DataFrame({"x": [1.0, None, 2.0]})
    cur = pd.DataFrame({"x": [1.0, 2.0, 3.0]})

    row = drift_report(ref, cur, ["x"], []).iloc[0]

    assert row["reference_rows"] == 2
    assert row["current_rows"] == 3
