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
from fraud_stream.models.metrics import evaluate_scores, threshold_for_target_recall
from fraud_stream.models.splits import unseen_scenario_split
from fraud_stream.models.train_supervised import build_preprocessor, _optional_lgbm
from fraud_stream.models.train_anomaly import train_autoencoder
from fraud_stream.models.hybrid import make_hybrid_scores, score_autoencoder


def split_train_valid_by_time(df: pd.DataFrame, valid_frac: float = 0.25):
    df = df.sort_values("TX_DATETIME").copy()
    cutoff_idx = int(len(df) * (1 - valid_frac))

    train = df.iloc[:cutoff_idx].copy()
    valid = df.iloc[cutoff_idx:].copy()

    return train, valid


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


def print_compact_table(results: dict):
    rows = []
    for name in ["supervised_lightgbm", "autoencoder", "hybrid"]:
        m = results[name]["test"]
        rows.append({
            "model": name,
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
    parser.add_argument("--supervised-weight", type=float, default=0.7)
    parser.add_argument(
        "--target-recall",
        type=float,
        default=0.80,
        help="Threshold is selected on validation to reach this recall when possible.",
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

    print("[1/5] Building unseen-scenario split")
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
    }
    print(json.dumps(split_info, ensure_ascii=False, indent=2))

    print("[2/5] Training supervised LightGBM without held-out scenario")
    supervised, feature_cols = train_lightgbm_only(us_train)

    valid_sup = supervised.predict_proba(us_valid[feature_cols])[:, 1]
    test_sup = supervised.predict_proba(us_test[feature_cols])[:, 1]

    sup_threshold = threshold_for_target_recall(
        us_valid[TARGET].astype(int),
        valid_sup,
        target_recall=args.target_recall,
    )

    supervised_metrics = {
        "valid": evaluate_scores(us_valid[TARGET].astype(int), valid_sup, sup_threshold),
        "test": evaluate_scores(us_test[TARGET].astype(int), test_sup, sup_threshold),
        "threshold": sup_threshold,
    }

    print("[3/5] Training autoencoder anomaly model")
    anomaly_metrics = train_autoencoder(
        us_train,
        us_valid,
        us_test,
        vae_model_path=args.vae_model_path,
        vae_device=args.vae_device,
    )
    anomaly_bundle = joblib.load(ARTIFACTS_DIR / "autoencoder_anomaly.joblib")

    valid_anom = score_autoencoder(anomaly_bundle, us_valid[feature_cols])
    test_anom = score_autoencoder(anomaly_bundle, us_test[feature_cols])

    print("[4/5] Evaluating hybrid")
    valid_hybrid = make_hybrid_scores(
        valid_sup,
        valid_anom,
        supervised_weight=args.supervised_weight,
    )
    test_hybrid = make_hybrid_scores(
        test_sup,
        test_anom,
        supervised_weight=args.supervised_weight,
    )

    hybrid_threshold = threshold_for_target_recall(
        us_valid[TARGET].astype(int),
        valid_hybrid,
        target_recall=args.target_recall,
    )

    hybrid_metrics = {
        "valid": evaluate_scores(us_valid[TARGET].astype(int), valid_hybrid, hybrid_threshold),
        "test": evaluate_scores(us_test[TARGET].astype(int), test_hybrid, hybrid_threshold),
        "threshold": hybrid_threshold,
        "supervised_weight": args.supervised_weight,
    }

    print("[5/5] Saving results")
    results = {
        "split": split_info,
        "supervised_lightgbm": supervised_metrics,
        "autoencoder": anomaly_metrics,
        "hybrid": hybrid_metrics,
    }

    out_path = ARTIFACTS_DIR / f"unseen_scenario_{args.heldout_scenario}_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print_compact_table(results)
    print("\nFull JSON:")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
