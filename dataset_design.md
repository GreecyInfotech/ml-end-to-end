# Vessel Delay Prediction Dataset Design

## 1. Document Purpose

This document defines the data contract and lifecycle for the vessel-delay prediction system. It covers the training dataset, inference payload, derived features, validation, quality gates, split strategy, drift reference, lineage, and production ingestion requirements.

The repository currently contains a synthetic dataset for development and testing. The observed values in this document describe that file; they are not a substitute for a governed production data contract.

## 2. Dataset Objective

The model predicts whether a vessel will be delayed by more than two hours.

- Target column: `delayed`
- Target type: binary integer, `0` or `1`
- Positive class: `1`, delayed
- Negative class: `0`, not delayed
- Prediction unit: one vessel arrival event
- Grain key: `vessel_id`
- Event-time column: `event_timestamp`

The target must be known only for historical training and evaluation records. It must not be sent in an online prediction request.

## 3. Current Development Dataset

The current `data/raw/vessels.csv` contains:

| Property | Observed value |
|---|---:|
| Rows | 5,000 |
| Columns | 10 |
| Date range | 2024-01-01 00:00:00 to 2025-02-20 14:00:00 |
| Delay rate | 34.36% |
| Duplicate `vessel_id` values | 0 |
| Missing values | 0 in the supplied file |

Observed categorical values:

- `port_congestion`: `High`, `Low`, `Medium`
- `weather`: `Clear`, `Cloudy`, `Rain`, `Storm`

Observed numeric ranges:

| Column | Minimum | Maximum |
|---|---:|---:|
| `arrival_hour` | 0 | 22 |
| `cargo_volume` | 100.0 | 2454.3 |
| `berth_wait_minutes` | 0.0 | 158.9 |
| `previous_delay_hours` | 0.0 | 8.61 |
| `crane_available` | 0 | 1 |

## 4. Raw Schema

| Column | Type | Required | Meaning | Training use |
|---|---|---:|---|---|
| `vessel_id` | string | Yes | Stable identifier for a vessel arrival event | Key and duplicate detection; not a model feature |
| `event_timestamp` | datetime string | Recommended | Time at which the arrival event was recorded | Temporal ordering and calendar features |
| `arrival_hour` | integer | Yes | Hour of arrival in local port time | Numeric feature |
| `cargo_volume` | decimal | Yes | Cargo volume associated with the arrival | Numeric feature |
| `berth_wait_minutes` | decimal | Yes | Berth waiting time observed for the event | Numeric feature |
| `port_congestion` | categorical string | Yes | Port congestion level | Categorical feature |
| `weather` | categorical string | Yes | Weather condition at the event | Categorical feature |
| `previous_delay_hours` | decimal | Yes | Historical delay duration available before this event | Numeric feature |
| `crane_available` | binary integer | Yes | Whether a crane was available, 1 or 0 | Numeric feature |
| `delayed` | binary integer | Training only | Whether the vessel was delayed more than two hours | Target label |

### Required CSV header

```text
vessel_id,event_timestamp,arrival_hour,cargo_volume,berth_wait_minutes,port_congestion,weather,previous_delay_hours,crane_available,delayed
```

## 5. Data Contract Rules

The training validator in `src/data_validation.py` enforces these rules:

- The dataset must not be empty.
- Required columns must be present.
- `vessel_id` must not be null.
- `delayed` must contain only `0` and `1`.
- `arrival_hour` must be between 0 and 23.
- `cargo_volume` must be at least 0.
- `berth_wait_minutes` must be between 0 and 1440 minutes.
- `previous_delay_hours` must be between 0 and 168 hours.
- `crane_available` must be 0 or 1.
- Numeric fields must be parseable as numbers.
- When present, `event_timestamp` must parse successfully.

The API applies the corresponding request bounds for `arrival_hour`, `berth_wait_minutes`, `previous_delay_hours`, `cargo_volume`, and `crane_available`.

Production ingestion should additionally enforce:

