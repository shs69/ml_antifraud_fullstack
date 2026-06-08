from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from fraud_stream.config import ARTIFACTS_DIR, PROCESSED_DIR
from fraud_stream.data.load_handbook import load_transactions
from fraud_stream.features.build_features import build_feature_table, get_model_columns
from fraud_stream.models.hybrid import evaluate_hybrid
from fraud_stream.models.splits import temporal_split_by_days, unseen_scenario_split
from fraud_stream.models.train_anomaly import train_anomaly_models
from fraud_stream.models.train_supervised import train_supervised_models


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--begin-date", default="2018-04-01")
    parser.add_argument("--end-date", default="2018-07-09")
    parser.add_argument("--train-end-day", type=int, default=60)
    parser.add_argument("--valid-end-day", type=int, default=80)
    parser.add_argument("--heldout-scenario", type=int, default=3)
    parser.add_argument(
        "--sample-frac",
        type=float,
        default=1.0,
        help="Use smaller value like 0.2 for quick smoke tests.",
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
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/6] Loading transactions")
    # raw = load_transactions(args.begin_date, args.end_date)
    #
    # if args.sample_frac < 1.0:
    #     raw = (
    #         raw.sample(frac=args.sample_frac, random_state=42)
    #         .sort_values("TX_DATETIME")
    #         .reset_index(drop=True)
    #     )
    #
    # print(raw.head())
    # print(raw.shape)
    # print(raw["TX_FRAUD"].value_counts())
    #
    # print("[2/6] Building features")
    # features = build_feature_table(raw)
    # features.to_parquet(PROCESSED_DIR / "handbook_features.parquet", index=False)
    features = pd.read_parquet(PROCESSED_DIR / "features.parquet")

    print("[3/6] Temporal split")
    train, valid, test = temporal_split_by_days(
        features,
        train_end_day=args.train_end_day,
        valid_end_day=args.valid_end_day,
    )
    print({"train": train.shape, "valid": valid.shape, "test": test.shape})
    print(
        {
            "train_fraud": int(train["TX_FRAUD"].sum()),
            "valid_fraud": int(valid["TX_FRAUD"].sum()),
            "test_fraud": int(test["TX_FRAUD"].sum()),
        }
    )

    print("[4/6] Training supervised models")
    supervised_results = train_supervised_models(train, valid, test)
    print(json.dumps(supervised_results, indent=2, ensure_ascii=False)[:5000])

    print("[5/6] Training anomaly models")
    anomaly_results = train_anomaly_models(
        train,
        valid,
        test,
        vae_model_path=args.vae_model_path,
        vae_device=args.vae_device,
    )
    print(json.dumps(anomaly_results, indent=2, ensure_ascii=False)[:5000])

    print("[6/6] Hybrid evaluation")
    hybrid_results = evaluate_hybrid(valid, test, get_model_columns(train))
    print(json.dumps(hybrid_results, indent=2, ensure_ascii=False))

    print("[extra] Unseen fraud scenario split")
    us_train, us_test = unseen_scenario_split(
        features,
        heldout_scenario=args.heldout_scenario,
        train_end_day=args.train_end_day,
    )
    print(
        {
            "heldout_scenario": args.heldout_scenario,
            "train_shape": us_train.shape,
            "test_shape": us_test.shape,
            "train_scenario_counts": us_train["TX_FRAUD_SCENARIO"]
            .value_counts()
            .to_dict(),
            "test_scenario_counts": us_test["TX_FRAUD_SCENARIO"]
            .value_counts()
            .to_dict(),
        }
    )

    print(f"Artifacts saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
