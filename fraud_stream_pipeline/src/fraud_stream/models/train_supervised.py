from __future__ import annotations

import json

import joblib
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from fraud_stream.config import ARTIFACTS_DIR, RANDOM_STATE, TARGET
from fraud_stream.features.build_features import get_model_columns
from fraud_stream.models.metrics import evaluate_scores, threshold_for_target_recall


def _optional_xgb(scale_pos_weight: float):
    try:
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            tree_method="hist",
            random_state=RANDOM_STATE,
            scale_pos_weight=scale_pos_weight,
            # XGBoost wheels on macOS can crash in OpenMP when several ML
            # libraries load their own libomp. Keep the model, limit threads.
            n_jobs=1,
        )
    except Exception as e:
        print(f"[warn] xgboost unavailable: {type(e).__name__}: {e}")
        return None


def _optional_lgbm(scale_pos_weight: float):
    try:
        from lightgbm import LGBMClassifier

        return LGBMClassifier(
            n_estimators=500,
            learning_rate=0.05,
            num_leaves=63,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=RANDOM_STATE,
            class_weight={0: 1.0, 1: scale_pos_weight},
            # Keep native thread pools from fighting with PyTorch VAE later in
            # the same process on macOS.
            n_jobs=1,
            verbose=-1,
        )
    except Exception as e:
        print(f"[warn] lightgbm unavailable: {type(e).__name__}: {e}")
        return None


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    numeric_cols = list(X.columns)

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler(with_mean=False)),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_cols),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )


def scale_pos_weight_for(y_train: pd.Series) -> float:
    fraud = int(y_train.sum())
    non_fraud = int((y_train == 0).sum())
    return max(non_fraud / max(fraud, 1), 1.0)


def get_base_models() -> dict:
    return {
        "logreg": LogisticRegression(
            max_iter=300,
            class_weight="balanced",
            solver="lbfgs",
            random_state=RANDOM_STATE,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=250,
            min_samples_leaf=5,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=1,
        ),
    }


def train_supervised_models(train: pd.DataFrame, valid: pd.DataFrame, test: pd.DataFrame) -> dict:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    feature_cols = get_model_columns(train)
    X_train, y_train = train[feature_cols], train[TARGET].astype(int)
    X_valid, y_valid = valid[feature_cols], valid[TARGET].astype(int)
    X_test, y_test = test[feature_cols], test[TARGET].astype(int)

    results = {}
    best_name = None
    best_pr_auc = -1

    def train_one(name: str, estimator):
        nonlocal best_name, best_pr_auc
        print(f"[train] {name} started")
        pipe = Pipeline(
            steps=[
                ("preprocessor", build_preprocessor(X_train)),
                ("model", estimator),
            ]
        )
        pipe.fit(X_train, y_train)
        print(f"[train] {name} finished")

        valid_score = pipe.predict_proba(X_valid)[:, 1]
        threshold = threshold_for_target_recall(y_valid, valid_score, target_recall=0.80)

        test_score = pipe.predict_proba(X_test)[:, 1]
        valid_metrics = evaluate_scores(y_valid, valid_score, threshold)
        test_metrics = evaluate_scores(y_test, test_score, threshold)

        results[name] = {
            "valid": valid_metrics,
            "test": test_metrics,
            "threshold": threshold,
            "feature_cols": feature_cols,
        }

        joblib.dump(pipe, ARTIFACTS_DIR / f"{name}_pipeline.joblib")

        pr_auc = test_metrics["pr_auc"] or -1
        if pr_auc > best_pr_auc:
            best_pr_auc = pr_auc
            best_name = name

    for name, estimator in get_base_models().items():
        train_one(name, estimator)

    scale_pos_weight = scale_pos_weight_for(y_train)
    xgb = _optional_xgb(scale_pos_weight)
    if xgb is not None:
        train_one("xgboost", xgb)

    lgbm = _optional_lgbm(scale_pos_weight)
    if lgbm is not None:
        train_one("lightgbm", lgbm)

    results["best_model"] = best_name

    with open(ARTIFACTS_DIR / "supervised_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if best_name:
        best_pipe = joblib.load(ARTIFACTS_DIR / f"{best_name}_pipeline.joblib")
        joblib.dump(best_pipe, ARTIFACTS_DIR / "best_supervised_pipeline.joblib")

    return results
