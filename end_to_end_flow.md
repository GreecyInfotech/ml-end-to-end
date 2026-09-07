# Vessel Delay MLOps End-to-End Flow

## 1. System Goal

The platform predicts whether a vessel will be delayed by more than two hours and operates the full lifecycle from governed data to monitored online prediction.

```text
raw data
  -> validation and quality
  -> versioned feature contract
  -> time-aware train/calibration/test
  -> candidate evaluation
  -> MLflow registration
  -> promotion gate
  -> champion alias
  -> HTTP/Kafka serving
  -> observability and drift
  -> guarded retraining or rollback
```

## 2. Training Flow

1. `src.train` reads the configured dataset.
2. Timestamp parsing, schema checks, target checks, type checks, and range checks run.
3. Quality evidence is generated before cleaning.
4. Duplicate handling and approved imputation are applied.
5. `create_features()` applies the shared feature contract.
6. A deterministic feature-contract hash is calculated.
7. Chronological data is split into 70% training, 10% calibration, and 20% untouched test data.
8. Five-fold time-series cross-validation evaluates stability.
9. Logistic Regression, Random Forest, and XGBoost pipelines are fitted.
10. Thresholds are tuned only on calibration data using recall and business cost.
11. Final metrics are calculated on untouched test data.
12. Candidate runs and artifacts are registered in MLflow.
13. Feature version, feature hash, dataset lineage, split sizes, target rate, threshold, and metrics are recorded.
14. The promotion gate selects a candidate or retains the existing champion.
15. Local artifacts are written for fallback and audit.

## 3. Registry and Promotion Flow

```text
candidate run
  -> immutable model version
  -> validation_status=candidate
  -> recall/cost/quality/latency gate
      +--> fail: retain current champion
      +--> pass: set champion alias
```

The API resolves `models:/vessel-delay-classifier@champion`, not a hard-coded numeric version. Rollback changes the alias to a previous approved version and records a reason.

## 4. Feature Consistency Flow

Training and serving call the same feature transformation code. The contract hash is persisted during training and recalculated during API startup.

```text
training feature contract hash
              ==
serving feature contract hash
              |
        MATCH -> ready
     MISMATCH -> HTTP 503
```

This is the primary defense against offline/online feature skew.

## 5. Serving Flow

### HTTP

1. API loads the champion alias from MLflow.
2. On registry failure, it loads the local champion artifact.
3. API checks feature-contract status.
4. `/ready` exposes readiness only when the model and contract are valid.
5. `/predict` validates input, applies shared features, returns a probability, and applies the approved threshold.
6. Request IDs, errors, uptime, latency, model source, and model version are exposed through telemetry.

### Kafka

```text
vessel-events
  -> consumer group
  -> shared prediction callback
  -> vessel-delay-predictions
```

The streaming adapter uses manual commits after successful output publication, giving at-least-once processing. Event IDs and output keys provide downstream idempotency.

## 6. Monitoring Flow

`monitoring.monitor` compares a versioned reference population with current data.

It produces:

- Data-quality status
- PSI for numeric and categorical features
- Missingness-rate drift
- Feature sample counts
- Unavailable feature status
- High/medium drift summaries
- Overall `PASS`, `WARN`, or `ALERT`

`--fail-on-alert` returns exit code `2` for scheduler integration.

## 7. Retraining and Improvement Flow

```text
monitor
  -> quality/drift investigation
  -> freeze dataset version
  -> guarded retraining
  -> candidate evaluation
  -> MLflow version registration
  -> promotion gate
  -> champion update or retention
  -> matured-label monitoring
```

`src.retrain` blocks on `ALERT` unless an operator provides `--allow-alert` and a reason. Each run writes a retraining audit file.

## 8. Runtime and Failure Boundaries

| Failure | Behavior |
|---|---|
| Invalid training data | Training stops before fitting |
| Feature-contract mismatch | API readiness fails with HTTP 503 |
| MLflow unavailable | Local champion fallback is attempted |
| No model available | `/ready` and `/predict` return HTTP 503 |
| Prediction failure | API returns HTTP 503 and logs the failure |
| High drift | Monitoring alerts; no automatic promotion |
| Retraining alert state | Retraining blocked unless explicitly approved |
| Kafka message failure | Do not commit offset; retry or dead-letter |
| Challenger gate failure | Existing champion remains active |

## 9. Container and Cloud Flow

The same application image runs as:

```text
api     -> online service
train   -> controlled training job
monitor -> scheduled quality/drift job
mlflow  -> local registry service
```

Cloud mappings:

- Azure: Container Apps, Azure ML, Blob Storage, PostgreSQL, Event Hubs Kafka, Key Vault, Azure Monitor.
- AWS: ECS/Fargate, Batch, S3, RDS PostgreSQL, MSK, Secrets Manager, CloudWatch.
- GCP: Cloud Run, Vertex AI, GCS, Cloud SQL, managed Kafka, Secret Manager, Cloud Monitoring.

## 10. Operational Release Sequence

```text
1. Run tests and build the image.
2. Scan and sign the image.
3. Train candidates on a frozen dataset.
4. Verify MLflow versions and champion alias.
5. Verify feature-contract hash.
6. Run monitoring against the reference population.
7. Deploy canary capacity.
8. Verify /health, /ready, /metrics, and a representative prediction.
9. Verify error rate, latency, drift, and consumer lag.
10. Expand traffic or rollback the champion alias.
11. Observe matured labels and realized business cost.
```

## 11. Final Production Boundaries

- Model registration is not approval.
- Drift is not an automatic retraining decision.
- The test set is never used for threshold tuning.
- The local fallback is an availability mechanism, not a substitute for a durable registry.
- Kafka output is at least once and requires idempotent consumers.
- Process-local metrics must be exported to a centralized observability system.
- Cloud deployment requires provider credentials, regions, networking, secrets, and managed-service configuration.
