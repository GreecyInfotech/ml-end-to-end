# MLflow Model Registry and Versioning

## 1. Registry Contract

The project uses MLflow as the model registry when enabled:

```text
Registered model: vessel-delay-classifier
Production alias: champion
Candidate versions: immutable MLflow versions
Deployment lookup: models:/vessel-delay-classifier@champion
```

Every Logistic Regression, Random Forest, and XGBoost candidate is logged as a separate run and registered as a new model version. A numeric version is never overwritten. Promotion changes the alias, not the artifact.

## 2. Candidate Version Lifecycle

```text
candidate run
    -> model artifact logged
    -> immutable model version registered
    -> validation_status=candidate
    -> evaluation and promotion gate
    +--> rejected: version retained, alias unchanged
    +--> approved: validation_status=approved, champion alias updated
```

Each registered version contains or references:

- MLflow run ID
- Model version number
- Model name and candidate name
- Model artifact URI
- Feature version
- Project version
- Dataset and split lineage tags
- Threshold and business-cost assumptions
- Recall, F1, and business cost
- Validation status

## 3. Promotion Rules

Registration is not deployment approval. The selected candidate must pass the configured promotion gate:

- Recall meets the minimum floor.
- F1 is no worse than the current production model.
- ROC-AUC is no worse than the current production model.
- PR-AUC is no worse than the current production model.
- Business cost is no higher than the current production model.
- P95 latency is within the SLA.

When the gate fails, the new version remains available for audit and comparison, but `champion` continues to point to the previous approved version.

## 4. Local Registry Workflow

Train and register candidate versions:

```powershell
python -m src.train
```

Start the local UI:

```powershell
mlflow ui `
  --backend-store-uri sqlite:///mlruns/mlflow.db `
  --host 127.0.0.1 `
  --port 5000
```

Inspect the registered model at `http://127.0.0.1:5000`.

The latest local metadata is also written to:

```text
models/metadata.json
models/production_metadata.json
models/baseline_metadata.json
models/random_forest_metadata.json
models/xgboost_metadata.json
```

Each candidate metadata file includes a `registry` object with the registered model name, numeric version, run ID, and model URI when MLflow is enabled.

## 5. API Resolution

At startup, the API attempts to load:

```text
models:/vessel-delay-classifier@champion
```

This keeps serving independent of numeric version numbers. `/health` and `/ready` expose the resolved alias and version. If the registry is unavailable, the API loads `models/champion.joblib` as a local fallback.

## 6. Rollback

Rollback is an alias operation. Select a previously approved version after reviewing its evidence, then move the alias through the MLflow client or controlled release job:

```python
from mlflow.tracking import MlflowClient

client = MlflowClient()
client.set_registered_model_alias(
    "vessel-delay-classifier",
    "champion",
    "<approved-version>",
)
```

The rollback version must be compatible with the serving feature version and dependency environment. Record the incident, reason, operator, and resulting alias target in the release system.

## 7. Remote Production Registry

Use environment variables to point the same training and serving code at a shared registry:

```powershell
$env:MLFLOW_TRACKING_URI = "https://<mlflow-server>"
$env:MLFLOW_REGISTRY_URI = "postgresql://<user>:<password>@<host>:5432/mlflow"
$env:MLFLOW_ENABLED = "true"
python -m src.train
```

Use durable artifact storage such as S3, Azure Blob Storage, or GCS. Use a managed PostgreSQL backend for registry metadata. Keep credentials in the platform secret manager.

## 8. Versioning Rules

- Never overwrite a registered model version.
- Never deploy a numeric version without passing the promotion gate.
- Use aliases for serving contracts.
- Keep the previous champion available for rollback.
- Increment the feature version when feature definitions change.
- Record project and dependency versions with every candidate.
- Retain rejected candidate versions for auditability.
- Restrict model-version and alias writes to the release identity.
- Give the API read-only registry access in production.

## 9. Verification

```powershell
python -m pytest -q
python -m src.train
```

After training, verify:

1. Three candidate runs were created.
2. Each candidate has a distinct numeric model version.
3. Candidate model-version tags include `model_version` and `artifact_uri`.
4. Exactly the approved version has alias `champion`.
5. Local candidate metadata contains the registry reference.
6. The API resolves the alias and reports its version.