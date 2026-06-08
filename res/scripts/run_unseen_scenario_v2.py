from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from fraud_stream.config import ARTIFACTS_DIR, TARGET
from fraud_stream.data.features_io import load_feature_table
from fraud_stream.features.build_features import get_model_columns
from fraud_stream.models.hybrid import (
    evaluate_two_threshold_or,
    fuse_scores,
    score_autoencoder,
    threshold_by_normal_quantile,
)
from fraud_stream.models.metrics import evaluate_scores, threshold_for_target_recall
from fraud_stream.models.splits import unseen_scenario_split
from fraud_stream.models.train_anomaly import train_autoencoder
from fraud_stream.models.train_supervised import _optional_lgbm, build_preprocessor


def split_train_valid_by_time(df: pd.DataFrame, valid_frac: float = 0.25):
    df = df.sort_values("TX_DATETIME").copy()
    cutoff_idx = int(len(df) * (1 - valid_frac))
    return df.iloc[:cutoff_idx].copy(), df.iloc[cutoff_idx:].copy()


def train_lightgbm_only(train: pd.DataFrame):
    feature_cols = get_model_columns(train)
    X_train = train[feature_cols]
    y_train = train[TARGET].astype(int)

    fraud = int(y_train.sum())
    non_fraud = int((y_train == 0).sum())
    scale_pos_weight = max(non_fraud / max(fraud, 1), 1.0)

    model = _optional_lgbm(scale_pos_weight)
    if model is None:
        raise RuntimeError("LightGBM is not installed. Run: pip install lightgbm")

    pipe = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor(X_train)),
            ("model", model),
        ]
    )
    pipe.fit(X_train, y_train)
    return pipe, feature_cols


def continuous_fusion_metrics(
    name: str,
    y_valid,
    y_test,
    valid_scores,
    test_scores,
    target_recall: float,
) -> dict:
    threshold = threshold_for_target_recall(y_valid, valid_scores, target_recall=target_recall)
    return {
        "name": name,
        "valid": evaluate_scores(y_valid, valid_scores, threshold),
        "test": evaluate_scores(y_test, test_scores, threshold),
        "threshold": float(threshold),
    }


def anomaly_quantile_metrics(
    y_valid,
    y_test,
    valid_anom,
    test_anom,
    normal_quantile: float,
) -> dict:
    threshold = threshold_by_normal_quantile(
        y_valid,
        valid_anom,
        normal_quantile=normal_quantile,
    )

    return {
        "name": "autoencoder_threshold",
        "valid": evaluate_scores(y_valid, valid_anom, threshold),
        "test": evaluate_scores(y_test, test_anom, threshold),
        "threshold": float(threshold),
        "threshold_strategy": f"normal_validation_quantile_{normal_quantile}",
    }