- Unique event identity, preferably a composite of source system, vessel, and event timestamp.
- A declared timezone for `event_timestamp` and a normalized UTC representation.
- Allowed-value dictionaries for categorical fields.
- Freshness and late-arrival limits.
- Source record counts and reconciliation totals.
- Rejection or quarantine of invalid records rather than silent correction.

## 6. Data Preparation Lifecycle

The training flow processes data in this order:

```text
Source extract
    -> schema and range validation
    -> data-quality report
    -> duplicate removal and type normalization
    -> missing-value handling
    -> feature engineering
    -> chronological split
    -> model training and evaluation
```

`src/data_cleaning.py` currently:

- Removes duplicate rows by `vessel_id`, retaining the first occurrence.
- Converts numeric fields with coercion.
- Fills numeric missing values with the column median.
- Fills missing categorical values with `Unknown`.

For production, invalid numeric coercion and duplicate records should be counted and surfaced as quality metrics before cleaning. A record-level quarantine path is preferable to silently replacing values when the source is operationally important.

## 7. Feature Design

The model uses the following numeric features:

```text
arrival_hour
cargo_volume
berth_wait_minutes
previous_delay_hours
crane_available
month
day_of_week
is_weekend
is_peak_hour
high_berth_wait
high_cargo_volume
has_previous_delay
```

Categorical features:

```text
port_congestion
weather
```

Derived feature definitions:

| Feature | Definition |
|---|---|
| `month` | Month extracted from `event_timestamp`; 0 if no timestamp exists |
| `day_of_week` | Monday=0 through Sunday=6; 0 if no timestamp exists |
| `is_weekend` | 1 when day of week is Saturday or Sunday, otherwise 0 |
| `is_peak_hour` | 1 for arrival hours 7-10 or 17-20, otherwise 0 |
| `high_berth_wait` | 1 when `berth_wait_minutes` is greater than 60 |
| `high_cargo_volume` | 1 when `cargo_volume` is greater than 1000 |
| `has_previous_delay` | 1 when `previous_delay_hours` is greater than 1 |

The `vessel_id` is intentionally excluded from model features to avoid memorization. The `delayed` label is also excluded from inference features.

## 8. Leakage and Availability Rules

Every feature must be available at the time the prediction is requested. In particular:

- `previous_delay_hours` must represent history known before the current arrival event.
- `berth_wait_minutes` must be available at the chosen prediction point. If it is only known after the outcome, it is leakage and must be removed or the prediction point must be redefined.
- `delayed` is a historical outcome and is never an input feature.
- Future schedule, post-arrival handling, or retrospective status fields must not enter the feature set.
- Any feature sourced after the prediction timestamp must be rejected during feature review.

The production data contract should document an availability timestamp for every feature, not only its business definition.

## 9. Train, Calibration, and Test Design

When `event_timestamp` exists, the pipeline sorts chronologically and creates:

```text
first 70%  -> training set
next 10%   -> calibration set for threshold tuning
last 20%   -> untouched test set
```

The test set is not used to fit models or tune thresholds. Five-fold `TimeSeriesSplit` is used on the training portion. Without timestamps, the fallback is stratified random splitting and stratified cross-validation.

For production data, split boundaries should be recorded as dataset versions with:

- Source extract identifier
- Minimum and maximum event timestamp
- Row counts
- Positive-class rate
- Feature schema hash
- Code and feature version
- Creation timestamp

## 10. Preprocessing Contract

The model pipeline applies preprocessing fitted only on training data:

- Numeric fields: median imputation followed by standardization.
- Categorical fields: most-frequent imputation followed by one-hot encoding.
- Unseen categories at inference: ignored by the encoder rather than causing a request failure.

The training and inference paths must use the same `create_features()` implementation and the same ordered model columns. A feature version change requires a new model version and should not silently reuse an old artifact.

## 11. Data Quality Checks

The quality report in `src/data_quality.py` records:

- Row and column counts
- Missing values by column
- Missing required schema fields
- Duplicate vessel IDs
- Delay rate
- Invalid numeric values by column
- Invalid target values
- Out-of-range counts
- Overall `PASS` or `WARN` status

Recommended production quality thresholds:

