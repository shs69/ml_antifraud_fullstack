from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from fraud_stream.config import PROCESSED_DIR
from fraud_stream.features.build_features import get_model_columns
from fraud_stream.explain.shap_reasons import explain_with_shap, simple_reason_codes


def main():
    df = pd.read_parquet(PROCESSED_DIR / "handbook_features.parquet")
    sample = df.sample(n=min(200, len(df)), random_state=42)
    X = sample[get_model_columns(sample)]

    shap_df = explain_with_shap(X, max_rows=200)
    print(shap_df.abs().mean().sort_values(ascending=False).head(20))

    fraud_examples = sample[sample["TX_FRAUD"] == 1].head(5)
    for _, row in fraud_examples.iterrows():
        print({
            "TRANSACTION_ID": int(row.get("TRANSACTION_ID", -1)),
            "scenario": int(row.get("TX_FRAUD_SCENARIO", -1)),
            "amount": float(row["TX_AMOUNT"]),
            "reasons": simple_reason_codes(row),
        })


if __name__ == "__main__":
    main()
