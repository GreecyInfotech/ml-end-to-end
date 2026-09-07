# Episode 2: Data Engineering, Quality, and Feature Engineering

**Duration:** 42 minutes

## Business Problem

A model cannot be production-ready if training data is invalid, unavailable, or transformed differently at serving time.

## Video Flow

1. Inspect `data/raw/vessels.csv`.
2. Explain the required schema and target field.
3. Demonstrate validation, quality reporting, cleaning, and feature creation.
4. Show how the same feature contract is used by training and the API.
5. Explain the feature-contract hash as a defense against training-serving skew.

## Live Demo

```powershell
Get-Content data/raw/vessels.csv -TotalCount 5
Get-Content src/data_validation.py
Get-Content src/data_quality.py
Get-Content src/data_cleaning.py
Get-Content src/feature_engineering.py
Get-Content src/feature_store.py
python -m monitoring.monitor --reference data/raw/vessels.csv --current data/raw/vessels.csv
Get-Content data/predictions/monitoring_report.json
```

## Explain on Screen

Required input fields include timestamp, arrival hour, cargo volume, berth wait, congestion, weather, previous delay, crane availability, and delayed label.

Demonstrate that the pipeline checks:

- Required columns
- Numeric ranges
- Missing values
- Target validity
- Timestamp quality
- Feature availability
- Missingness drift

## Suggested Experiment

Copy the CSV to a temporary file, alter a numeric range or remove a required feature, then run validation and show that the pipeline stops before training.

## Closing Evidence

Show `PASS`, `WARN`, and `ALERT` monitoring outcomes and the feature contract hash stored in model metadata.
