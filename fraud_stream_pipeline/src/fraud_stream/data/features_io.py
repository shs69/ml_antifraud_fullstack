from __future__ import annotations

import pandas as pd

from fraud_stream.config import PROCESSED_DIR


def load_feature_table() -> pd.DataFrame:
    parquet_path = PROCESSED_DIR / "handbook_features.parquet"
    pickle_path = PROCESSED_DIR / "handbook_features.pkl"

    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if pickle_path.exists():
        return pd.read_pickle(pickle_path)

    raise FileNotFoundError("Feature table not found. Run scripts/run_all.py first.")
