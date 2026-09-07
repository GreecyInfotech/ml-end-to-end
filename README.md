# Vessel Delay MLOps — Production Evaluation Edition v2

A production-oriented classical ML system for predicting whether a vessel will be delayed by more than 2 hours.

## What v2 adds

- Logistic Regression, Random Forest and XGBoost benchmark
- Explicit Logistic Regression baseline artifact and metadata
- Production-configured Random Forest and XGBoost challenger artifacts
- Time-aware train / calibration / untouched test split when `event_timestamp` exists
- 5-fold/time-series cross-validation
- Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC, Brier score
- Confusion matrix, FP/FN counts and configurable business cost
- Threshold optimization on a calibration set — test set remains untouched
- Slice evaluation: congestion, rain, peak hour, high berth wait
- P95 prediction latency measurement
- Data-quality gates and schema/range checks
- PSI-based numerical/categorical drift monitoring
- Champion vs Challenger promotion gate
- Explicit production baseline so retraining cannot silently overwrite a production model
- Optional MLflow Model Registry registration through `MLFLOW_REGISTRY_URI`
- FastAPI `/health`, `/ready`, `/metrics`, `/predict`
- Request IDs and basic reliability/latency metrics
- Prometheus metrics, Grafana SRE dashboard, JSON structured logs, optional OTLP traces, SLO/error-budget endpoint, and incident-response runbook
- ML Gateway authentication, role authorization, validation, rate limiting, routing, timeouts, retries, fallback, and request tracing
- Evidence-based retraining triggers for drift, performance degradation, new data, schedules, business changes, feature changes, and label changes
- Larger 5,000-row synthetic dataset for realistic local testing

## Project documentation

- [Dataset design](dataset_design.md): schema, target, feature availability, validation, drift, lineage, and production ingestion guidance.
- [Train/validation/test strategy](train_validation_test_strategy.md): temporal splitting, calibration, cross-validation, test isolation, promotion gates, and retraining policy.
- [Model evaluation and business cost](model_evaluation_business_cost.md): production model selection, threshold optimization, cost formula, and promotion decision.
- [MLflow experiment tracking](mlflow_experiment_tracking.md): run lineage, registry versions, champion promotion, remote configuration, and safeguards.
- [MLflow model registry and versioning](model_registry_versioning.md): immutable versions, aliases, promotion, rollback, and serving resolution.
- [Production monitoring and observability](monitoring_observability.md): service telemetry, drift alerts, dashboards, and incident response.
- [Rollback, retraining, and Kafka streaming](recovery_retraining_kafka.md): recovery procedures, guarded retraining, continuous improvement, and real-time prediction topics.
- [Feature-store consistency](feature_store_consistency.md): feature contracts, offline/online parity, readiness checks, and SRE release gates.
- [Cloud migration guide](cloud_migration.md): local MLOps mappings and deployment sequence for Azure, AWS, and GCP.
- [Enterprise MLOps capstone](enterprise_mlops_capstone.md): architecture, governance, SRE, cloud portability, interview answers, and final validation evidence.
- [ML gateway architecture](ml_gateway_architecture.md): API orchestration, authentication, rate limiting, routing, and cloud edge mapping.
- [User manual](usermanual.md): setup, training, API, monitoring, MLflow, Docker, and troubleshooting.
- [End-to-end flow](end_to_end_flow.md): training, promotion, serving, monitoring, and deployment flow.
- [Complete end-to-end execution flow](src/end_to_end_execution_flow.md): executable local and production steps from environment setup through release, monitoring, retraining, and rollback.
- [YouTube course series](youtube/README.md): 10 source-anchored episodes with business framing, architecture walkthroughs, live demos, and production takeaways.

## Architecture