| Check | Recommended action |
|---|---|
| Missing required column | Reject batch |
| Invalid target value | Reject training batch |
| Invalid event timestamp | Reject or quarantine record |
| Duplicate event key | Quarantine and investigate |
| Missing feature | Quarantine or apply an approved imputation policy |
| Delay rate shift | Alert; investigate label or operational change |
| Stale data | Alert and block scheduled training if beyond SLA |

Quality checks should run before training and before monitoring. Their report should be retained with the model run.

## 12. Drift Reference Design

The current configuration points the reference dataset to `data/raw/vessels.csv`. This is suitable for a local smoke test but not for production. A production reference should be a frozen, representative training or validation population with a recorded time window and version.

`monitoring/monitor.py` compares reference and current data using PSI for:

- Numeric features: quantile bins from the reference population
- Categorical features: the union of reference and current categories

The monitor also compares missingness rates for every feature. A feature can alert even when its non-null values have no PSI shift if its availability has degraded.

Severity thresholds:

| PSI | Severity |
|---:|---|
| `< 0.10` | LOW |
| `0.10` to `< 0.25` | MEDIUM |
| `>= 0.25` | HIGH |

Missingness uses the same default MEDIUM/HIGH thresholds (`0.10`/`0.25`) for the absolute change in null rate. These thresholds are configurable under `drift` in `configs/config.yaml`.

Drift is an investigation signal, not an automatic retraining trigger. Pair feature drift with prediction volume, delay rate, calibration, business cost, and data-quality evidence.

## 13. Dataset Versioning and Lineage

Each training run should record:

- Dataset URI or object-store location
- Dataset version or content hash
- Source-system extraction time
- Event-time range
- Row count and delay rate
- Schema and feature version
- Cleaning and validation status
- Training code version
- Model candidate and MLflow run ID
- Threshold and promotion decision

Recommended storage layout for a cloud object store:

```text
raw/vessels/extract_date=YYYY-MM-DD/part-*.parquet
curated/vessels/schema=v1/extract_date=YYYY-MM-DD/part-*.parquet
references/vessels/reference_version=YYYYMMDD/
reports/quality/run_id=.../quality.json
reports/drift/run_id=.../drift.json
```

Use immutable paths for historical inputs. Do not overwrite a reference dataset used by an existing model.

## 14. Training vs Inference Data

Training data includes the `delayed` label and may include additional retrospective fields for analysis. Inference data contains only fields available at request time:

```text
arrival_hour
cargo_volume
berth_wait_minutes
port_congestion
weather
previous_delay_hours
crane_available
event_timestamp (optional)
```

The API validates inference payloads with the `VesselRequest` model and returns a probability plus the thresholded status. It does not accept `delayed` as a required prediction input.

## 15. Privacy and Governance

The current sample contains operational identifiers and vessel-event information. Before production use:

- Classify each field and document data ownership.
- Minimize identifiers sent to the model service.
- Restrict access to raw data, labels, and model artifacts.
- Encrypt data in transit and at rest.
- Define retention and deletion policies.
- Audit access to training data and registry artifacts.
- Avoid logging full request payloads if they contain sensitive operational information.
- Document the business owner for the delay label and model decisions.

## 16. Dataset Acceptance Checklist

Before accepting a new dataset version:

- [ ] Required columns and types are present.
- [ ] Event timestamps parse and have a declared timezone.
- [ ] Event keys are unique or duplicates are explained.
- [ ] Numeric ranges are within the approved contract.
- [ ] Categorical values are mapped to an approved dictionary.
- [ ] The delay label definition matches the business definition.
- [ ] Features are available before the prediction point.
- [ ] Row count and freshness meet the ingestion SLA.
- [ ] Delay rate is reviewed against the reference population.
- [ ] Quality and drift reports are stored with the dataset version.
- [ ] Dataset, feature, code, and model versions are linked in MLflow.

## 17. Local Commands

Inspect the local data contract through the project workflow:

```powershell
python -m src.train
python -m monitoring.monitor `
  --reference data/raw/vessels.csv `
  --current data/raw/vessels.csv
python -m pytest -q
```

For production, replace the local CSV paths with versioned object-store or governed data-platform inputs while keeping the schema and feature contract unchanged.
