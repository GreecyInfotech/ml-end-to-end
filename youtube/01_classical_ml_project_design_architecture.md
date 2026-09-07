# Episode 1: Classical ML Project Design and Architecture

**Duration:** 42 minutes

## Business Problem

Predict whether a vessel will be delayed by more than two hours. The value is operational: port teams can prioritize berth planning, crane allocation, weather response, and customer communication.

## Key Takeaway

Do not start with model code. Start with the business decision, data contract, operating constraints, and production architecture.

## Video Flow

1. Introduce the delay decision and the cost of false negatives.
2. Show the repository structure and explain ownership boundaries.
3. Draw the architecture: raw data -> quality -> features -> training -> registry -> API -> gateway -> monitoring -> retraining.
4. Explain why the model API, ML Gateway, MLflow, monitoring job, and streaming adapter are separate components.
5. Explain the production baseline and champion/challenger model strategy.

## Live Demo

```powershell
Get-ChildItem
Get-Content README.md -TotalCount 55
Get-Content end_to_end_flow.md -TotalCount 80
python -m pytest -q
```

Open these source areas during the demo:

- `src/train.py`
- `src/feature_engineering.py`
- `api/main.py`
- `gateway/main.py`
- `monitoring/monitor.py`
- `docker-compose.yml`

## Explain on Screen

- Business target: `delayed`
- Model output: delay probability and operational status
- Production boundary: model serving is private; the gateway owns edge controls
- Registry boundary: registration is not the same as promotion
- Reliability boundary: monitoring can alert, but drift alone does not promote a model

## Closing Evidence

Show the passing test suite and the architecture diagram. The audience should understand what the system must do before learning how each model works.
