# Episode 5: MLflow Tracking and Model Registry

**Duration:** 42 minutes

## Business Problem

Production teams need to answer: which data, code, features, parameters, metrics, and approval decision produced the running model?

## Video Flow

1. Explain experiment tracking versus model registry.
2. Inspect the local `mlruns/mlflow.db` backend.
3. Run training and open the MLflow UI.
4. Show candidate model versions and tags.
5. Explain the `champion` alias and immutable numeric versions.
6. Demonstrate rollback as an alias operation.

## Live Demo

```powershell
python -m src.train
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --host 127.0.0.1 --port 5000
```

Open:

```text
http://127.0.0.1:5000
```

Inspect:

```powershell
Get-Content src/mlflow_registry.py
Get-Content model_registry_versioning.md
Get-Content models/metadata.json
```

## Explain on Screen

The API resolves:

```text
models:/vessel-delay-classifier@champion
```

It does not hard-code a numeric version. Promotion changes the alias; it does not mutate an artifact.

## Production Note

Local SQLite is for development. Production should use managed PostgreSQL for MLflow metadata and durable object storage for artifacts.

## Closing Evidence

Show a candidate that fails the gate, the existing champion remaining active, and the model lineage visible in MLflow.
