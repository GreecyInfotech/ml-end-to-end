# Complete End-to-End Execution Flow

This runbook executes the vessel-delay MLOps platform from raw data validation through training, MLflow promotion, API serving, gateway protection, monitoring, retraining, rollback, and production release.

## 1. Environment Setup

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Recommended Python versions: 3.11 or 3.12.

## 2. Validate the Repository

Run the complete automated test suite:

```powershell
python -m pytest -q
```

The suite covers data validation, drift detection, feature engineering, evaluation, API behavior, gateway behavior, retraining decisions, and observability.

## 3. Validate the Raw Dataset

The default dataset is:

```text
data/raw/vessels.csv
```

Required fields:

```text
vessel_id
event_timestamp
arrival_hour
cargo_volume
berth_wait_minutes
port_congestion
weather
previous_delay_hours
crane_available
delayed
```

Training validates schema, types, nulls, ranges, target values, and timestamps. Invalid data stops the pipeline before model fitting.

## 4. Train Candidate Models

```powershell
python -m src.train
```

The training pipeline:

1. Loads the configured raw dataset.
2. Parses `event_timestamp`.
3. Runs schema and data-quality checks.
4. Cleans duplicates and missing values.
5. Applies shared feature engineering.
6. Calculates the feature-contract hash.
7. Creates a chronological 70% train, 10% calibration, and 20% untouched test split.
8. Runs time-series cross-validation.
9. Trains Logistic Regression, Random Forest, and XGBoost candidates.
10. Tunes thresholds only on calibration data.
11. Evaluates final metrics on the untouched test data.
12. Measures P95 prediction latency.
13. Calculates business cost and slice metrics.
14. Registers candidate runs and models in MLflow.
15. Applies the promotion gate.
16. Promotes the `champion` alias only when the gate passes.
17. Writes local fallback artifacts and metadata.

Generated model artifacts:

```text
models/baseline.joblib
models/random_forest.joblib
models/xgboost.joblib
models/champion.joblib
models/metadata.json
models/production_metadata.json
```

## 5. Inspect MLflow

The local MLflow backend is:

```text
mlruns/mlflow.db
```

Start the local MLflow UI:

```powershell
mlflow ui `
  --backend-store-uri sqlite:///mlruns/mlflow.db `
  --host 127.0.0.1 `
  --port 5000
```

Open:

```text
http://127.0.0.1:5000
```

Registered model:

```text
vessel-delay-classifier
```

Production alias:

```text
champion
```

Promotion requires acceptable recall, business cost, model quality, latency, and feature-contract compatibility. A failed candidate keeps the existing champion active.

## 6. Start the Model API

```powershell
python -m uvicorn api.main:app `
  --host 127.0.0.1 `
  --port 8000
```

API endpoints:

```text
GET  /health
GET  /ready
GET  /metrics
GET  /metrics.json
GET  /sre
POST /predict
```

The API first loads:

```text
models:/vessel-delay-classifier@champion
```

If MLflow is unavailable, it falls back to:

```text
models/champion.joblib
```

Readiness returns HTTP 503 when no model is available or the feature-contract hash does not match.

## 7. Start the ML Gateway

```powershell
$env:MODEL_API_URL = "http://127.0.0.1:8000"
$env:GATEWAY_API_KEY = "local-admin-key"
$env:GATEWAY_REQUIRED_ROLE = "predictor"
$env:GATEWAY_BACKEND_MAX_RETRIES = "2"
$env:GATEWAY_RETRY_BACKOFF_SECONDS = "0.1"

python -m uvicorn gateway.main:app `
  --host 127.0.0.1 `
  --port 8080
```

The gateway provides:

- API-key authentication
- Role-based authorization
- Pydantic request validation
- Sliding-window rate limiting
- Request ID generation and propagation
- OpenTelemetry trace propagation
- Backend routing
- Configurable timeout
- Exponential retry for transient backend failures
- Controlled HTTP 503 fallback
- Structured JSON logs
- Prometheus and SRE metrics

For role-based API keys, use a JSON map stored in a secret manager:

```powershell
$env:GATEWAY_API_KEYS = '{"predict-key":"predictor","admin-key":"admin"}'
```

Unknown keys return `401`. Known keys without the required role return `403`.

## 8. Send a Prediction Through the Gateway

```powershell
$payload = @{
  arrival_hour = 8
  cargo_volume = 1200.0
  berth_wait_minutes = 45.0
  port_congestion = "high"
  weather = "rain"
  previous_delay_hours = 1.5
  crane_available = 1
} | ConvertTo-Json

Invoke-RestMethod `
  http://127.0.0.1:8080/predict `
  -Method Post `
  -Headers @{
    "X-API-Key" = "local-admin-key"
    "X-Request-ID" = "demo-request-001"
  } `
  -ContentType "application/json" `
  -Body $payload
```

