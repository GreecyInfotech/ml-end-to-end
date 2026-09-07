# Rollback, Retraining, and Kafka Streaming Operations

## 1. Rollback and Fallback

The serving path has two layers of recovery:

1. FastAPI resolves the MLflow `champion` alias.
2. If the registry or artifact store is unavailable, it loads `models/champion.joblib`.

For a controlled rollback, move the alias to an already approved numeric version:

```python
from src.config import load_config, ROOT
from src.mlflow_registry import rollback_alias

result = rollback_alias(
  load_config(),
  ROOT,
  version="<approved-version>",
  reason="Elevated false-negative rate after release",
)
print(result)
```

The rollback requires a non-empty reason, sets the alias, marks the model version as `rollback`, and records the reason as a model-version tag.

Rollback checklist:

- Confirm the target version is approved and feature-compatible.
- Check its run, dataset, dependency, and threshold metadata.
- Move the `champion` alias through a controlled release identity.
- Verify `/health`, `/ready`, and `/metrics` show the expected version.
- Preserve the incident reason and rollback timestamp.

## 2. Controlled Retraining

Retraining is intentionally a separate command from monitoring:

```powershell
python -m monitoring.monitor --fail-on-alert
python -m src.retrain --reason "Scheduled weekly retraining"
```

The retraining command:

- Reads `data/predictions/monitoring_report.json`.
- Blocks when status is `ALERT` unless `--allow-alert` is explicit.
- Runs the full candidate training and promotion gate.
- Writes `models/retraining_audit.json` with reason, monitoring status, override, timestamp, and exit code.

For an approved exception:

```powershell
python -m src.retrain `
  --allow-alert `
  --reason "Approved retraining after verified source-system correction"
```

Drift alone is not a promotion decision. Review data quality, label maturity, business cost, and candidate metrics before allowing an alert-state retraining run.

## 3. Continuous Improvement Loop

```text
current data
   -> quality and drift monitor
   -> investigate WARN/ALERT
   -> freeze dataset version
   -> controlled retraining
   -> evaluate candidates
   -> MLflow registration
   -> promotion gate
   -> champion alias or retain current champion
   -> observe matured labels and business cost
```

Keep rejected candidates and monitoring reports for auditability. Never overwrite the current champion artifact until the candidate gate passes.

## 4. Kafka Streaming Prediction

The optional adapter in `streaming/kafka_predictor.py` uses `confluent-kafka` and keeps Kafka out of API startup. This allows HTTP serving and streaming serving to scale independently.

Install the project requirements, including `confluent-kafka`, then configure:

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
```

The adapter consumes JSON events from an input topic and publishes JSON results to an output topic. The supplied callback should call the same feature engineering and model prediction contract used by the API.

Event flow:

```text
vessel-events topic
      -> Kafka consumer group vessel-delay-predictor
      -> model callback
      -> vessel-delay-predictions topic
```

The consumer uses manual commits: it commits an input message only after the prediction is produced. This provides at-least-once processing. Downstream consumers should use an event ID or Kafka key for idempotency because retries can duplicate outputs.

Recommended event envelope:

```json
{
  "event_id": "vessel-event-123",
  "arrival_hour": 8,
  "cargo_volume": 1200.0,
  "berth_wait_minutes": 45.0,
  "port_congestion": "high",
  "weather": "rain",
  "previous_delay_hours": 1.5,
  "crane_available": 1,
  "event_timestamp": "2024-01-01T08:00:00Z"
}
```

Recommended output envelope:

```json
{
  "input": {"event_id": "vessel-event-123"},
  "prediction": {
    "prediction": 1,
    "status": "DELAYED",
    "delay_probability": 0.91,
    "model_version": "13"
  }
}
```

## 5. Kafka Production Requirements

- Use TLS and SASL or the cloud provider's managed identity mechanism.
- Store credentials in a secret manager.
- Use a stable consumer group for offset recovery.
- Configure dead-letter handling for invalid JSON and schema failures.
- Use event IDs and output keys for idempotent consumers.
- Monitor consumer lag, rebalance count, error rate, throughput, and prediction latency.
- Keep model version in every output event.
- Roll out model changes with a new consumer deployment or controlled alias resolution.
- Do not commit offsets before successful output publication.

## 6. Deployment Mapping

| Local role | AWS | Azure | GCP |
|---|---|---|---|
| HTTP API | ECS/Fargate or App Runner | Container Apps or App Service | Cloud Run or GKE |
| Retraining job | Batch or scheduled ECS task | Container Apps Job or Azure ML | Cloud Run Job or Vertex AI |
| Kafka-compatible stream | MSK or Kafka provider | Event Hubs Kafka endpoint or managed Kafka | Managed Kafka or Pub/Sub adapter |
| Registry | MLflow on managed infrastructure | MLflow on managed infrastructure | MLflow on managed infrastructure |

The Python model and prediction contract remain provider-neutral.
