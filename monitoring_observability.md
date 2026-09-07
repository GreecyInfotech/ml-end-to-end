# Production ML Monitoring and Observability

## 1. Monitoring Signals

The system exposes three operational signal groups:

| Signal | Source | Purpose |
|---|---|---|
| Service health | FastAPI `/health` and `/ready` | Process and model availability |
| Runtime telemetry | FastAPI `/metrics` and `/metrics.json` | Prometheus metrics plus JSON diagnostics |
| SRE health | FastAPI `/sre` | Availability SLO, error budget, and burn rate |
| Distributed traces | OpenTelemetry OTLP | Trace/request correlation across gateway and API |
| Data/model health | `monitoring.monitor` | Data quality, PSI drift, and actionable alert status |

## 2. API Observability

### `/health`

Returns process health, whether a model is loaded, the model source, and registry metadata.

### `/ready`

Returns HTTP 200 only when a model is available. Returns HTTP 503 when neither the MLflow champion nor local fallback can be loaded. Use this endpoint for readiness probes.

### `/metrics.json`

Returns:

- Uptime in seconds
- Request count
- Error count and error rate
- P50, P95, and P99 latency
- Model-loaded state
- Model source
- Resolved MLflow model version

The current counters are process-local. Production deployments should export these values to a metrics backend and preserve request ID correlation through the gateway or log pipeline.

### Prometheus and Grafana

`/metrics` is a Prometheus scrape endpoint. It exports request counters, 5xx counters, request duration histograms, process CPU utilization, resident memory, throughput, availability, SLO targets, error-budget remaining ratio, and SLO burn rate. Histogram queries provide P50/P95/P99 latency in Grafana:

```promql
histogram_quantile(0.95, sum by (service, le) (rate(vessel_http_request_duration_seconds_bucket[5m])))
```

Start the local observability stack with:

```powershell
docker compose --profile observability up -d
```

Prometheus is available at `http://127.0.0.1:9090`; Grafana is available at `http://127.0.0.1:3000`. The provisioned dashboard includes CPU, memory, throughput, errors, availability, request rate, P50/P95/P99, error budget, and burn rate. Set `GF_SECURITY_ADMIN_PASSWORD` before a shared deployment.

### SLO and error budget

The default availability SLO is 99.5% over the configured `SLO_WINDOW` (default `30d`). Change it with `SLO_AVAILABILITY_TARGET`. `/sre` gives the current process-window availability, 5xx error rate, remaining budget, burn rate, and breach status. For durable multi-instance SLOs, aggregate the Prometheus counters centrally and evaluate a recording rule over a 30-day window.

### Logs and traces

Each request emits one JSON log record with method, route, status, duration, `request_id`, and `trace_id`. Incoming `X-Request-ID` is preserved and forwarded by the gateway. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to enable OTLP HTTP trace export; without it, tracing stays local/no-op and the service remains usable without a collector.

Gateway retries and controlled backend fallbacks are exposed as gateway counters in `/metrics.json` and in the Prometheus HTTP request/error series. Alert on sustained backend errors or fallback responses, not on a single transient retry.

Every response receives an `X-Request-ID` header. Callers may provide one; otherwise the service generates one.

## 3. Data and Drift Monitoring

Run the monitoring job:

```powershell
python -m monitoring.monitor `
  --reference data/raw/vessels.csv `
  --current data/raw/vessels.csv
```

The report is written to `data/predictions/monitoring_report.json` and includes:

- UTC generation time
- Reference and current paths
- Overall status
- Data-quality report
- Feature-level PSI records
- Feature-level missingness rates and deltas
- High, medium, and unavailable feature summaries

Status rules:

| Condition | Report status |
|---|---|
| Quality PASS and all drift LOW | `PASS` |
| Any MEDIUM drift with quality PASS | `WARN` |
| Quality WARN, HIGH drift, or unavailable drift feature | `ALERT` |

Each feature is evaluated on both distribution and availability. PSI measures the change in non-null values; missingness drift measures the absolute change in null rate. Either signal can raise a feature to `MEDIUM` or `HIGH` according to `configs/config.yaml`.

For scheduled jobs that should fail on production alerts:

```powershell
python -m monitoring.monitor --fail-on-alert
```

Exit code `2` indicates `ALERT`. This makes the job compatible with CI, cron, Kubernetes Jobs, and cloud schedulers.

## 4. Recommended Alerts

Create alerts for:

- `/ready` returning non-2xx
- Error rate above the service SLO
- P95 or P99 latency above the model/API SLA
- No requests received during an expected traffic window
- Monitoring report status `ALERT`
- High PSI on business-critical features
- Data-quality status `WARN`
- Champion model version changing outside a release window
- Registry or artifact-store load failures

## 5. Dashboard Panels

Recommended dashboard panels:

1. Request volume and error rate.
2. P50/P95/P99 latency.
3. Current model source and registry version.
4. Prediction rate and delayed prediction rate.
5. Latest monitoring status and report timestamp.
6. Top PSI features.
7. Data-quality issue counts.
8. Current champion version and deployment time.
9. Matured-label recall, precision, and business cost.
10. Drift and quality status by data source.

## 6. Incident Response

When an alert fires:

1. Check `/health`, `/ready`, `/metrics`, and `/sre` for the affected service.
2. Capture the `X-Request-ID`, `trace_id`, deployment revision, and model version.
3. Inspect the Grafana error-budget and latency panels, then query structured logs by request ID.
4. Determine whether the issue is service, registry, data quality, drift, or model performance.
5. Declare an incident when the SLO is breached or the burn-rate alert is sustained; assign an incident lead and record the timeline.
6. Mitigate first: reduce traffic, disable a bad route, or roll back the MLflow `champion` alias when an approved prior version exists.
7. Do not retrain automatically from a drift alert alone. Preserve reports, logs, traces, model version, and decision rationale for the post-incident review.

## 7. Production Integration

The local Docker roles map naturally to scheduled cloud jobs:

- API container: long-running service with `/ready` probe.
- Monitor container: scheduled job writing report output and failing on `ALERT` when configured.
- Train container: controlled release job that registers candidates and promotes aliases only after the gate.
- MLflow: protected registry and artifact service.

Use centralized logs and metrics in AWS, Azure, or GCP. Keep the application contract provider-neutral through environment variables and standard HTTP probes.