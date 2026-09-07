from __future__ import annotations

import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline

from .config import ROOT, load_config
from .baseline import build_baseline_model
from .data_cleaning import clean_data
from .data_quality import quality_report
from .data_validation import validate_data
from .ensemble_models import build_random_forest, build_xgboost
from .evaluation import classification_metrics, p95_latency_ms, slice_metrics, tune_threshold
from .feature_engineering import create_features, model_columns
from .feature_store import feature_contract_hash
from .model_gate import promotion_gate
from .pipeline import make_preprocessor
from .mlflow_registry import configure_mlflow, promote_alias, register_model, registry_enabled


def split_data(df, target, cfg):
    if "event_timestamp" in df.columns:
        ordered = df.sort_values("event_timestamp").reset_index(drop=True)
        n = len(ordered)
        train_end = int(n * 0.70)
        cal_end = int(n * 0.80)
        return ordered.iloc[:train_end], ordered.iloc[train_end:cal_end], ordered.iloc[cal_end:]
    from sklearn.model_selection import train_test_split
    train, test = train_test_split(df, test_size=cfg["model"]["test_size"], random_state=cfg["model"]["random_state"], stratify=df[target])
    train, cal = train_test_split(train, test_size=0.125, random_state=cfg["model"]["random_state"], stratify=train[target])
    return train, cal, test


def build_models(cfg):
    return {
        "LogisticRegression": build_baseline_model(cfg),
        "RandomForest": build_random_forest(cfg),
        "XGBoost": build_xgboost(cfg),
    }


