from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from fraud_stream.config import RAW_REPO_DIR, RAW_DATA_DIR, RAW_REPO_URL


def ensure_raw_repo() -> Path:
    """Clone simulated-data-raw if it is not present."""
    if RAW_REPO_DIR.exists():
        return RAW_DATA_DIR

    RAW_REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", RAW_REPO_URL, str(RAW_REPO_DIR)]
    subprocess.run(cmd, check=True)
    return RAW_DATA_DIR


def _date_range(begin_date: str, end_date: str):
    begin = datetime.strptime(begin_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    current = begin
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def read_from_daily_pickles(data_dir: Path, begin_date: str, end_date: str) -> pd.DataFrame:
    """Read daily .pkl files from Fraud Detection Handbook simulated-data-raw/data."""
    frames = []
    missing = []
    for day in _date_range(begin_date, end_date):
        path = data_dir / f"{day}.pkl"
        if not path.exists():
            missing.append(path.name)
            continue
        frames.append(pd.read_pickle(path))

    if not frames:
        raise FileNotFoundError(
            f"No .pkl files found in {data_dir} for period {begin_date}..{end_date}. "
            "Run ensure_raw_repo() or check dates."
        )

    if missing:
        print(f"[WARN] Missing {len(missing)} daily files. First missing: {missing[:5]}")

    df = pd.concat(frames, ignore_index=True)
    df["TX_DATETIME"] = pd.to_datetime(df["TX_DATETIME"])
    df = df.sort_values("TX_DATETIME").reset_index(drop=True)

    # Some files already contain TRANSACTION_ID, but make it monotonic after concat.
    if "TRANSACTION_ID" not in df.columns:
        df.insert(0, "TRANSACTION_ID", range(len(df)))
    return df


def load_transactions(begin_date: str = "2018-04-01", end_date: str = "2018-07-09") -> pd.DataFrame:
    data_dir = ensure_raw_repo()
    return read_from_daily_pickles(data_dir, begin_date, end_date)


if __name__ == "__main__":
    df = load_transactions()
    print(df.head())
    print(df.shape)
    print(df["TX_FRAUD"].value_counts(dropna=False))
