import numpy as np
from src.evaluation import classification_metrics, tune_threshold


def test_metrics_and_threshold():
    y = np.array([0,0,1,1])
    p = np.array([0.1,0.4,0.7,0.9])
    m = classification_metrics(y, p, 0.5, 1, 5)
    assert m["recall"] == 1.0
    tuned = tune_threshold(y, p, 1, 5, min_recall=1.0)
    assert tuned["recall"] >= 1.0


def test_threshold_optimization_prefers_recall_when_false_negatives_are_expensive():
    y = np.array([1, 0])
    p = np.array([0.4, 0.6])

    tuned = tune_threshold(y, p, fp_cost=1, fn_cost=5, min_recall=1.0)

    assert tuned["threshold"] <= 0.4
    assert tuned["business_cost"] == 1.0


def test_business_cost_counts_false_positive_and_false_negative_penalties():
    y = np.array([0, 1, 1])
    p = np.array([0.8, 0.2, 0.9])

    metrics = classification_metrics(y, p, threshold=0.5, fp_cost=2, fn_cost=7)

    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["business_cost"] == 9.0
