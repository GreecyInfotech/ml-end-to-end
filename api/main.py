from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from src.config import load_config
from src.feature_engineering import create_features
from src.feature_store import feature_contract_hash
from src.mlflow_registry import get_alias_model, registry_enabled

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "champion.joblib"
PROCESS_STARTED_AT = time.time()
CONFIG = load_config()
logger = logging.getLogger("vessel-delay-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = FastAPI(title="Vessel Delay Prediction API", version="2.1.0")

model = None
model_source = "local"
registry_metadata = {}
feature_version = CONFIG.get("project", {}).get("feature_version", "v2")
runtime_feature_contract_hash = feature_contract_hash(feature_version)
expected_feature_contract_hash = None
try:
    if registry_enabled(CONFIG):
        model, registry_metadata = get_alias_model(CONFIG, ROOT)
        model_source = "mlflow_registry"
except Exception as exc:
    logger.warning("MLflow champion unavailable; using local champion: %s", exc)

if model is None and MODEL_PATH.exists():
    model = joblib.load(MODEL_PATH)

threshold = float(CONFIG["model"].get("decision_threshold", 0.5))
metadata_path = ROOT / "models" / "metadata.json"
if metadata_path.exists():
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        champion = metadata.get("champion")
        expected_feature_contract_hash = metadata.get("feature_contract_hash")
        threshold = float(next((m["threshold"] for m in metadata.get("metrics", []) if m.get("model") == champion), threshold))
    except Exception:
        pass

stats = {"requests": 0, "errors": 0, "latencies_ms": []}
stats_lock = Lock()


class VesselRequest(BaseModel):
    arrival_hour: int = Field(ge=0, le=23)
    cargo_volume: float = Field(ge=0)
    berth_wait_minutes: float = Field(ge=0, le=1440)
    port_congestion: str
    weather: str
    previous_delay_hours: float = Field(ge=0, le=168)
    crane_available: int = Field(ge=0, le=1)
    event_timestamp: str | None = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_source: str
    registry: dict[str, Any]
    feature_version: str
    feature_contract_hash: str
    feature_contract_status: str


class ReadyResponse(BaseModel):
    ready: bool
    model_source: str
    registry: dict[str, Any]
    feature_version: str
    feature_contract_hash: str
    feature_contract_status: str


class MetricsResponse(BaseModel):
    uptime_seconds: float
    requests: int
    errors: int
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    model_loaded: bool
    model_source: str
    model_version: str | None = None


class PredictionResponse(BaseModel):
    prediction: int
    status: str
    delay_probability: float
    decision_threshold: float
    latency_ms: float
    model_source: str
    registry: dict[str, Any]


def predict_probability(predictive_model: Any, features: pd.DataFrame) -> float:
    """Return a validated positive-class probability from a fitted model."""
    if hasattr(predictive_model, "predict_proba"):
        probabilities = np.asarray(predictive_model.predict_proba(features))
        probability = float(probabilities[0, 1])
    elif hasattr(predictive_model, "decision_function"):
        score = float(predictive_model.decision_function(features)[0])
        probability = float(1.0 / (1.0 + np.exp(-score)))
    else:
        raise ValueError("Loaded model does not expose probability prediction")
    if not np.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("Loaded model returned an invalid probability")
    return probability


def feature_contract_status() -> str:
    if expected_feature_contract_hash is None:
        return "UNKNOWN"
    return "MATCH" if expected_feature_contract_hash == runtime_feature_contract_hash else "MISMATCH"


@app.middleware("http")
async def reliability_middleware(request: Request, call_next):
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    try:
        response = await call_next(request)
        with stats_lock:
            stats["requests"] += 1
            stats["latencies_ms"].append((time.perf_counter() - started) * 1000)
            stats["latencies_ms"] = stats["latencies_ms"][-1000:]
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        with stats_lock:
            stats["requests"] += 1
            stats["errors"] += 1
        logger.exception("request_failed request_id=%s", request_id)
        raise


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy", "model_loaded": model is not None, "model_source": model_source, "registry": registry_metadata, "feature_version": feature_version, "feature_contract_hash": runtime_feature_contract_hash, "feature_contract_status": feature_contract_status()}


@app.get("/ready", response_model=ReadyResponse)
def ready():
    if model is None:
        raise HTTPException(status_code=503, detail="Model not trained")
    if feature_contract_status() == "MISMATCH":
        raise HTTPException(status_code=503, detail="Feature contract mismatch")
    return {"ready": True, "model_source": model_source, "registry": registry_metadata, "feature_version": feature_version, "feature_contract_hash": runtime_feature_contract_hash, "feature_contract_status": feature_contract_status()}


@app.get("/metrics", response_model=MetricsResponse)
def metrics():
    with stats_lock:
        latencies = list(stats["latencies_ms"])
        requests = stats["requests"]
        errors = stats["errors"]
    return {
        "uptime_seconds": max(time.time() - PROCESS_STARTED_AT, 0.0),
        "requests": requests,
        "errors": errors,
        "error_rate": errors / max(requests, 1),
        "p50_latency_ms": float(np.percentile(latencies, 50)) if latencies else 0.0,
        "p95_latency_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "p99_latency_ms": float(np.percentile(latencies, 99)) if latencies else 0.0,
        "model_loaded": model is not None,
        "model_source": model_source,
        "model_version": registry_metadata.get("version"),
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(vessel: VesselRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not trained")
    data = create_features(pd.DataFrame([vessel.model_dump()]))
    started = time.perf_counter()
    try:
        probability = predict_probability(model, data)
    except (TypeError, ValueError, IndexError) as exc:
        logger.exception("prediction_failed")
        raise HTTPException(status_code=503, detail="Model prediction unavailable") from exc
    latency_ms = (time.perf_counter() - started) * 1000
    prediction = int(probability >= threshold)
    return {"prediction": prediction, "status": "DELAYED" if prediction else "ON_TIME", "delay_probability": round(probability, 4), "decision_threshold": threshold, "latency_ms": round(latency_ms, 3), "model_source": model_source, "registry": registry_metadata}