The response contains the prediction, probability, threshold, latency, model source, registry metadata, and gateway version.

## 9. Run Data Quality and Drift Monitoring

```powershell
python -m monitoring.monitor `
  --reference data/raw/vessels.csv `
  --current data/raw/vessels.csv
```

Report output:

```text
data/predictions/monitoring_report.json
```

The report includes data quality, PSI drift, missingness drift, unavailable features, and an overall status:

```text
PASS
WARN
ALERT
```

For scheduler or CI enforcement:

```powershell
python -m monitoring.monitor --fail-on-alert
```

Exit code `2` indicates `ALERT`.

## 10. Start Prometheus and Grafana

```powershell
docker compose --profile observability up -d
```

Prometheus:

```text
http://127.0.0.1:9090
```

Grafana:

```text
http://127.0.0.1:3000
```

The provisioned dashboard monitors:

- CPU utilization
- Resident memory
- Rolling throughput
- Error rate
- Availability
- Request rate
- P50, P95, and P99 latency
- Error budget
- SLO burn rate

Optional OTLP tracing:

```powershell
$env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://127.0.0.1:4318/v1/traces"
```

## 11. Preview Retraining Decisions

```powershell
python -m src.retrain `
  --trigger scheduled `
  --reason "Weekly candidate refresh" `
  --dry-run
```

Supported triggers:

- `data_drift`
- `performance_degradation`
- `business_requirement_change`
- `new_data`
- `scheduled`
- `feature_change`
- `label_change`
- `manual`

The decision records dataset row count, dataset SHA-256 fingerprint, feature version, feature-contract hash, label version, business requirements version, recall degradation, business-cost increase, and latency increase.

## 12. Execute Controlled Retraining

```powershell
python -m src.retrain `
  --trigger scheduled `
  --reason "Approved weekly retraining"
```

If monitoring is `ALERT`, retraining requires explicit approval:

```powershell
python -m src.retrain `
  --allow-alert `
  --trigger data_drift `
  --reason "Approved retraining after verified source correction"
```

Audit output:

```text
models/retraining_audit.json
```

Retraining still passes through the normal candidate evaluation and promotion gate. Drift alone never automatically promotes a model.

## 13. Roll Back the Champion

Rollback requires an approved prior MLflow version and a reason:

```powershell
python -c "from src.config import load_config, ROOT; from src.mlflow_registry import rollback_alias; print(rollback_alias(load_config(), ROOT, version='18', reason='Elevated false-negative rate'))"
```

Verify the service after rollback:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/metrics.json
```

## 14. Docker Execution

Build the image:

```powershell
docker compose build
```

Start API and gateway:

```powershell
docker compose up -d api gateway
```

Run training:

```powershell
docker compose --profile jobs run --rm train
```

Run monitoring:

```powershell
docker compose --profile jobs run --rm monitor
```

Start MLflow:

```powershell
docker compose --profile registry up -d mlflow
```

Start the complete observability stack:

```powershell
docker compose --profile observability up -d
```

## 15. Production Release Sequence

1. Run `python -m pytest -q`.
2. Build the container image.
3. Scan and sign the image.
4. Freeze and version the training dataset.
5. Train candidate models.
6. Verify MLflow runs and candidate versions.
7. Verify the `champion` alias.
8. Verify feature-contract hashes.
9. Run quality and drift monitoring.
10. Deploy canary capacity.
11. Verify `/health` and `/ready`.
12. Send a representative prediction through the gateway.
13. Check authentication and authorization behavior.
14. Check CPU, memory, throughput, errors, availability, and P50/P95/P99 latency.
15. Check error budget and SLO burn rate.
16. Expand traffic only after the release is healthy.
17. Roll back the champion alias if model or service behavior is unsafe.
18. Monitor matured labels and realized business cost.

## 16. Production Boundaries

- Do not commit `mlruns/mlflow.db` or model artifacts to Git.
- Use managed PostgreSQL and durable object storage for production MLflow.
- Keep the model API private behind the gateway.
- Store API keys and registry credentials in a secret manager.
- Do not retry non-idempotent operations without an idempotency strategy.
- Treat drift as an investigation signal, not an automatic promotion decision.
- Keep the test set isolated from threshold tuning.
- Preserve request IDs, traces, logs, metrics, model versions, and incident decisions.
