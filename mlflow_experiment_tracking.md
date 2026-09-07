# Production ML Pipeline Engineering with MLflow

## 1. Purpose

MLflow provides the experiment, artifact, model-version, and promotion record for the vessel-delay pipeline. The source model files and JSON metadata remain useful local fallbacks, while MLflow is the authoritative registry when enabled.

The pipeline separates:

```text
experiment run -> candidate model version -> validation evidence -> approved champion alias
```

Registering a candidate does not approve it. Approval occurs only when the promotion gate passes and the `champion` alias is updated.

## 2. MLflow Resources

| Resource | Default value | Purpose |
|---|---|---|
| Experiment | `vessel-delay-prediction` | Groups training runs |
| Registered model | `vessel-delay-classifier` | Stores immutable model versions |
| Production alias | `champion` | Points to the approved version |
| Tracking backend | `sqlite:///mlruns/mlflow.db` | Stores runs and metadata locally |
| Artifact location | Local MLflow artifact path | Stores logged model pipelines |

The configuration is in `configs/config.yaml`. Environment variables override the tracking and registry URIs:

- `MLFLOW_TRACKING_URI`
- `MLFLOW_REGISTRY_URI`
- `MLFLOW_ENABLED`

## 3. What Each Run Records

For every candidate, the training pipeline creates a run named:

```text
candidate-LogisticRegression
candidate-RandomForest
candidate-XGBoost
```

Parameters include:

- Model name
- Selected decision threshold
- False-positive cost
- False-negative cost
- Cross-validation fold count

Metrics include:

- Accuracy, precision, recall, F1
- ROC-AUC, PR-AUC, and Brier score
- Confusion counts and error rates
- Business cost
- P95 latency
- Cross-validation means and variation

Run tags include:

- Validation strategy: `time_based` or `stratified`
- Dataset row count
- Training, calibration, and test row counts
- Dataset target rate
- Data-quality status
- Feature version
- Project version
- Lifecycle: `candidate`

Model-version tags additionally include validation status, model name, feature version, project version, threshold, business cost, F1, and recall.

## 4. Local Workflow

Train and register all candidates:

```powershell
python -m src.train
```

Start the local MLflow UI:

```powershell
mlflow ui `
  --backend-store-uri sqlite:///mlruns/mlflow.db `
  --host 127.0.0.1 `
  --port 5000
```

Open `http://127.0.0.1:5000` and inspect:

1. Experiment `vessel-delay-prediction`.
2. Candidate runs and their metrics.
3. Registered model `vessel-delay-classifier`.
4. Model-version tags and validation status.
5. The version assigned to alias `champion`.

The API loads `models:/vessel-delay-classifier@champion` when available and falls back to `models/champion.joblib` when the registry cannot be reached.

## 5. Enablement and Failure Behavior

MLflow is enabled by default when the package is installed and `mlflow.enabled` is true. Disable tracking and registry operations explicitly when needed:

```powershell
$env:MLFLOW_ENABLED = "false"
python -m src.train
Remove-Item Env:MLFLOW_ENABLED
```

When disabled or unavailable:

- Training still evaluates candidates and writes local model artifacts.
- Candidate registration returns a disabled result.
- Alias promotion is skipped.
- The API can serve the local champion fallback.

This makes local development possible without turning a missing registry into silent production approval.

## 6. Remote Production Configuration

For a shared MLflow deployment, configure a remote tracking server and a database-backed registry:

```powershell
$env:MLFLOW_TRACKING_URI = "https://<mlflow-server>"
$env:MLFLOW_REGISTRY_URI = "postgresql://<user>:<password>@<host>:5432/mlflow"
$env:MLFLOW_ENABLED = "true"
python -m src.train
```

Use durable object storage for artifacts:

| Provider | Artifact store |
|---|---|
| AWS | S3 |
| Azure | Blob Storage |
| GCP | GCS |

Use managed PostgreSQL or another supported durable backend for registry metadata. Keep credentials in the deployment secret manager, not in source, `.env` files, command history, or metadata JSON.

## 7. Promotion Lifecycle

```text
Train candidates
      |
      v
Log run metrics and artifacts
      |
      v
Register immutable model versions
      |
      v
Evaluate recall, cost, ranking, slices, and latency
      |
      +--> gate fails: retain current champion
      |
      v
Set champion alias on approved version
      |
      v
API resolves models:/vessel-delay-classifier@champion
```

The alias is the deployment contract. Consumers should resolve the alias rather than hard-code a numeric model version.

## 8. Reproducibility Requirements

A run is production-auditable only when these values are retained together:

- Source dataset version or URI
- Dataset row count and target rate
- Split strategy and partition sizes
- Feature version
- Project/code version
- Dependency or container image version
- Configuration snapshot
- Candidate parameters
- Calibration threshold and cost weights
- Final test metrics
- Model artifact URI
- Run ID and registered model version
- Promotion gate result

The local pipeline records most of these as MLflow parameters, metrics, tags, and model-version tags. A production CI/CD system should additionally log the Git commit, image digest, and immutable dataset URI.

## 9. Operational Queries

Use the MLflow UI or client to answer:

- Which run produced the current champion?
- What threshold and cost assumptions were used?
- Which dataset split and feature version were used?
- Why was a challenger rejected?
- Which model version can be used for rollback?
- Which candidate has the best business cost under the recall floor?

The local JSON files provide the same key evidence for offline inspection:

```text
models/metadata.json
models/production_metadata.json
models/baseline_metadata.json
models/random_forest_metadata.json
models/xgboost_metadata.json
```

## 10. Production Safeguards

- Never move `champion` manually without validation evidence.
- Keep candidate versions immutable.
- Retain the previous champion for rollback.
- Restrict registry write permissions to the training or release identity.
- Give the serving identity read-only access to the approved model alias.
- Monitor artifact-store and registry availability separately from API health.
- Back up the registry database and artifact store.
- Avoid local SQLite for a multi-worker or multi-region production registry.
- Do not expose the MLflow UI publicly without authentication and network controls.
- Review serialized model artifacts as trusted code because pickle-based formats can execute code during loading.

## 11. Verification Commands

```powershell
python -m pytest -q
python -m src.train
python -m monitoring.monitor
```

After training, verify that:

- All three candidate runs exist.
- Each candidate has parameters, metrics, and lineage tags.
- Each candidate has an immutable registered version when MLflow is enabled.
- Exactly the approved production version has alias `champion`.
- The API reports the registry model source and version through `/health` and `/ready`.
