from __future__ import annotations

import contextvars
import json
import logging
import os
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from fastapi import FastAPI, Request
import psutil
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

try:
    from opentelemetry import context, propagate, trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except ImportError:  # Tracing remains no-op when OTLP extras are not installed.
    context = propagate = trace = None

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")
_state: dict[str, dict[str, float]] = {}
_request_timestamps: dict[str, deque[float]] = defaultdict(deque)
_state_lock = Lock()

HTTP_REQUESTS = Counter(
    "vessel_http_requests_total",
    "HTTP requests processed by vessel-delay services.",
    ["service", "method", "route", "status"],
)
HTTP_ERRORS = Counter(
    "vessel_http_errors_total",
    "HTTP 5xx responses produced by vessel-delay services.",
    ["service", "route"],
)
HTTP_DURATION = Histogram(
    "vessel_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["service", "method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
SLO_TARGET = Gauge("vessel_slo_availability_target", "Configured availability SLO target.", ["service"])
SERVICE_AVAILABILITY = Gauge("vessel_service_availability_ratio", "Observed service availability ratio.", ["service"])
SERVICE_ERROR_RATE = Gauge("vessel_service_error_rate", "Observed HTTP 5xx error rate.", ["service"])
SERVICE_THROUGHPUT = Gauge("vessel_service_throughput_requests_per_second", "Recent service throughput in requests per second.", ["service"])
ERROR_BUDGET_REMAINING = Gauge(
    "vessel_error_budget_remaining_ratio",
    "Remaining availability error budget as a ratio of the allowed budget.",
    ["service"],
)
SLO_BURN_RATE = Gauge("vessel_slo_burn_rate", "Availability SLO burn rate.", ["service"])
PROCESS_CPU_PERCENT = Gauge("vessel_process_cpu_percent", "Process CPU utilization percentage.", ["service"])
PROCESS_MEMORY_BYTES = Gauge("vessel_process_memory_bytes", "Resident process memory in bytes.", ["service"])
PROCESS_UPTIME_SECONDS = Gauge("vessel_process_uptime_seconds", "Process uptime in seconds.", ["service"])

_PROCESS = psutil.Process(os.getpid())
_PROCESS_STARTED_AT = time.time()
_THROUGHPUT_WINDOW_SECONDS = float(os.getenv("TELEMETRY_THROUGHPUT_WINDOW_SECONDS", "60"))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
            "trace_id": _trace_id.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(service: str) -> logging.Logger:
    logger = logging.getLogger(service)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    if not any(getattr(handler, "_vessel_json", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler._vessel_json = True
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def _configure_tracing(service: str) -> Any:
    if trace is None:
        return None
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and not isinstance(trace.get_tracer_provider(), TracerProvider):
        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
    return trace.get_tracer(service)


def _slo_target() -> float:
    value = float(os.getenv("SLO_AVAILABILITY_TARGET", "0.995"))
    return min(max(value, 0.9), 0.99999)


def _record_slo(service: str, status_code: int) -> None:
    now = time.time()
    with _state_lock:
        state = _state.setdefault(service, {"requests": 0.0, "errors": 0.0})
        state["requests"] += 1
        if status_code >= 500:
            state["errors"] += 1
        timestamps = _request_timestamps[service]
        timestamps.append(now)
        while timestamps and now - timestamps[0] > _THROUGHPUT_WINDOW_SECONDS:
            timestamps.popleft()
        requests = state["requests"]
        errors = state["errors"]
        recent_requests = len(timestamps)
    target = _slo_target()
    error_rate = errors / max(requests, 1.0)
    budget = max(1.0 - target, 1e-9)
    remaining = max(0.0, min(1.0, (budget - error_rate) / budget))
    SLO_TARGET.labels(service).set(target)
    ERROR_BUDGET_REMAINING.labels(service).set(remaining)
    SLO_BURN_RATE.labels(service).set(error_rate / budget)
    SERVICE_AVAILABILITY.labels(service).set(1.0 - error_rate)
    SERVICE_ERROR_RATE.labels(service).set(error_rate)
    SERVICE_THROUGHPUT.labels(service).set(recent_requests / max(_THROUGHPUT_WINDOW_SECONDS, 1.0))


def _record_process_metrics(service: str) -> None:
    PROCESS_CPU_PERCENT.labels(service).set(_PROCESS.cpu_percent(interval=None))
    PROCESS_MEMORY_BYTES.labels(service).set(_PROCESS.memory_info().rss)
    PROCESS_UPTIME_SECONDS.labels(service).set(max(time.time() - _PROCESS_STARTED_AT, 0.0))


def sre_snapshot(service: str) -> dict[str, Any]:
    with _state_lock:
        state = dict(_state.get(service, {"requests": 0.0, "errors": 0.0}))
    requests = int(state["requests"])
    errors = int(state["errors"])
    target = _slo_target()
    error_rate = errors / max(requests, 1)
    availability = 1.0 - error_rate
    budget = max(1.0 - target, 1e-9)
    return {
        "service": service,
        "slo": {"availability_target": target, "window": os.getenv("SLO_WINDOW", "30d")},
        "requests": requests,
        "errors_5xx": errors,
        "availability": round(availability, 6),
        "error_rate": round(error_rate, 6),
        "error_budget_remaining_ratio": round(max(0.0, min(1.0, (budget - error_rate) / budget)), 6),
        "burn_rate": round(error_rate / budget, 6),
        "status": "breached" if availability < target else "within_budget",
    }


def prometheus_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def inject_trace_headers(headers: dict[str, str]) -> dict[str, str]:
    if propagate:
        propagate.inject(headers)
    return headers


def install_observability(app: FastAPI, service: str) -> None:
    logger = configure_logging(service)
    tracer = _configure_tracing(service)

    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or os.urandom(8).hex()
        request_token = _request_id.set(request_id)
        carrier = dict(request.headers)
        parent_context = propagate.extract(carrier) if propagate else None
        context_token = context.attach(parent_context) if context and parent_context else None
        started = time.perf_counter()
        status_code = 500
        route = request.url.path
        try:
            span_context = tracer.start_as_current_span(f"{request.method} {route}") if tracer else None
            if span_context:
                with span_context as span:
                    span.set_attribute("http.method", request.method)
                    span.set_attribute("http.route", route)
                    span.set_attribute("http.request_id", request_id)
                    response = await call_next(request)
            else:
                response = await call_next(request)
            status_code = response.status_code
            route = getattr(request.scope.get("route"), "path", route)
            duration = time.perf_counter() - started
            HTTP_REQUESTS.labels(service, request.method, route, str(status_code)).inc()
            HTTP_DURATION.labels(service, request.method, route).observe(duration)
            if status_code >= 500:
                HTTP_ERRORS.labels(service, route).inc()
            _record_slo(service, status_code)
            _record_process_metrics(service)
            response.headers["X-Request-ID"] = request_id
            logger.info("request_complete method=%s route=%s status=%s duration_ms=%.3f", request.method, route, status_code, duration * 1000)
            return response
        except Exception:
            route = getattr(request.scope.get("route"), "path", route)
            duration = time.perf_counter() - started
            HTTP_REQUESTS.labels(service, request.method, route, "500").inc()
            HTTP_ERRORS.labels(service, route).inc()
            HTTP_DURATION.labels(service, request.method, route).observe(duration)
            _record_slo(service, 500)
            _record_process_metrics(service)
            logger.exception("request_failed method=%s route=%s", request.method, route)
            raise
        finally:
            if context_token is not None and context is not None:
                context.detach(context_token)
            _request_id.reset(request_token)

    app.add_api_route("/metrics", prometheus_response, methods=["GET"], include_in_schema=False)
    app.add_api_route("/sre", lambda: sre_snapshot(service), methods=["GET"], include_in_schema=False)
