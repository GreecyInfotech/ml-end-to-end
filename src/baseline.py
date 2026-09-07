from __future__ import annotations

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .pipeline import make_preprocessor


def build_baseline_model(cfg: dict) -> Pipeline:
    """Build the deterministic, interpretable Logistic Regression baseline."""
    return Pipeline(
        [
            ("preprocessor", make_preprocessor()),
            (
                "model",
                LogisticRegression(
                    max_iter=cfg["models"]["logistic_regression"]["max_iter"],
                    random_state=cfg["model"]["random_state"],
                ),
            ),
        ]
    )