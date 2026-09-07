# Vessel Delay MLOps User Manual

## 1. Purpose

This project predicts whether a vessel will be delayed by more than two hours. It includes data validation, feature engineering, time-aware model training, MLflow experiment tracking and registry promotion, FastAPI inference, Kafka streaming support, drift monitoring, rollback, guarded retraining, and cloud migration templates.

The supplied CSV is synthetic and intended for local evaluation. Replace it with governed operational data before production use.

## 2. Repository Layout

| Path | Purpose |
|---|---|
| `api/main.py` | FastAPI service, probes, metrics, prediction, and feature-contract checks |
| `src/train.py` | Training, evaluation, registration, and promotion |
| `src/retrain.py` | Alert-aware retraining entry point and audit record |
| `src/feature_engineering.py` | Shared offline/online feature transformation |
| `src/feature_store.py` | Versioned feature contract and deterministic hash |
| `src/data_validation.py` | Schema, target, null, type, and range checks |
| `src/data_quality.py` | Quality evidence and batch status |
| `src/drift.py` | PSI and missingness drift detection |
| `src/mlflow_registry.py` | MLflow runs, versions, aliases, rollback, and loading |
| `streaming/kafka_predictor.py` | Optional Kafka prediction adapter |
| `monitoring/monitor.py` | Quality, drift, and alert report generation |
| `configs/config.yaml` | Runtime, model, business, gate, MLflow, and drift settings |
| `data/raw/vessels.csv` | Default raw dataset |
| `data/predictions/monitoring_report.json` | Latest monitoring report |
| `models/champion.joblib` | Local production fallback |
| `models/metadata.json` | Latest training and registry metadata |
| `models/production_metadata.json` | Current production baseline |
| `mlruns/mlflow.db` | Local MLflow SQLite backend |
| `deploy/` | Azure, AWS, and GCP deployment templates |
| `tests/` | Automated regression tests |

## 3. Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Python 3.11 or 3.12 is recommended. Docker is optional for local Python execution and required for container execution.

## 4. Complete Local Workflow

```powershell
python -m pytest -q
python -m src.train
python -m monitoring.monitor --reference data/raw/vessels.csv --current data/raw/vessels.csv
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open API documentation at `http://127.0.0.1:8000/docs`.

## 5. Training and Promotion

`python -m src.train`:

1. Reads and parses the configured dataset.
2. Validates schema, target, types, ranges, and timestamps.
3. Generates quality evidence and cleans data.
4. Applies the shared feature contract.
5. Creates a chronological 70% train, 10% calibration, and 20% untouched test split when timestamps exist.
6. Runs time-series cross-validation, or stratified fallback without timestamps.
7. Trains Logistic Regression, Random Forest, and XGBoost candidates.
8. Tunes each threshold on calibration data using business costs and the recall floor.
9. Evaluates final metrics on untouched test data.
10. Registers every candidate as an immutable MLflow model version.
11. Applies the promotion gate.
12. Updates the `champion` alias only when approval passes.
13. Writes local fallback artifacts and feature-contract metadata.

Default policy:

| Setting | Default |
|---|---:|
| Minimum recall | `0.85` |
| Maximum P95 latency | `200 ms` |
| False-positive cost | `1.0` |
| False-negative cost | `5.0` |

## 6. Feature Contract and Data Contract

Required training columns:

```text
vessel_id,event_timestamp,arrival_hour,cargo_volume,berth_wait_minutes,port_congestion,weather,previous_delay_hours,crane_available,delayed
```

The feature contract contains numeric features, categorical features, and derived rules. Its SHA-256 hash is stored with the model and checked by the API.

Readiness fails with HTTP 503 when a known feature-contract mismatch exists. This prevents a model from serving with a different feature definition than the one used during training.

## 7. API

### Health and readiness

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

`/health` reports model source, registry version, feature version, and feature-contract status. `/ready` requires a loaded model and matching feature contract.

### Prediction

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

Invoke-RestMethod http://127.0.0.1:8000/predict `
  -Method Post -ContentType "application/json" -Body $payload
