# Train, Validation, and Test Strategy for Production ML

## 1. Purpose

This document defines how vessel-delay models are trained, calibrated, evaluated, promoted, and monitored without contaminating the final test evidence.

The strategy is designed for a time-dependent operational prediction problem. A model must perform on future vessel events, not only on randomly mixed historical rows.

## 2. Prediction Contract

- Prediction unit: one vessel arrival event.
- Target: `delayed`, where `1` means delay greater than two hours and `0` means otherwise.
- Prediction output: delay probability plus a business decision based on an approved threshold.
- Primary operational concern: missed delays are more expensive than unnecessary delay alerts.
- Default false-positive cost: `1.0`.
- Default false-negative cost: `5.0`.
- Minimum recall gate: `0.85`.
- Maximum P95 prediction latency: `200 ms`.

The threshold is a business decision and is not assumed to be `0.50`.

## 3. Dataset Eligibility Before Splitting

A dataset version must pass these checks before it is split:

1. Required columns are present.
2. `vessel_id` identifies a unique arrival event or duplicates are explicitly resolved.
3. `event_timestamp` parses successfully and has a declared timezone.
4. The `delayed` target contains only `0` and `1` for training data.
5. Numeric values satisfy approved ranges.
6. Features are available at the prediction timestamp.
7. Data quality and freshness meet the ingestion SLA.
8. The source extract, schema, feature version, and code version are recorded.

A failed contract check stops training. Records needing operational investigation should be quarantined rather than silently included.

## 4. Primary Time-Aware Split

When `event_timestamp` exists, `src.train.split_data()` sorts records chronologically and applies:

```text
first 70%  -> training set
next 10%   -> calibration set
last 20%   -> final test set
```

The chronological test set represents the most recent future-like observations available in the dataset. It is not used for model fitting, threshold selection, or candidate selection.

The split boundary must be recorded with:

- Dataset version
- Source extract ID
- Earliest and latest timestamp in each partition
- Row count and positive-class rate
- Feature version
- Training code version
- Random seed, if a fallback split is used

### Why random splitting is not primary

Randomly mixing vessel events can put records from the same operating regime, time period, or future distribution into both training and test data. This can produce optimistic metrics that do not represent deployment performance.

## 5. Fallback Split Without Timestamps

If no `event_timestamp` column is available, the implementation uses stratified random splitting:

- 80% development data and 20% test data.
- The development data is split again into approximately 70% training and 10% calibration proportions relative to the full dataset.
- `random_state=42` provides reproducibility.
- Stratification preserves the target class proportion where possible.

This fallback is weaker than a temporal split. A production source should provide an event timestamp or another reliable ordering key.

## 6. Cross-Validation Strategy

Cross-validation is performed only on the training partition.

### With timestamps

`TimeSeriesSplit(n_splits=5)` preserves ordering within each fold. Each fold trains on earlier observations and validates on later observations.

### Without timestamps

`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)` is used to preserve class proportions.

Each candidate records:

- Mean and standard deviation of F1
- Mean ROC-AUC
- Mean PR-AUC

Cross-validation estimates training stability. It does not replace the untouched final test set.

## 7. Preprocessing and Leakage Control

Every candidate is a single scikit-learn `Pipeline` containing preprocessing and the estimator. This ensures imputers, scalers, and encoders are fitted inside each training fold rather than on the full dataset.

Preprocessing rules:

- Numeric features: median imputation and standardization.
- Categorical features: most-frequent imputation and one-hot encoding.
- Unknown inference categories: ignored by the encoder.

Leakage review must confirm that:

- `delayed` is never a feature.
- `vessel_id` is not a feature.
- `previous_delay_hours` contains only history known before the current event.
- `berth_wait_minutes` is known at the declared prediction point.
- No post-outcome operational status is included.
- Feature engineering uses only information available at prediction time.

## 8. Model Training

The current benchmark trains three candidate families with the same feature pipeline:

- Logistic Regression
- Random Forest
- XGBoost

Random Forest uses balanced class weights, configurable tree depth, minimum leaf size, and feature sampling. XGBoost uses configurable histogram training, row and feature subsampling, L2 regularization, class weighting, and child-weight controls. These settings are versioned in `configs/config.yaml` and recorded with each MLflow candidate.

Logistic Regression is the explicit baseline. The reusable factory is in `src/baseline.py`, and each training run persists:

- `models/baseline.joblib`: fitted preprocessing and Logistic Regression pipeline.
- `models/baseline_metadata.json`: baseline test metrics, project version, feature version, and validation strategy.

The baseline is interpretable and stable enough to serve as the first comparison point for more complex challengers. It is still evaluated with the same temporal split, calibration procedure, and release gates as the other candidates.

For each candidate:

1. Fit on the training partition.
2. Generate calibration probabilities.
3. Tune the decision threshold on calibration data.
4. Generate final probabilities for the untouched test partition.
5. Calculate test metrics at the selected threshold.
6. Log parameters, metrics, tags, and the model artifact to MLflow.

The test partition must not be used to choose the candidate or threshold.

## 9. Threshold Calibration

