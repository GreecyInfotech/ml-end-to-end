# Episode 3: Logistic Regression, Random Forest, and XGBoost

**Duration:** 42 minutes

## Business Problem

The team needs a baseline that is explainable and challengers that can capture nonlinear vessel-delay behavior.

## Video Flow

1. Explain why Logistic Regression is the baseline.
2. Explain why Random Forest is a robust nonlinear challenger.
3. Explain why XGBoost is a high-performance challenger.
4. Walk through the common preprocessing and model interface.
5. Run training and compare candidate metrics.

## Live Demo

```powershell
Get-Content src/baseline.py
Get-Content src/ensemble_models.py
Get-Content src/pipeline.py
python -m src.train
Get-Content models/metadata.json
```

## Explain on Screen

Every candidate uses the same data split and evaluation contract. The point is not to choose the most complex model automatically; it is to compare quality, business cost, latency, and governance evidence.

Discuss:

- Reproducible random seeds
- Time-aware validation when event timestamps exist
- Candidate artifacts versus production champion
- Why a baseline is required for safe promotion decisions

## Live Comparison

Create a small table on screen with:

- Recall
- F1
- ROC-AUC
- PR-AUC
- Business cost
- P95 latency

## Closing Evidence

Show that all candidates are evaluated, but only one becomes the champion after the promotion gate.
