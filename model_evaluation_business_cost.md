# Model Evaluation, Production Selection, and Business Cost

## 1. Decision Summary

The current trained candidates produce this final test comparison:

| Model | Threshold | Recall | Precision | F1 | ROC-AUC | PR-AUC | Business cost | P95 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0.23 | 0.875 | 0.516 | 0.649 | 0.804 | 0.697 | 508 | 4.7 ms |
| Random Forest | 0.28 | 0.866 | 0.500 | 0.634 | 0.790 | 0.656 | 539 | 31.3 ms |
| XGBoost | 0.22 | 0.812 | 0.514 | 0.630 | 0.781 | 0.669 | 599 | 4.0 ms |

**Production decision: Logistic Regression.** It meets the minimum recall requirement, has the lowest business cost, and leads the candidates on F1, ROC-AUC, and PR-AUC. Random Forest is a valid registered challenger but costs more and is slower. XGBoost does not meet the configured recall floor of `0.85`.

These values come from the latest local training run and should be regenerated for every dataset and code version.

## 2. What Is Evaluated

Each candidate is evaluated on the untouched chronological test set after:

1. Validation and cleaning.
2. Feature engineering.
3. Training on the first 70% of events.
4. Threshold calibration on the next 10% of events.
5. Final test scoring on the last 20% of events.

The test set is not used to fit the model or choose the operating threshold.

## 3. Candidate Metrics

The evaluation reports:

- Accuracy
- Precision
- Recall
- F1
- ROC-AUC
- PR-AUC
- Brier score
- True negatives, false positives, false negatives, and true positives
- False-positive rate and false-negative rate
- Business cost
- P95 prediction latency
- Slice metrics for high congestion, rain, peak hour, and high berth wait

ROC-AUC measures ranking quality across thresholds. PR-AUC is particularly useful when the delayed class is not balanced. Neither metric alone selects the production threshold.

## 4. Threshold Optimization

`src.evaluation.tune_threshold()` tests thresholds from `0.10` through `0.90` in increments of `0.01`.

For each threshold:

```text
probability >= threshold -> predicted delayed (1)
probability < threshold  -> predicted on time (0)
```

A threshold is eligible only when calibration recall is at least the configured minimum. Among eligible thresholds, the implementation selects:

1. Lowest business cost.
2. Highest recall as the tie-breaker.

The current minimum recall is `0.85`, so the selected threshold is intentionally lower than the conventional `0.50` when necessary to catch more delayed vessels.

Threshold tuning is performed on calibration probabilities, not test probabilities. The selected threshold is stored in model metadata and MLflow parameters.

## 5. Business Cost

The system uses a cost matrix based on operational consequences:

| Actual / Predicted | On time | Delayed |
|---|---:|---:|
| On time | 0 | False positive cost |
| Delayed | False negative cost | 0 |

The implementation calculates:

$$
\text{business cost} = (FP \times C_{FP}) + (FN \times C_{FN})
$$

The default configuration is:

```yaml
business:
  false_positive_cost: 1.0
  false_negative_cost: 5.0
```

This means missing a delayed vessel is five times more expensive than raising an unnecessary delay alert. The cost values must be agreed with operations and should be recalibrated when staffing, service-level penalties, or customer impact changes.

## 6. How to Choose the Production Model

The model-selection policy is ordered as follows:

### First production model

When no production baseline exists:

1. Keep candidates whose final recall meets the minimum floor.
2. If none meet the floor, retain all candidates as a fallback selection policy and record the gate limitation.
3. Select the lowest business cost.
4. Break a cost tie with higher F1.

### Challenger promotion

When a production baseline exists, the challenger must satisfy all of these constraints:

- Recall is at least the configured minimum.
- F1 is no worse than the production model.
- ROC-AUC is no worse than the production model.
- PR-AUC is no worse than the production model.
- Business cost is no higher than the production model.
- P95 latency is within the configured SLA.

A failed challenger remains registered for audit and analysis. The `champion` alias and local production fallback remain unchanged.

## 7. Interpreting the Current Decision

### Logistic Regression

- Best overall ranking metrics in the current run.
- Lowest business cost: `508`.
- Recall: `0.875`, above the `0.85` floor.
- Lowest operational complexity and fastest enough for the current SLA.
- Selected as champion and persisted as `models/champion.joblib` and `models/baseline.joblib`.

### Random Forest

- Recall meets the floor at `0.866`.
- Business cost is higher at `539`.
- P95 latency is materially higher than Logistic Regression in this run.
- Useful challenger when nonlinear interactions justify the additional complexity.

### XGBoost

- Fast inference in the current run.
- Recall is `0.812`, below the `0.85` floor.
- Business cost is highest at `599`.
- Registered for comparison but not eligible for promotion under the current policy.

## 8. When to Change the Threshold

Do not change the threshold directly in the API without a new evaluation record. Recalibrate when:

- False-negative or false-positive costs change.
- The delay label definition changes.
- The delay rate shifts materially.
- The prediction horizon or decision workflow changes.
- Calibration or production recall degrades.
- A new model version is promoted.

A threshold change requires a new calibration report, final test report, business-owner approval, and model metadata update.

## 9. Monitoring After Promotion

Track the following after deployment:

- Production prediction volume
- Delayed prediction rate
- Matured-label recall and precision
- False-positive and false-negative counts
- Realized business cost
- Probability calibration and Brier score
- P50/P95/P99 latency
- Feature quality and PSI drift
- Slice-level recall and business cost

A drift alert alone should not trigger automatic promotion. Investigate data quality, label delay, operational changes, and realized business cost first.

## 10. Reproducible Commands

```powershell
python -m src.train
python -m pytest -q
```

Review these outputs after training:

- `models/metadata.json`
- `models/production_metadata.json`
- `models/baseline_metadata.json`
- `models/random_forest_metadata.json`
- `models/xgboost_metadata.json`
- MLflow registered model `vessel-delay-classifier`
- MLflow alias `champion`

## 11. Governance Rules

- Never select a model using test performance alone without the configured business and reliability gates.
- Never tune a threshold on the final test set.
- Record the cost assumptions with every model version.
- Keep rejected challengers immutable for auditability.
- Preserve the previous champion for rollback.
- Revisit cost weights with the business owner when operational consequences change.