```

The service returns a validated positive-class probability, thresholded prediction, model source, model version, and latency. It loads `models:/vessel-delay-classifier@champion` first and falls back to `models/champion.joblib` if the registry is unavailable.

### Runtime metrics

```powershell
Invoke-RestMethod http://127.0.0.1:8000/metrics
```

Reports uptime, request count, errors, error rate, p50/p95/p99 latency, model source, loaded state, and registry version. Metrics are process-local unless exported by the deployment platform.

Every response includes an `X-Request-ID` header.

## 8. MLflow

Start the local UI:

```powershell
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --host 127.0.0.1 --port 5000
```

Use environment variables for shared registries:

```powershell
$env:MLFLOW_TRACKING_URI = "https://<mlflow-server>"
$env:MLFLOW_REGISTRY_URI = "postgresql://<user>:<password>@<host>:5432/mlflow"
$env:MLFLOW_ENABLED = "true"
```

The registered model is `vessel-delay-classifier`; the serving alias is `champion`. Numeric versions are immutable. Rollback moves the alias to a previously approved version.

## 9. Monitoring and Drift

```powershell
python -m monitoring.monitor `
  --reference data/raw/vessels.csv `
  --current data/raw/vessels.csv
```

Reports are written to `data/predictions/monitoring_report.json` with quality status, PSI distribution drift, missingness drift, unavailable features, timestamps, and overall `PASS`, `WARN`, or `ALERT` status.

Fail a scheduled job on alert:

```powershell
python -m monitoring.monitor --fail-on-alert
```

Exit code `2` indicates `ALERT`.

## 10. Guarded Retraining and Rollback

```powershell
python -m src.retrain --reason "Scheduled weekly retraining"
```

Retraining is blocked when the monitoring report is `ALERT` unless explicitly approved:

```powershell
python -m src.retrain `
  --allow-alert `
  --reason "Approved source-system correction"
```

Audit output is written to `models/retraining_audit.json`.

Rollback is performed by moving the MLflow `champion` alias to an approved version with `rollback_alias()`; a reason is required and recorded.

## 11. Docker Architecture

The Docker image supports four Compose roles:

| Service | Command | Purpose |
|---|---|---|
| `api` | Uvicorn | Long-running HTTP service |
| `train` | `python -m src.train` | One-shot training job |
| `monitor` | `python -m monitoring.monitor` | One-shot monitoring job |
| `mlflow` | MLflow server | Optional local registry UI |

Commands:

```powershell
docker compose build
docker compose --profile jobs run --rm train
docker compose up -d api
docker compose --profile jobs run --rm monitor
docker compose --profile registry up -d mlflow
```

The image runs as a non-root user. Named volumes persist MLflow, models, and monitoring reports.

## 12. Kafka Streaming

The optional adapter consumes JSON events from an input topic and publishes prediction envelopes to an output topic. It uses manual commits for at-least-once delivery.

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
```

Production requirements include TLS/SASL or managed identity, stable consumer groups, dead-letter handling, event IDs for idempotency, consumer-lag monitoring, and model version in each output event.

## 13. Cloud Migration

The same image and environment contract maps to:

| Role | Azure | AWS | GCP |
|---|---|---|---|
| API | Container Apps | ECS/Fargate | Cloud Run |
| Training | Container Apps Job / Azure ML | Batch / ECS task | Cloud Run Job / Vertex AI |
| Registry artifacts | Blob Storage | S3 | GCS |
| Registry database | Azure PostgreSQL | RDS PostgreSQL | Cloud SQL PostgreSQL |
| Streaming | Event Hubs Kafka endpoint | MSK | Managed Kafka |
| Secrets | Key Vault | Secrets Manager | Secret Manager |

Templates are under `deploy/`. No cloud resources are created by local commands.

## 14. Production Hardening

- Replace synthetic data with governed event ingestion.
- Use managed MLflow, durable artifacts, and backups.
- Use managed identity/task roles/service accounts.
- Add centralized metrics, logs, traces, and alert ownership.
- Use private networking and TLS for control-plane services.
- Add image signing, vulnerability scanning, CI/CD, canary rollout, and rollback testing.
- Monitor matured labels, business cost, feature drift, model drift, latency, and streaming lag.
