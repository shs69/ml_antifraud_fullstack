from __future__ import annotations

import json
from typing import Literal

import joblib
import numpy as np
import pandas as pd

from fraud_stream.config import ARTIFACTS_DIR, TARGET
from fraud_stream.models.metrics import evaluate_scores, threshold_for_target_recall
from fraud_stream.models.torch_autoencoder import score_vae_anomaly_model


FusionName = Literal[
    "weighted_average",
    "max",
    "probabilistic_or",
]


def score_autoencoder(bundle: dict, X: pd.DataFrame) -> np.ndarray:
    preprocessor = bundle["preprocessor"]
    scaler = bundle["score_scaler"]

    Xt = preprocessor.transform(X)
    if bundle.get("model_type") == "vae":
        err = score_vae_anomaly_model(bundle["vae"], Xt)
    else:
        ae = bundle["autoencoder"]
        pred = ae.predict(Xt)
        err = np.mean((Xt - pred) ** 2, axis=1)
    return scaler.transform(err.reshape(-1, 1)).ravel()


def score_autoencoder_percentile(bundle: dict, X: pd.DataFrame) -> np.ndarray:
    preprocessor = bundle["preprocessor"]
    reference = np.asarray(bundle.get("reference_scores", []), dtype=float)
    Xt = preprocessor.transform(X)

    if bundle.get("model_type") == "vae":
        err = score_vae_anomaly_model(bundle["vae"], Xt)
    else:
        ae = bundle["autoencoder"]
        pred = ae.predict(Xt)
        err = np.mean((Xt - pred) ** 2, axis=1)

    if len(reference) == 0:
        return np.zeros(len(err), dtype=float)
    return np.searchsorted(reference, err, side="right") / len(reference)


def fuse_scores(
    supervised_scores: np.ndarray,
    anomaly_scores: np.ndarray,
    method: FusionName = "probabilistic_or",
    supervised_weight: float = 0.7,
) -> np.ndarray:
    supervised_scores = np.asarray(supervised_scores)
    anomaly_scores = np.asarray(anomaly_scores)

    if method == "weighted_average":
        return supervised_weight * supervised_scores + (1 - supervised_weight) * anomaly_scores

    if method == "max":
        return np.maximum(supervised_scores, anomaly_scores)

    if method == "probabilistic_or":
        return 1 - (1 - supervised_scores) * (1 - anomaly_scores)

    raise ValueError(f"Unknown fusion method: {method}")


def make_hybrid_scores(
    supervised_scores: np.ndarray,
    anomaly_scores: np.ndarray,
    supervised_weight: float = 0.7,
) -> np.ndarray:
    """Backward-compatible weighted hybrid."""
    return fuse_scores(
        supervised_scores,
        anomaly_scores,
        method="weighted_average",
        supervised_weight=supervised_weight,
    )


def threshold_by_normal_quantile(
    y_valid: np.ndarray,
    scores: np.ndarray,
    normal_quantile: float = 0.995,
) -> float:
    y_valid = np.asarray(y_valid).astype(int)
    scores = np.asarray(scores)
    normal_scores = scores[y_valid == 0]

    if len(normal_scores) == 0:
        return float(np.quantile(scores, normal_quantile))

    return float(np.quantile(normal_scores, normal_quantile))


def evaluate_binary_alerts(y_true, alerts: np.ndarray) -> dict:
    """Evaluate already-thresholded alerts.

    Adds ROC/PR placeholders as None because alerts are binary decisions, not continuous scores.
    """
    from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

    alerts = np.asarray(alerts).astype(int)
    y_true = np.asarray(y_true).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, alerts, labels=[0, 1]).ravel()

    return {
        "roc_auc": None,
        "pr_auc": None,
        "precision": float(precision_score(y_true, alerts, zero_division=0)),
        "recall": float(recall_score(y_true, alerts, zero_division=0)),
        "f1": float(f1_score(y_true, alerts, zero_division=0)),
        "recall_at_precision_90": None,
        "threshold": None,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def evaluate_two_threshold_or(
    y_valid,
    y_test,
    valid_sup,
    test_sup,
    valid_anom,
    test_anom,
    supervised_threshold: float,
    anomaly_normal_quantile: float = 0.995,
) -> dict:
    """Two-channel hybrid decision.

    supervised branch threshold is selected by supervised validation target recall.
    anomaly branch threshold is selected as a quantile of normal validation scores.

    hybrid_alert = supervised_alert OR anomaly_alert
    """
    anomaly_threshold = threshold_by_normal_quantile(
        y_valid,
        valid_anom,
        normal_quantile=anomaly_normal_quantile,
    )

    valid_alert = (valid_sup >= supervised_threshold) | (valid_anom >= anomaly_threshold)
    test_alert = (test_sup >= supervised_threshold) | (test_anom >= anomaly_threshold)

    return {
        "valid": evaluate_binary_alerts(y_valid, valid_alert),
        "test": evaluate_binary_alerts(y_test, test_alert),
        "supervised_threshold": float(supervised_threshold),
        "anomaly_threshold": float(anomaly_threshold),
        "anomaly_normal_quantile": float(anomaly_normal_quantile),
        "decision_rule": "supervised_score >= supervised_threshold OR anomaly_score >= anomaly_threshold",
    }


def evaluate_hybrid(valid: pd.DataFrame, test: pd.DataFrame, feature_cols: list[str]) -> dict:
    """Default temporal-split hybrid evaluation.

    Kept for compatibility with scripts/run_all.py.
    """
    supervised = joblib.load(ARTIFACTS_DIR / "best_supervised_pipeline.joblib")
    anomaly = joblib.load(ARTIFACTS_DIR / "autoencoder_anomaly.joblib")

    valid_sup = supervised.predict_proba(valid[feature_cols])[:, 1]
    test_sup = supervised.predict_proba(test[feature_cols])[:, 1]

    valid_anom = score_autoencoder(anomaly, valid[feature_cols])
    test_anom = score_autoencoder(anomaly, test[feature_cols])

    valid_hybrid = fuse_scores(valid_sup, valid_anom, method="probabilistic_or")
    test_hybrid = fuse_scores(test_sup, test_anom, method="probabilistic_or")

    threshold = threshold_for_target_recall(valid[TARGET].astype(int), valid_hybrid, target_recall=0.80)

    results = {
        "valid": evaluate_scores(valid[TARGET].astype(int), valid_hybrid, threshold),
        "test": evaluate_scores(test[TARGET].astype(int), test_hybrid, threshold),
        "threshold": threshold,
        "fusion": "probabilistic_or",
    }

    with open(ARTIFACTS_DIR / "hybrid_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results
