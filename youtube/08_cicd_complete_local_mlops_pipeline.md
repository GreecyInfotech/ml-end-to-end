# Episode 8: CI/CD and the Complete Local MLOps Pipeline

**Duration:** 42 minutes

## Business Problem

Production ML needs repeatability: the same checks should run before training, promotion, deployment, and monitoring.

## Video Flow

1. Define the CI/CD quality gates.
2. Run tests before training.
3. Run data quality and drift checks.
4. Train candidates and inspect the promotion gate.
5. Build the image.
6. Validate Compose configuration.
7. Deploy API, gateway, and observability.
8. Run a smoke prediction.

## Live Demo

```powershell
python -m pytest -q
python -m monitoring.monitor --fail-on-alert
python -m src.train
docker compose build
docker compose --profile observability config --quiet
docker compose up -d api gateway
docker compose --profile observability up -d
```

## Release Gates

- Unit and integration tests pass.
- Dataset contract passes.
- Monitoring does not contain an unapproved alert.
- Candidate passes model and business gates.
- Feature-contract hash matches.
- Image builds successfully.
- Readiness is healthy.
- Representative prediction succeeds.
- Error rate and latency are within budget.

## Explain on Screen

Separate one-shot jobs from long-running services:

```text
train   -> controlled job
monitor -> scheduled job
api     -> model serving
 gateway -> edge protection
 prometheus/grafana -> operations
```

## Closing Evidence

Show the complete local workflow as a repeatable release pipeline, not as a sequence of manual notebooks.
