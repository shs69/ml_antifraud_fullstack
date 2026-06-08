from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from fraud_stream.features.build_features import build_feature_table
from fraud_stream.models.splits import temporal_split_by_days


def make_tiny_data(n=1000):
    rng = np.random.default_rng(42)
    t0 = pd.Timestamp("2018-04-01")
    df = pd.DataFrame({
        "TRANSACTION_ID": np.arange(n),
        "TX_DATETIME": [t0 + pd.Timedelta(minutes=int(i * 10)) for i in range(n)],
        "CUSTOMER_ID": rng.integers(0, 50, n),
        "TERMINAL_ID": rng.integers(0, 100, n),
        "TX_AMOUNT": rng.gamma(2, 30, n).round(2),
        "TX_TIME_SECONDS": np.arange(n) * 600,
        "TX_TIME_DAYS": (np.arange(n) * 600 // 86400).astype(int),
    })
    df["TX_FRAUD"] = ((df["TX_AMOUNT"] > 160) | (rng.random(n) < 0.01)).astype(int)
    df["TX_FRAUD_SCENARIO"] = np.where(df["TX_FRAUD"] == 1, 1, 0)
    return df


if __name__ == "__main__":
    df = make_tiny_data()
    features = build_feature_table(df)
    train, valid, test = temporal_split_by_days(features, train_end_day=3, valid_end_day=5)
    print(features.head())
    print(train.shape, valid.shape, test.shape)
    print("OK")