def main():
    cfg = load_config()
    df = pd.read_csv(ROOT / cfg["data"]["raw_path"])
    if "event_timestamp" in df.columns:
        df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")
        if df["event_timestamp"].isna().any():
            raise ValueError("event_timestamp contains invalid values")
    validate_data(df)
    quality = quality_report(df)
    df = create_features(clean_data(df))
    target = cfg["model"]["target"]
    train_df, cal_df, test_df = split_data(df, target, cfg)
    X_train, y_train = train_df[model_columns()], train_df[target]
    X_cal, y_cal = cal_df[model_columns()], cal_df[target]
    X_test, y_test = test_df[model_columns()], test_df[target]
    cv = TimeSeriesSplit(n_splits=cfg["model"]["cv_folds"]) if "event_timestamp" in df.columns else StratifiedKFold(n_splits=cfg["model"]["cv_folds"], shuffle=True, random_state=cfg["model"]["random_state"])

    if registry_enabled(cfg):
        configure_mlflow(cfg, ROOT)

    fp_cost = cfg["business"]["false_positive_cost"]
    fn_cost = cfg["business"]["false_negative_cost"]
    min_recall = cfg["promotion_gate"]["min_recall"]
    results, candidates, registry_records = [], {}, {}

    for name, estimator in build_models(cfg).items():
        pipe = estimator if name == "LogisticRegression" else Pipeline([("preprocessor", make_preprocessor()), ("model", estimator)])
        cv_result = cross_validate(pipe, X_train, y_train, cv=cv, scoring=["f1", "roc_auc", "average_precision"], n_jobs=1)
        pipe.fit(X_train, y_train)
        cal_prob = pipe.predict_proba(X_cal)[:, 1]
        threshold_row = tune_threshold(y_cal, cal_prob, fp_cost, fn_cost, min_recall=min_recall)
        threshold = threshold_row["threshold"]
        test_prob = pipe.predict_proba(X_test)[:, 1]
        m = classification_metrics(y_test, test_prob, threshold, fp_cost, fn_cost)
        m.update({"model": name, "cv_f1_mean": float(np.mean(cv_result["test_f1"])), "cv_f1_std": float(np.std(cv_result["test_f1"])), "cv_auc_mean": float(np.mean(cv_result["test_roc_auc"])), "cv_pr_auc_mean": float(np.mean(cv_result["test_average_precision"]))})
        m["p95_latency_ms"] = p95_latency_ms(lambda: pipe.predict_proba(X_test.iloc[[0]])[:, 1], iterations=50)
        m["slices"] = slice_metrics(test_df, y_test, test_prob, threshold, fp_cost, fn_cost)
        results.append(m)
        candidates[name] = (pipe, m)

        registry_records[name] = register_model(
            pipe=pipe,
            run_name=f"candidate-{name}",
            metrics=m,
            params={
                "model": name,
                "threshold": threshold,
                "fp_cost": fp_cost,
                "fn_cost": fn_cost,
                "cv_folds": cfg["model"]["cv_folds"],
            },
            tags={
                "validation_strategy": "time_based" if "event_timestamp" in df.columns else "stratified",
                "quality_status": quality["status"],
                "lifecycle": "candidate",
                "dataset_rows": len(df),
                "train_rows": len(train_df),
                "calibration_rows": len(cal_df),
                "test_rows": len(test_df),
                "target_rate": float(df[target].mean()),
                "feature_version": cfg["project"]["feature_version"],
                "feature_contract_hash": feature_contract_hash(cfg["project"]["feature_version"]),
                "project_version": cfg["project"]["version"],
            },
            cfg=cfg,
            root=ROOT,
        )
        print(name, json.dumps({k: v for k, v in m.items() if k != "slices"}, indent=2))

    model_dir = ROOT / "models"
    model_dir.mkdir(exist_ok=True)
    validation_strategy = "time_based" if "event_timestamp" in df.columns else "stratified"
    artifact_names = {
        "LogisticRegression": "baseline",
        "RandomForest": "random_forest",
        "XGBoost": "xgboost",
    }
    for model_name, artifact_name in artifact_names.items():
        fitted_pipe, fitted_metrics = candidates[model_name]
        joblib.dump(fitted_pipe, model_dir / f"{artifact_name}.joblib")
        (model_dir / f"{artifact_name}_metadata.json").write_text(
            json.dumps(
                {
                    "model": model_name,
                    "role": "baseline" if model_name == "LogisticRegression" else "challenger",
                    "metrics": fitted_metrics,
                    "project_version": cfg["project"]["version"],
                    "feature_version": cfg["project"]["feature_version"],
                    "feature_contract_hash": feature_contract_hash(cfg["project"]["feature_version"]),
                    "validation_strategy": validation_strategy,
                    "registry": registry_records.get(model_name, {}),
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
    production_path = model_dir / "production_metadata.json"
    production = json.loads(production_path.read_text(encoding="utf-8")) if production_path.exists() else None

    eligible = [r for r in results if r["recall"] >= min_recall]
    if not eligible:
        eligible = results
    candidate = min(eligible, key=lambda r: (r["business_cost"], -r["f1"]))
    champion_name = candidate["model"]
    champion_pipe = candidates[champion_name][0]
    gate = {"passed": True, "checks": {"initial_model": True}, "reasons": []}
    promoted_registry = None

    if production:
        gate = promotion_gate(candidate, production, cfg["promotion_gate"])
        if not gate["passed"]:
            champion_name = production["model"]
            champion_pipe = joblib.load(model_dir / "champion.joblib")
            candidate = production
        else:
            promoted_registry = registry_records.get(champion_name)
    else:
        promoted_registry = registry_records.get(champion_name)

    if promoted_registry and promoted_registry.get("registered"):
        alias_result = promote_alias(cfg, ROOT, promoted_registry["version"], status="approved")
    else:
        alias_result = {"enabled": False, "promoted": False, "reason": "No new registry version promoted"}

    joblib.dump(champion_pipe, model_dir / "champion.joblib")
    metadata = {
        "champion": champion_name,
        "candidate_selected": candidate["model"],
        "promotion_gate": gate,
        "metrics": results,
        "registry": {"candidates": registry_records, "promotion": alias_result},
        "data_quality": quality,
        "reference_columns": model_columns(),
        "feature_contract_hash": feature_contract_hash(cfg["project"]["feature_version"]),
        "business_costs": {"false_positive": fp_cost, "false_negative": fn_cost},
        "project_version": cfg["project"]["version"],
    }
    (model_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    if not production or gate["passed"]:
        production_record = dict(candidate)
        production_record["registry"] = promoted_registry or {}
        production_path.write_text(json.dumps(production_record, indent=2, default=str), encoding="utf-8")

    print(f"Champion: {champion_name}; promotion gate: {gate['passed']}; registry: {alias_result}")


if __name__ == "__main__":
    main()
