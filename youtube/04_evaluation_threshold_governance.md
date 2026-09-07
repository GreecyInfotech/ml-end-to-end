# Episode 4: Evaluation, Threshold Optimization, and Governance

**Duration:** 42 minutes

## Business Problem

A probability threshold is an operational policy. In this project, missing a true delay is more expensive than generating an unnecessary alert.

## Video Flow

1. Explain classification metrics and their operational meaning.
2. Explain false-positive and false-negative costs.
3. Show why threshold tuning belongs on calibration data, not the test set.
4. Demonstrate promotion gates and production baselines.
5. Explain approval, rejection, and audit evidence.

## Live Demo

```powershell
Get-Content src/evaluation.py
Get-Content src/model_gate.py
Get-Content model_evaluation_business_cost.md
python -m pytest tests/test_evaluation.py -q
python -m src.train
Get-Content models/production_metadata.json
```

## Explain on Screen

The evaluation flow is:

```text
train -> calibrate threshold -> evaluate untouched test -> apply business gate
```

Discuss:

- Recall floor
- Business cost formula
- Confusion matrix
- Slice metrics for congestion, rain, peak hour, and berth wait
- P95 latency constraint
- Champion retention when a challenger fails

## Governance Moment

Explain why the system does not overwrite the production model simply because a new training run completed.

## Closing Evidence

Show the promotion gate result in `models/metadata.json` and explain which evidence would block release.
