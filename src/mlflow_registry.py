from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    mlflow = None
    MlflowClient = None
    MLFLOW_AVAILABLE = False


def registry_enabled(cfg: dict[str, Any]) -> bool:
    configured = cfg.get("mlflow", {}).get("enabled", True)
    override = os.getenv("MLFLOW_ENABLED")
    if override is not None:
        configured = override.strip().lower() in {"1", "true", "yes", "on"}
    return MLFLOW_AVAILABLE and bool(configured)


def tracking_uri(cfg: dict[str, Any], root: Path) -> str:
    value = os.getenv("MLFLOW_TRACKING_URI") or cfg["mlflow"].get("tracking_uri", "")
    if value:
        return value
    return f"sqlite:///{(root / 'mlruns' / 'mlflow.db').as_posix()}"


def registry_uri(cfg: dict[str, Any], root: Path) -> str:
    value = os.getenv("MLFLOW_REGISTRY_URI") or cfg["mlflow"].get("registry_uri", "")
    return value or tracking_uri(cfg, root)


def configure_mlflow(cfg: dict[str, Any], root: Path) -> None:
    if not registry_enabled(cfg):
        return
    mlruns = root / "mlruns"
    mlruns.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking_uri(cfg, root))
    mlflow.set_registry_uri(registry_uri(cfg, root))
    mlflow.set_experiment(cfg["mlflow"]["experiment_name"])


def register_model(pipe, run_name: str, metrics: dict[str, Any], params: dict[str, Any], tags: dict[str, Any], cfg: dict[str, Any], root: Path) -> dict[str, Any]:
    """Log one candidate and register it as a new immutable model version."""
    if not registry_enabled(cfg):
        return {"enabled": False, "registered": False, "reason": "MLflow unavailable/disabled"}

    configure_mlflow(cfg, root)
    registered_name = cfg["mlflow"]["registered_model_name"]
    with mlflow.start_run(run_name=run_name) as run:
        safe_params = {k: str(v) for k, v in params.items()}
        safe_tags = {k: str(v) for k, v in tags.items()}
        mlflow.log_params(safe_params)
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.set_tags(safe_tags)
        model_info = mlflow.sklearn.log_model(
            sk_model=pipe,
            name="model",
            registered_model_name=registered_name,
        )

        client = MlflowClient()
        # The registration created from this run is the latest version for this run.
        versions = client.search_model_versions(f"name='{registered_name}'")
        run_versions = [v for v in versions if v.run_id == run.info.run_id]
        if not run_versions:
            raise RuntimeError(f"Could not locate registered version for run {run.info.run_id}")
        version = max(run_versions, key=lambda v: int(v.version))

        for key, value in {
            "validation_status": "candidate",
            "model_name": run_name,
            "model_version": version.version,
            "feature_version": cfg.get("project", {}).get("feature_version", "v2"),
            "feature_contract_hash": tags.get("feature_contract_hash", ""),
            "project_version": cfg.get("project", {}).get("version", "2.0.0"),
            "threshold": metrics.get("threshold", ""),
            "business_cost": metrics.get("business_cost", ""),
            "f1": metrics.get("f1", ""),
            "recall": metrics.get("recall", ""),
            "artifact_uri": getattr(model_info, "model_uri", f"runs:/{run.info.run_id}/model"),
        }.items():
            client.set_model_version_tag(registered_name, version.version, key, str(value))

        return {
            "enabled": True,
            "registered": True,
            "registered_model_name": registered_name,
            "version": str(version.version),
            "run_id": run.info.run_id,
            "model_uri": getattr(model_info, "model_uri", f"runs:/{run.info.run_id}/model"),
        }


def promote_alias(cfg: dict[str, Any], root: Path, version: str, status: str = "approved") -> dict[str, Any]:
    if not registry_enabled(cfg):
        return {"enabled": False, "promoted": False, "reason": "MLflow unavailable/disabled"}
    configure_mlflow(cfg, root)
    client = MlflowClient()
    name = cfg["mlflow"]["registered_model_name"]
    alias = cfg["mlflow"].get("production_alias", "champion")
    client.set_registered_model_alias(name, alias, version)
    client.set_model_version_tag(name, version, "validation_status", status)
    return {"enabled": True, "promoted": True, "registered_model_name": name, "alias": alias, "version": str(version)}


def rollback_alias(cfg: dict[str, Any], root: Path, version: str, reason: str) -> dict[str, Any]:
    """Move the production alias to an approved prior version for recovery."""
    if not reason.strip():
        raise ValueError("Rollback reason is required")
    result = promote_alias(cfg, root, version, status="rollback")
    if result.get("promoted"):
        configure_mlflow(cfg, root)
        client = MlflowClient()
        client.set_model_version_tag(
            cfg["mlflow"]["registered_model_name"],
            str(version),
            "rollback_reason",
            reason.strip(),
        )
    return result


def get_alias_model(cfg: dict[str, Any], root: Path) -> tuple[Any, dict[str, Any]]:
    if not registry_enabled(cfg):
        raise RuntimeError("MLflow registry is disabled or unavailable")
    configure_mlflow(cfg, root)
    client = MlflowClient()
    name = cfg["mlflow"]["registered_model_name"]
    alias = cfg["mlflow"].get("production_alias", "champion")
    mv = client.get_model_version_by_alias(name, alias)
    uri = f"models:/{name}@{alias}"
    model = mlflow.sklearn.load_model(uri)
    return model, {"registered_model_name": name, "alias": alias, "version": str(mv.version), "run_id": mv.run_id, "model_uri": uri}
