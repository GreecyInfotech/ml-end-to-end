# Episode 6: FastAPI, Docker, and Local Production Deployment

**Duration:** 42 minutes

## Business Problem

A trained model is not useful until it can serve reliable, validated predictions through a repeatable deployment unit.

## Video Flow

1. Walk through the FastAPI application.
2. Explain health, readiness, metrics, and prediction endpoints.
3. Demonstrate request validation and feature-contract readiness.
4. Show local process startup.
5. Show the non-root Docker image and Compose services.

## Live Demo

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

Prediction example:

```powershell
$payload = @{arrival_hour=8; cargo_volume=1200.0; berth_wait_minutes=45.0; port_congestion="high"; weather="rain"; previous_delay_hours=1.5; crane_available=1} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/predict -Method Post -ContentType "application/json" -Body $payload
```

Docker demo:

```powershell
docker compose build
docker compose up -d api
```

## Explain on Screen

- `/health` describes service state.
- `/ready` is the deployment readiness gate.
- `/metrics.json` provides diagnostics.
- `/metrics` is Prometheus-compatible.
- The API falls back to the local champion if MLflow is unavailable.
- The container runs as `appuser`, not root.

## Closing Evidence

Show a valid prediction, an invalid payload returning 422, and readiness behavior when the model or feature contract is unavailable.
