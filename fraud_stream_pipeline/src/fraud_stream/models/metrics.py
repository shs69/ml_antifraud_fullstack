from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def recall_at_precision(y_true, y_score, min_precision: float = 0.90) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    valid = precision >= min_precision
    if not valid.any():
        return 0.0
    return float(recall[valid].max())


def threshold_for_target_recall(y_true, y_score, target_recall: float = 0.80) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    candidates = []
    for p, r, t in zip(precision[:-1], recall[:-1], thresholds):
        if r >= target_recall:
            candidates.append((p, r, t))
    if not candidates:
        return 0.5
    # among thresholds satisfying recall, maximize precision
    return float(max(candidates, key=lambda x: x[0])[2])


def evaluate_scores(y_true, y_score, threshold: float = 0.5) -> dict:
    y_pred = (np.asarray(y_score) >= threshold).astype(int)

    out = {
        "roc_auc": float(roc_auc_score(y_true, y_score)) if len(set(y_true)) > 1 else None,
        "pr_auc": float(average_precision_score(y_true, y_score)) if len(set(y_true)) > 1 else None,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "recall_at_precision_90": float(recall_at_precision(y_true, y_score, 0.90)),
        "threshold": float(threshold),
    }

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out.update({"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)})
    return out
