from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fraud_stream.config import ARTIFACTS_DIR, TARGET  # noqa: E402
from fraud_stream.data.load_handbook import load_transactions  # noqa: E402
from fraud_stream.features.build_features import build_feature_table  # noqa: E402
from fraud_stream.inference.production_engine import (  # noqa: E402
    ProductionFraudInferenceEngine,
    ProductionInferenceConfig,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run production LightGBM + autoencoder + SHAP inference on a small 30-day example."
    )
    parser.add_argument("--begin-date", default="2018-04-01")
    parser.add_argument("--end-date", default="2018-04-30")
    parser.add_argument(
        "--raw-sample-frac",
        type=float,
        default=1.0,
        help="Sample raw 30-day transactions before feature building for a faster demo.",
    )
    parser.add_argument("--sample-rows", type=int, default=25)
    parser.add_argument("--include-shap", action="store_true")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--vae-device",
        default="auto",
        choices=["auto", "cpu", "mps"],
        help="Use cpu/auto for stable demo runs on macOS.",
    )
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="Require existing production artifacts instead of training missing models.",
    )
    parser.add_argument(
        "--output",
        default=str(ARTIFACTS_DIR / "production_inference_demo_30d.json"),
    )
    args = parser.parse_args()

    print(
        f"[demo] loading raw transactions {args.begin_date}..{args.end_date}",
        flush=True,
    )
    raw = load_transactions(args.begin_date, args.end_date)
    if args.raw_sample_frac < 1.0:
        raw = (
            raw.sample(frac=args.raw_sample_frac, random_state=42)
            .sort_values("TX_DATETIME")
            .reset_index(drop=True)
        )
    print(f"[demo] raw shape={raw.shape}", flush=True)

    print("[demo] building engineered features", flush=True)
    features = build_feature_table(raw)

    sample = features.sort_values("TX_DATETIME").reset_index(drop=True)

    config = ProductionInferenceConfig(
        begin_date=args.begin_date,
        end_date=args.end_date,
        train_end_day=18,
        valid_end_day=24,
        vae_device=args.vae_device,
        train_if_missing=not args.no_train,
    )

    print("[demo] loading production inference engine", flush=True)
    engine = ProductionFraudInferenceEngine(config)

    print(
        f"[demo] scoring sample rows={len(sample)} include_shap={args.include_shap}",
        flush=True,
    )
    predictions = engine.score_features(
        sample,
        include_shap=args.include_shap,
        top_k=args.top_k,
    )

    rows = []
    for source, prediction in zip(sample.to_dict(orient="records"), predictions):
        rows.append(
            {
                "transaction_id": source.get("TRANSACTION_ID"),
                "tx_datetime": str(source.get("TX_DATETIME")),
                "tx_amount": float(source.get("TX_AMOUNT", 0.0)),
                "true_fraud": int(source.get(TARGET, 0)),
                **prediction,
            }
        )

    summary = {
        "period": {"begin_date": args.begin_date, "end_date": args.end_date},
        "raw_rows": int(len(raw)),
        "feature_rows": int(len(features)),
        "scored_rows": int(len(rows)),
        "fraud_rows_in_sample": int(sum(row["true_fraud"] for row in rows)),
        "decision_counts": {
            decision: sum(row["decision"] == decision for row in rows)
            for decision in ["approve", "manual_review", "decline"]
        },
    }

    result = {"summary": summary, "predictions": rows}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[demo] saved predictions to {output_path}", flush=True)


if __name__ == "__main__":
    main()