def print_compact_table(results: dict):
    rows = []

    for key in [
        "supervised_lightgbm",
        "autoencoder_recall_threshold",
        "autoencoder_quantile_threshold",
        "hybrid_weighted_average",
        "hybrid_max",
        "hybrid_probabilistic_or",
        "hybrid_two_threshold_or",
    ]:
        m = results[key]["test"]
        rows.append({
            "model": key,
            "roc_auc": m["roc_auc"],
            "pr_auc": m["pr_auc"],
            "precision": m["precision"],
            "recall": m["recall"],
            "f1": m["f1"],
            "recall_at_precision_90": m["recall_at_precision_90"],
            "fp": m["fp"],
            "fn": m["fn"],
            "tp": m["tp"],
        })

    df = pd.DataFrame(rows)
    print("\n=== TEST COMPARISON ===")
    print(df.to_string(index=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout-scenario", type=int, default=3)
    parser.add_argument("--train-end-day", type=int, default=60)
    parser.add_argument("--valid-frac", type=float, default=0.25)
    parser.add_argument("--target-recall", type=float, default=0.80)
    parser.add_argument("--supervised-weight", type=float, default=0.7)
    parser.add_argument(
        "--anomaly-normal-quantile",
        type=float,
        default=0.995,
        help="Anomaly branch threshold from normal validation scores. 0.995 means top 0.5 percent normal FPR.",
    )
    parser.add_argument(
        "--vae-model-path",
        default=None,
        help="Optional path to a trained VAE .pt checkpoint to score instead of retraining.",
    )
    parser.add_argument(
        "--vae-device",
        default="auto",
        choices=["auto", "cpu", "mps"],
        help="Device for VAE training/scoring. Use cpu if MPS stalls after supervised training.",
    )
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_feature_table()

    print("[1/6] Building unseen-scenario split")
    us_train_full, us_test = unseen_scenario_split(
        df,
        heldout_scenario=args.heldout_scenario,
        train_end_day=args.train_end_day,
    )
    us_train, us_valid = split_train_valid_by_time(us_train_full, valid_frac=args.valid_frac)

    split_info = {
        "heldout_scenario": args.heldout_scenario,
        "train": us_train.shape,
        "valid": us_valid.shape,
        "test": us_test.shape,
        "train_scenarios": us_train["TX_FRAUD_SCENARIO"].value_counts().to_dict(),
        "valid_scenarios": us_valid["TX_FRAUD_SCENARIO"].value_counts().to_dict(),
        "test_scenarios": us_test["TX_FRAUD_SCENARIO"].value_counts().to_dict(),
        "model_columns": get_model_columns(us_train),
    }
    print(json.dumps(split_info, ensure_ascii=False, indent=2))

    print("[2/6] Training supervised LightGBM without held-out scenario")
    supervised, feature_cols = train_lightgbm_only(us_train)

    y_valid = us_valid[TARGET].astype(int)
    y_test = us_test[TARGET].astype(int)

    valid_sup = supervised.predict_proba(us_valid[feature_cols])[:, 1]
    test_sup = supervised.predict_proba(us_test[feature_cols])[:, 1]

    supervised_result = continuous_fusion_metrics(
        "supervised_lightgbm",
        y_valid,
        y_test,
        valid_sup,
        test_sup,
        target_recall=args.target_recall,
    )
    supervised_threshold = supervised_result["threshold"]

    print("[3/6] Training autoencoder anomaly model")
    # train_autoencoder still computes its own recall-threshold metrics.
    autoencoder_recall_threshold = train_autoencoder(
        us_train,
        us_valid,
        us_test,
        vae_model_path=args.vae_model_path,
        vae_device=args.vae_device,
    )

    anomaly_bundle = joblib.load(ARTIFACTS_DIR / "autoencoder_anomaly.joblib")
    valid_anom = score_autoencoder(anomaly_bundle, us_valid[feature_cols])
    test_anom = score_autoencoder(anomaly_bundle, us_test[feature_cols])

    print("[4/6] Evaluating anomaly quantile threshold")
    autoencoder_quantile_threshold = anomaly_quantile_metrics(
        y_valid,
        y_test,
        valid_anom,
        test_anom,
        normal_quantile=args.anomaly_normal_quantile,
    )

    print("[5/6] Evaluating hybrid fusion strategies")
    valid_weighted = fuse_scores(
        valid_sup,
        valid_anom,
        method="weighted_average",
        supervised_weight=args.supervised_weight,
    )
    test_weighted = fuse_scores(
        test_sup,
        test_anom,
        method="weighted_average",
        supervised_weight=args.supervised_weight,
    )

    valid_max = fuse_scores(valid_sup, valid_anom, method="max")
    test_max = fuse_scores(test_sup, test_anom, method="max")

    valid_or = fuse_scores(valid_sup, valid_anom, method="probabilistic_or")
    test_or = fuse_scores(test_sup, test_anom, method="probabilistic_or")

    hybrid_weighted = continuous_fusion_metrics(
        "hybrid_weighted_average",
        y_valid,
        y_test,
        valid_weighted,
        test_weighted,
        target_recall=args.target_recall,
    )
    hybrid_weighted["supervised_weight"] = args.supervised_weight

    hybrid_max = continuous_fusion_metrics(
        "hybrid_max",
        y_valid,
        y_test,
        valid_max,
        test_max,
        target_recall=args.target_recall,
    )

    hybrid_probabilistic_or = continuous_fusion_metrics(
        "hybrid_probabilistic_or",
        y_valid,
        y_test,
        valid_or,
        test_or,
        target_recall=args.target_recall,
    )

    hybrid_two_threshold_or = evaluate_two_threshold_or(
        y_valid=y_valid,
        y_test=y_test,
        valid_sup=valid_sup,
        test_sup=test_sup,
        valid_anom=valid_anom,
        test_anom=test_anom,
        supervised_threshold=supervised_threshold,
        anomaly_normal_quantile=args.anomaly_normal_quantile,
    )

    print("[6/6] Saving results")
    results = {
        "split": split_info,
        "supervised_lightgbm": supervised_result,
        "autoencoder_recall_threshold": autoencoder_recall_threshold,
        "autoencoder_quantile_threshold": autoencoder_quantile_threshold,
        "hybrid_weighted_average": hybrid_weighted,
        "hybrid_max": hybrid_max,
        "hybrid_probabilistic_or": hybrid_probabilistic_or,
        "hybrid_two_threshold_or": hybrid_two_threshold_or,
        "settings": {
            "target_recall": args.target_recall,
            "supervised_weight": args.supervised_weight,
            "anomaly_normal_quantile": args.anomaly_normal_quantile,
        },
    }

    out_path = ARTIFACTS_DIR / f"unseen_scenario_{args.heldout_scenario}_v2_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print_compact_table(results)
    print("\nFull JSON:")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