```text
Raw Port/Vessel Data
        |
        v
Data Contract + Quality Checks
        |
        v
Cleaning + Feature Engineering
        |
        v
Time-aware Train / Calibration / Test
        |
        +-----------------------------+
        |                             |
        v                             v
   LR / RF / XGBoost            Drift Reference
        |                             |
        v                             v
 Cross Validation              PSI Monitoring
        |
        v
Threshold Optimization
        |
        v
Business Cost + Recall + AUC + PR-AUC
        |
        v
Slice + Calibration + Latency Tests
        |
        v
Champion / Challenger Gate
        |
   +----+----+
   |         |
 PASS       FAIL
   |         |
   v         v
Promote    Keep v1
   |
   v
FastAPI
   |
   v
Production Monitoring
(Data Quality + Drift + Performance + Latency)
```

## Quick start

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m src.train
python -m monitoring.monitor
uvicorn api.main:app --reload
```

API: `http://127.0.0.1:8000/docs`

MLflow tracking UI:

```bash
mlflow ui --host 127.0.0.1 --port 5000
```

## Production model gate

A candidate must satisfy the configured recall floor, avoid increasing business cost, remain no worse on ROC-AUC/PR-AUC and F1 than the current production baseline, and meet the P95 latency SLA.

If no production baseline exists, the first champion is selected from models meeting the recall floor by lowest business cost and then F1.

## Drift monitoring

Run:

```bash
python -m monitoring.monitor --reference data/raw/vessels.csv --current data/raw/vessels.csv
```

PSI is used as an alerting signal:

- `< 0.10`: LOW
- `0.10–0.25`: MEDIUM
- `>= 0.25`: HIGH

These values are starting points, not universal truths. Calibrate them against historical behavior and business impact.

## MLflow Registry

Local file tracking is used by default. For a real Model Registry, provide a database-backed MLflow registry URI, for example through `MLFLOW_REGISTRY_URI`. MLflow supports model versions, lineage, aliases and tags for controlled promotion. See the official MLflow documentation.

## Important production hardening

Before internet-facing deployment:

- Replace synthetic CSV data with governed port DB/event-stream ingestion.
- Use a versioned reference dataset for drift rather than the live dataset itself.
- Persist model/data/feature versions and lineage.
- Add authentication, HTTPS, secrets management and centralized logs.
- Export metrics to Prometheus/Grafana or your existing observability platform.
- Add CI/CD, container scanning and dependency pinning.
- Use shadow/canary deployment before full promotion.
- Store production models in an enterprise MLflow registry/object store rather than only local files.
- Retrain only after root-cause analysis of drift and successful candidate validation.

## MLflow Model Registry Strategy (v2.1)

The production strategy uses MLflow Tracking + Model Registry with an alias-based deployment model:

```text
Train LR/RF/XGBoost
      -> evaluate -> threshold/business gate
      -> register every candidate as an immutable model version
      -> approve only the selected challenger
      -> champion alias points to approved production version
      -> FastAPI loads models:/vessel-delay-classifier@champion
```

### Local MLflow registry

The default local backend is a SQLite database persisted under `mlruns/mlflow.db`:

```bash
python -m src.train
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --host 127.0.0.1 --port 5000
```

The training pipeline registers each candidate, records metrics/tags, and moves the `champion` alias only when the promotion gate passes. If a challenger fails, the existing champion remains active and the local `models/champion.joblib` is preserved as a fallback.

### Production registry

For a shared production environment, set:

```bash
export MLFLOW_TRACKING_URI=https://<mlflow-server>
export MLFLOW_REGISTRY_URI=postgresql://<user>:<password>@<host>:5432/mlflow
```

Use object storage for model artifacts (for example S3/Azure Blob/GCS) and a managed/HA MLflow deployment. Do not commit `mlruns/` or database files to Git.

### Model promotion

The registry uses:

- Registered model: `vessel-delay-classifier`
- Production alias: `champion`
- Version tags: validation status, feature version, project version, threshold, F1, recall, business cost
- Candidate versions are immutable; promotion changes the alias, not the model artifact.

### API behavior

At startup the API attempts to load:

```text
models:/vessel-delay-classifier@champion
```

If the registry is unavailable, it falls back to `models/champion.joblib` so the service can remain available. `/health` and `/ready` expose the model source and registry version when available.

### Important production rule

Registering a model is not the same as approving it. The pipeline evaluates technical quality, business cost, threshold, slice behavior, and latency before assigning the production alias.
