from __future__ import annotations

import time
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def classification_metrics(y_true, probabilities, threshold: float = 0.5, fp_cost: float = 1.0, fn_cost: float = 5.0):
    probabilities = np.asarray(probabilities)
    predictions = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "false_positive_rate": float(fp / max(fp + tn, 1)),
        "false_negative_rate": float(fn / max(fn + tp, 1)),
        "business_cost": float(fp * fp_cost + fn * fn_cost),
        "threshold": float(threshold),
    }


def tune_threshold(y_true, probabilities, fp_cost: float, fn_cost: float, min_recall: float = 0.0):
    candidates = np.round(np.arange(0.10, 0.91, 0.01), 2)
    rows = []
    for threshold in candidates:
        m = classification_metrics(y_true, probabilities, threshold, fp_cost, fn_cost)
        if m["recall"] >= min_recall:
            rows.append(m)
    if not rows:
        rows = [classification_metrics(y_true, probabilities, 0.5, fp_cost, fn_cost)]
    return min(rows, key=lambda x: (x["business_cost"], -x["recall"]))


def slice_metrics(df: pd.DataFrame, y_true, probabilities, threshold: float, fp_cost: float, fn_cost: float):
    base = df.reset_index(drop=True)
    y = np.asarray(y_true)
    p = np.asarray(probabilities)
    slices = {
        "all": np.ones(len(base), dtype=bool),
        "high_congestion": base["port_congestion"].astype(str).str.lower().eq("high").to_numpy(),
        "rain": base["weather"].astype(str).str.lower().eq("rain").to_numpy(),
        "peak_hour": base["arrival_hour"].between(7, 10).to_numpy() | base["arrival_hour"].between(17, 20).to_numpy(),
        "high_berth_wait": (base["berth_wait_minutes"] > 60).to_numpy(),
    }
    output = {}
    for name, mask in slices.items():
        if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
            output[name] = {"rows": int(mask.sum()), "status": "insufficient_class_variation"}
        else:
            output[name] = {"rows": int(mask.sum()), **classification_metrics(y[mask], p[mask], threshold, fp_cost, fn_cost)}
    return output


def p95_latency_ms(predict_fn: Callable[[], object], iterations: int = 100) -> float:
    timings = []
    for _ in range(iterations):
        start = time.perf_counter()
        predict_fn()
        timings.append((time.perf_counter() - start) * 1000)
    return float(np.percentile(timings, 95))
