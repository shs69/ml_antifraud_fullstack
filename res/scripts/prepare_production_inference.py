from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fraud_stream.inference.production_engine import (  # noqa: E402
    ProductionInferenceConfig,
    ProductionFraudInferenceEngine,
    ensure_production_models,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--begin-date", default="2018-04-01")
    parser.add_argument("--end-date", default="2018-07-09")
    parser.add_argument("--train-end-day", type=int, default=60)
    parser.add_argument("--valid-end-day", type=int, default=80)
    parser.add_argument(
        "--vae-device",
        default="auto",
        choices=["auto", "cpu", "mps"],
        help="Use cpu for stable production inference on macOS.",
    )
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="Only load existing artifacts; fail if LightGBM or autoencoder is missing.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Instantiate the engine after preparing artifacts.",
    )
    args = parser.parse_args()

    config = ProductionInferenceConfig(
        begin_date=args.begin_date,
        end_date=args.end_date,
        train_end_day=args.train_end_day,
        valid_end_day=args.valid_end_day,
        vae_device=args.vae_device,
        train_if_missing=not args.no_train,
    )

    metadata = ensure_production_models(config)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))

    if args.smoke:
        ProductionFraudInferenceEngine(config)
        print("[production] engine loaded")


if __name__ == "__main__":
    main()
