# Feature Store Consistency and Production Reliability

## 1. Feature Contract

The project uses a lightweight, versioned feature-store contract in `src/feature_store.py`. It defines:

- Feature version
- Numeric and categorical model inputs
- Derived feature rules
- A deterministic SHA-256 contract hash

The contract is shared by training and serving because both paths call the same `create_features()` implementation and model-column definitions.

## 2. Training Lineage

Every training artifact and MLflow model version records:

- `feature_version`
- `feature_contract_hash`
- Project version
- Dataset and split metadata

This makes a model traceable to the exact feature definition used to fit it.

## 3. Serving Consistency

At startup, the API computes the runtime contract hash and compares it with the hash persisted in `models/metadata.json`.

`/health` and `/ready` report:

- Feature version
- Runtime feature contract hash
- Contract status: `MATCH`, `MISMATCH`, or `UNKNOWN`

Readiness returns HTTP 503 for `MISMATCH`, preventing a known feature-definition mismatch from receiving traffic. `UNKNOWN` is retained for legacy artifacts created before contract hashes were introduced.

## 4. SRE Signals

Monitor:

- `/ready` probe failures
- Feature contract status
- Model source and registry version
- API error rate
- P95/P99 latency
- Monitoring report status
- PSI and missingness drift
- Consumer lag for Kafka streaming
- Retraining and rollback audit records

## 5. Release Gate

A production release must verify:

- Feature contract hash is recorded.
- Offline and online feature tests pass.
- `/ready` returns `MATCH` after model loading.
- Model registry version and alias are correct.
- Monitoring report status is acceptable.
- Previous champion is available for rollback.

## 6. Failure Handling

| Failure | Response |
|---|---|
| Feature contract mismatch | Fail readiness; keep previous deployment serving if available |
| Registry unavailable | Use local champion fallback and alert |
| Missing model artifact | Fail readiness and return HTTP 503 for prediction |
| Data-quality ALERT | Block automated retraining unless explicitly approved |
| Kafka consumer error | Retry through consumer group offsets; route invalid events to dead-letter handling |
| High drift | Alert and investigate; do not auto-promote a new model |

## 7. Rollout Pattern

Use a staged rollout:

```text
build image
  -> run contract and model tests
  -> train and register candidate
  -> verify feature hash and promotion gate
  -> deploy canary
  -> verify /ready, latency, error rate, and model version
  -> observe drift and matured labels
  -> expand traffic or rollback champion alias
```
