from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from threading import Lock
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from observability.telemetry import inject_trace_headers, install_observability, sre_snapshot

app = FastAPI(title="Vessel Delay ML Gateway", version="1.0.0")
install_observability(app, "vessel-delay-gateway")
BACKEND_URL = os.getenv("MODEL_API_URL", "http://127.0.0.1:8000").rstrip("/")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY")
GATEWAY_API_KEYS = os.getenv("GATEWAY_API_KEYS", "")
GATEWAY_REQUIRED_ROLE = os.getenv("GATEWAY_REQUIRED_ROLE", "predictor")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "5"))
BACKEND_MAX_RETRIES = int(os.getenv("GATEWAY_BACKEND_MAX_RETRIES", "2"))
BACKEND_RETRY_BACKOFF_SECONDS = float(os.getenv("GATEWAY_RETRY_BACKOFF_SECONDS", "0.1"))
RATE_LIMIT = int(os.getenv("GATEWAY_RATE_LIMIT", "120"))
RATE_WINDOW_SECONDS = int(os.getenv("GATEWAY_RATE_WINDOW_SECONDS", "60"))
request_times: deque[float] = deque()
stats = {"requests": 0, "errors": 0, "rate_limited": 0, "backend_errors": 0, "backend_retries": 0, "fallbacks": 0}
stats_lock = Lock()
logger = logging.getLogger("vessel-delay-gateway")
ROLE_LEVELS = {"readonly": 1, "predictor": 2, "admin": 3}
RETRYABLE_STATUS_CODES = {502, 503, 504}


class GatewayVesselRequest(BaseModel):
    arrival_hour: int = Field(ge=0, le=23)
    cargo_volume: float = Field(ge=0)
    berth_wait_minutes: float = Field(ge=0, le=1440)
    port_congestion: str
    weather: str
    previous_delay_hours: float = Field(ge=0, le=168)
    crane_available: int = Field(ge=0, le=1)
    event_timestamp: str | None = None


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _api_key_roles() -> dict[str, str]:
    if not GATEWAY_API_KEYS:
        return {}
    try:
        roles = json.loads(GATEWAY_API_KEYS)
        return roles if isinstance(roles, dict) else {}
    except json.JSONDecodeError:
        logger.error("invalid GATEWAY_API_KEYS configuration")
        return {}


def _authorization_status(request: Request) -> int | None:
    supplied_key = request.headers.get("X-API-Key")
    if GATEWAY_API_KEYS:
        role = _api_key_roles().get(supplied_key or "")
        if role is None:
            return 401
    elif GATEWAY_API_KEY:
        if supplied_key != GATEWAY_API_KEY:
            return 401
        role = "admin"
    else:
        role = "admin"
    if ROLE_LEVELS.get(role, 0) < ROLE_LEVELS.get(GATEWAY_REQUIRED_ROLE, ROLE_LEVELS["predictor"]):
        return 403
    return None


def _allow_request() -> bool:
    now = time.time()
    with stats_lock:
        while request_times and now - request_times[0] >= RATE_WINDOW_SECONDS:
            request_times.popleft()
        if len(request_times) >= RATE_LIMIT:
            stats["rate_limited"] += 1
            return False
        request_times.append(now)
        return True


async def _backend(method: str, path: str, request_id: str, payload: Any = None) -> dict[str, Any]:
    headers = inject_trace_headers({"X-Request-ID": request_id})
    last_error: Exception | None = None
    for attempt in range(BACKEND_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.request(method, f"{BACKEND_URL}{path}", json=payload, headers=headers)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < BACKEND_MAX_RETRIES:
                with stats_lock:
                    stats["backend_retries"] += 1
                await asyncio.sleep(BACKEND_RETRY_BACKOFF_SECONDS * (2**attempt))
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, ValueError) as exc:
            last_error = exc
            if attempt < BACKEND_MAX_RETRIES:
                with stats_lock:
                    stats["backend_retries"] += 1
                await asyncio.sleep(BACKEND_RETRY_BACKOFF_SECONDS * (2**attempt))
                continue
            break
        except httpx.HTTPError as exc:
            last_error = exc
            break
    with stats_lock:
        stats["backend_errors"] += 1
        stats["fallbacks"] += 1
    raise HTTPException(status_code=503, detail="Model backend unavailable") from last_error


@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    request_id = _request_id(request)
    with stats_lock:
        stats["requests"] += 1
    authorization_status = _authorization_status(request)
    if authorization_status:
        with stats_lock:
            stats["errors"] += 1
        detail = "Invalid API key" if authorization_status == 401 else "Insufficient gateway role"
        response = JSONResponse(status_code=authorization_status, content={"detail": detail})
    elif not _allow_request():
        response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    else:
        try:
            response = await call_next(request)
        except Exception:
            with stats_lock:
                stats["errors"] += 1
            raise
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health():
    return {"status": "healthy", "gateway": "v1", "backend_url": BACKEND_URL}


@app.get("/ready")
async def ready(request: Request):
    return {"ready": True, "gateway": "v1", "backend": await _backend("GET", "/ready", _request_id(request))}


@app.get("/metrics.json")
async def metrics():
    with stats_lock:
        return {**stats, "backend_url": BACKEND_URL, "rate_limit": RATE_LIMIT, "rate_window_seconds": RATE_WINDOW_SECONDS}


@app.get("/sre")
async def sre():
    return sre_snapshot("vessel-delay-gateway")


@app.post("/predict")
async def predict(request: Request, vessel: GatewayVesselRequest):
    result = await _backend("POST", "/predict", _request_id(request), vessel.model_dump())
    result["gateway"] = "v1"
    return result