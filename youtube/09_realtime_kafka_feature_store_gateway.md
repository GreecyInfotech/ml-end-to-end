# Episode 9: Real-Time MLOps, Kafka, Feature Store, and ML Gateway

**Duration:** 42 minutes

## Business Problem

Port operations may need predictions from live vessel events, not only batch CSV files. Real-time processing introduces delivery, consistency, and edge-security concerns.

## Video Flow

1. Explain the event envelope and prediction topic.
2. Walk through the Kafka adapter.
3. Explain manual commits and at-least-once delivery.
4. Explain idempotency through event IDs and Kafka keys.
5. Demonstrate feature-store contract consistency.
6. Show the ML Gateway as the HTTP edge boundary.

## Live Demo

```powershell
Get-Content streaming/kafka_predictor.py
Get-Content feature_store_consistency.md
Get-Content gateway/main.py
Get-Content ml_gateway_architecture.md
```

Optional Kafka configuration:

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
```

HTTP gateway demo:

```powershell
python -m uvicorn gateway.main:app --host 127.0.0.1 --port 8080
```

## Explain on Screen

Event flow:

```text
vessel-events -> consumer group -> prediction callback -> vessel-delay-predictions
```

The adapter commits only after successful output publication. A failure leaves the input uncommitted for retry. Downstream consumers must tolerate duplicates.

Gateway responsibilities:

- Authentication
- Authorization
- Validation
- Rate limiting
- Request ID
- Routing
- Timeout
- Retry
- Fallback
- Observability

## Closing Evidence

Show the same feature contract serving batch and real-time predictions. Explain why feature parity is a release gate.
