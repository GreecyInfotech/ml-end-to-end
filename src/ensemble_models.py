from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier


def build_random_forest(cfg: dict) -> RandomForestClassifier:
    settings = cfg["models"]["random_forest"]
    return RandomForestClassifier(
        n_estimators=settings["n_estimators"],
        max_depth=settings["max_depth"],
        min_samples_leaf=settings.get("min_samples_leaf", 1),
        max_features=settings.get("max_features", "sqrt"),
        random_state=settings["random_state"],
        n_jobs=-1,
        class_weight="balanced",
    )


def build_xgboost(cfg: dict) -> XGBClassifier:
    settings = cfg["models"]["xgboost"]
    return XGBClassifier(
        n_estimators=settings["n_estimators"],
        max_depth=settings["max_depth"],
        learning_rate=settings["learning_rate"],
        min_child_weight=settings.get("min_child_weight", 1),
        subsample=settings.get("subsample", 1.0),
        colsample_bytree=settings.get("colsample_bytree", 1.0),
        reg_lambda=settings.get("reg_lambda", 1.0),
        scale_pos_weight=settings.get("scale_pos_weight", 1.0),
        random_state=settings["random_state"],
        eval_metric="logloss",
        tree_method=settings.get("tree_method", "hist"),
        n_jobs=-1,
    )