`src.evaluation.tune_threshold()` evaluates thresholds from `0.10` through `0.90` in increments of `0.01`.

A threshold is eligible when its calibration recall meets the configured minimum recall. Among eligible thresholds, the strategy selects the lowest business cost and then prefers higher recall.

The selected threshold is stored with:

- Model name
- Dataset version
- MLflow run
- Production metadata
- API model metadata

Threshold tuning must be repeated when class balance, business costs, feature definitions, or operational consequences change.

## 10. Final Test Evaluation

Final test evaluation uses the model fitted on the training partition and the threshold selected from calibration data. It reports:

- Accuracy
- Precision
- Recall
- F1
- ROC-AUC
- PR-AUC
- Brier score
- Confusion matrix counts: TN, FP, FN, TP
- False-positive rate
- False-negative rate
- Business cost
- P95 prediction latency
- Operational slice metrics

The test result is the primary release evidence for a candidate. It must be retained as an immutable report and linked to the registered model version.

## 11. Slice Evaluation

The implementation evaluates these slices on the test partition:

- High port congestion
- Rain weather
- Peak arrival hours: 7-10 and 17-20
- High berth wait: more than 60 minutes
- All test rows

Each slice records row count and the same core classification metrics. A slice with no rows or only one target class is reported as `insufficient_class_variation` rather than producing misleading AUC values.

Production review should add slices for port, vessel type, route, season, and other business-critical populations when those fields are available and approved for use.

## 12. Model Promotion Gate

If no production baseline exists, the first champion is selected from candidates meeting the recall floor by:

1. Lowest business cost
2. Highest F1 as the tie-breaker

For later candidates, `promotion_gate()` requires:

- Candidate recall meets the configured minimum.
- Candidate F1 is no worse than production.
- Candidate ROC-AUC is no worse than production.
- Candidate PR-AUC is no worse than production.
- Candidate business cost is no higher than production.
- Candidate P95 latency is within the configured SLA.

A rejected challenger is still registered for audit and analysis, but the production model and `champion` alias remain unchanged.

## 13. Minimum Release Criteria

A model release should be approved only when all of the following are true:

- [ ] Data contract passes.
- [ ] No unresolved leakage finding exists.
- [ ] Cross-validation results are stable enough for the use case.
- [ ] Calibration threshold meets the recall requirement.
- [ ] Final test metrics meet the promotion gate.
- [ ] P95 latency meets the SLA under the target runtime.
- [ ] Required slices have sufficient volume and acceptable behavior.
- [ ] Model artifact loads successfully from the intended registry.
- [ ] Rollback model and metadata are available.
- [ ] Dataset, code, feature, model, and threshold versions are linked.
- [ ] Business owner approves the operating point.

## 14. Retraining Strategy

Retraining is scheduled by a combination of time and evidence, not by drift alone. The controlled entry point is `python -m src.retrain`; use `--dry-run` to review the decision before executing training.

Trigger investigation when one or more conditions occur:

- PSI reaches MEDIUM or HIGH for an important feature.
- Data-quality status is not `PASS`.
- Production delay rate changes materially from the reference population.
- Recall, business cost, calibration, or latency degrades.
- Port operations, weather patterns, berth policy, or source systems change.
- A new label definition or prediction horizon is introduced.

The implemented trigger matrix covers data drift, model performance degradation, business requirement changes, new data, scheduled retraining, feature changes, and label changes. Every decision records the trigger evidence, dataset fingerprint, feature contract, label version, and business requirements version in `models/retraining_audit.json`.

Before retraining:

1. Confirm the data issue is real and not an ingestion defect.
2. Freeze the new dataset version.
3. Re-run contract and quality checks.
4. Review feature availability and leakage.
5. Train candidates using the same split policy.
6. Compare with the current production baseline.
7. Promote only after the gate passes.

## 15. Reproducibility and Auditability

Every training run should retain:

- Dataset URI and immutable version
- Dataset hash or source extract ID
- Split boundaries and counts
- Feature version
- Configuration snapshot
- Dependency lock or image digest
- Random seed
- Candidate parameters
- Cross-validation results
- Calibration threshold
- Final test metrics
- Slice metrics
- Latency environment
- MLflow run ID and model version
- Promotion gate result

The local project writes model and metadata files under `models/` and registers candidates in MLflow. A production deployment should store these artifacts in durable, access-controlled storage.

## 16. Limitations of the Current Local Strategy

The repository implements a strong local evaluation workflow, but production adoption still requires:

- A governed event-time source instead of synthetic CSV data.
- A versioned reference population for drift.
- Load and concurrency testing beyond single-row latency measurements.
- Monitoring of live labels once delayed outcomes mature.
- Business approval of feature availability and false-negative cost.
- A managed MLflow backend and artifact store.
- Automated release evidence retention and rollback procedures.

## 17. Local Verification Commands

```powershell
python -m pytest -q
python -m src.train
python -m monitoring.monitor `
  --reference data/raw/vessels.csv `
  --current data/raw/vessels.csv
```

Inspect `models/metadata.json`, `models/production_metadata.json`, and the MLflow `champion` alias after training. The final test metrics should be reviewed before treating a candidate as production-ready.
