from __future__ import annotations

import numpy as np
import pandas as pd


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["TX_DATETIME"] = pd.to_datetime(df["TX_DATETIME"])
    df["hour"] = df["TX_DATETIME"].dt.hour
    df["dayofweek"] = df["TX_DATETIME"].dt.dayofweek
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    df["is_night"] = ((df["hour"] <= 6) | (df["hour"] >= 23)).astype(int)
    return df


def _rolling_customer_features_for_group(group: pd.DataFrame, windows_days=(1, 7, 30)) -> pd.DataFrame:
    group = group.sort_values("TX_DATETIME").copy()
    indexed = group.set_index("TX_DATETIME")
    amount = indexed["TX_AMOUNT"]

    result = pd.DataFrame(index=group.index)

    for w in windows_days:
        roll = amount.rolling(f"{w}D", closed="left")
        result[f"customer_nb_tx_{w}d"] = roll.count().to_numpy()
        result[f"customer_avg_amount_{w}d"] = roll.mean().to_numpy()
        result[f"customer_sum_amount_{w}d"] = roll.sum().to_numpy()

    return result


def add_customer_behavior_features(df: pd.DataFrame, windows_days=(1, 7, 30)) -> pd.DataFrame:
    df = df.sort_values(["CUSTOMER_ID", "TX_DATETIME"]).copy()
    parts = []
    for _, group in df.groupby("CUSTOMER_ID", sort=False):
        parts.append(_rolling_customer_features_for_group(group, windows_days))

    features = pd.concat(parts).sort_index()
    df = df.join(features)

    global_median = df["TX_AMOUNT"].median()
    for col in features.columns:
        if "nb_tx" in col or "sum_amount" in col:
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna(global_median)

    df["amount_ratio_to_customer_avg_7d"] = df["TX_AMOUNT"] / (df["customer_avg_amount_7d"] + 1e-6)

    df = df.sort_values(["CUSTOMER_ID", "TX_DATETIME"]).copy()
    past_mean = df.groupby("CUSTOMER_ID")["TX_AMOUNT"].transform(lambda s: s.expanding().mean().shift(1))
    past_std = df.groupby("CUSTOMER_ID")["TX_AMOUNT"].transform(lambda s: s.expanding().std().shift(1))
    df["amount_zscore_customer"] = (df["TX_AMOUNT"] - past_mean) / (past_std + 1e-6)
    df["amount_zscore_customer"] = df["amount_zscore_customer"].replace([np.inf, -np.inf], 0).fillna(0)

    return df


def _rolling_customer_velocity_for_group(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("TX_DATETIME").copy()
    indexed = group.set_index("TX_DATETIME")
    amount = indexed["TX_AMOUNT"]

    result = pd.DataFrame(index=group.index)
    result["customer_tx_count_10min"] = amount.rolling("10min", closed="left").count().to_numpy()
    result["customer_tx_count_1h"] = amount.rolling("1h", closed="left").count().to_numpy()
    result["customer_amount_sum_1h"] = amount.rolling("1h", closed="left").sum().to_numpy()
    result["customer_amount_max_24h"] = amount.rolling("24h", closed="left").max().to_numpy()
    result["amount_ratio_to_customer_median_30d"] = (
        amount / (amount.rolling("30D", closed="left").median() + 1e-6)
    ).to_numpy()

    previous_tx = indexed.index.to_series().shift(1)
    seconds_since_previous = (indexed.index.to_series() - previous_tx).dt.total_seconds()
    result["time_since_last_customer_tx"] = seconds_since_previous.to_numpy()

    return result


def _rolling_terminal_velocity_for_group(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("TX_DATETIME").copy()
    indexed = group.set_index("TX_DATETIME")

    result = pd.DataFrame(index=group.index)
    result["terminal_tx_count_1h"] = indexed["TX_AMOUNT"].rolling("1h", closed="left").count().to_numpy()
    return result


def _rolling_customer_terminal_features_for_group(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("TX_DATETIME").copy()
    indexed = group.set_index("TX_DATETIME")
    amount = indexed["TX_AMOUNT"]

    result = pd.DataFrame(index=group.index)
    result["customer_terminal_seen_before"] = (np.arange(len(group)) > 0).astype(int)
    result["customer_terminal_tx_count_30d"] = amount.rolling("30D", closed="left").count().to_numpy()
    return result


def add_velocity_novelty_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    customer_parts = []
    for _, group in df.sort_values(["CUSTOMER_ID", "TX_DATETIME"]).groupby("CUSTOMER_ID", sort=False):
        customer_parts.append(_rolling_customer_velocity_for_group(group))
    customer_features = pd.concat(customer_parts).sort_index()
    df = df.join(customer_features)

    terminal_parts = []
    for _, group in df.sort_values(["TERMINAL_ID", "TX_DATETIME"]).groupby("TERMINAL_ID", sort=False):
        terminal_parts.append(_rolling_terminal_velocity_for_group(group))
    terminal_features = pd.concat(terminal_parts).sort_index()
    df = df.join(terminal_features)

    pair_parts = []
    pair_sort_cols = ["CUSTOMER_ID", "TERMINAL_ID", "TX_DATETIME"]
    for _, group in df.sort_values(pair_sort_cols).groupby(["CUSTOMER_ID", "TERMINAL_ID"], sort=False):
        pair_parts.append(_rolling_customer_terminal_features_for_group(group))
    pair_features = pd.concat(pair_parts).sort_index()
    df = df.join(pair_features)

    zero_fill_cols = [
        "customer_tx_count_10min",
        "customer_tx_count_1h",
        "customer_amount_sum_1h",
        "terminal_tx_count_1h",
        "customer_terminal_seen_before",
        "customer_terminal_tx_count_30d",
    ]
    df[zero_fill_cols] = df[zero_fill_cols].fillna(0)

    df["customer_amount_max_24h"] = df["customer_amount_max_24h"].fillna(df["TX_AMOUNT"].median())
    df["amount_ratio_to_customer_median_30d"] = (
        df["amount_ratio_to_customer_median_30d"]
        .replace([np.inf, -np.inf], 0)
        .fillna(1.0)
    )

    fallback_gap = df["time_since_last_customer_tx"].median()
    if pd.isna(fallback_gap):
        fallback_gap = 0.0
    df["time_since_last_customer_tx"] = df["time_since_last_customer_tx"].fillna(fallback_gap)

    return df


def _terminal_risk_for_group(
    group: pd.DataFrame,
    windows_days=(1, 7, 30),
    delay_days: int = 7,
) -> pd.DataFrame:
    group = group.sort_values("TX_DATETIME").copy()
    indexed = group.set_index("TX_DATETIME")
    fraud = indexed["TX_FRAUD"].astype(float)

    result = pd.DataFrame(index=group.index)

    for w in windows_days:
        delayed_fraud = fraud.shift(freq=f"{delay_days}D")
        roll = delayed_fraud.rolling(f"{w}D", closed="left")
        result[f"terminal_nb_tx_{w}d_delay{delay_days}"] = roll.count().to_numpy()
        result[f"terminal_risk_{w}d_delay{delay_days}"] = roll.mean().to_numpy()

    return result


def add_terminal_risk_features(df: pd.DataFrame, windows_days=(1, 7, 30), delay_days: int = 7) -> pd.DataFrame:
    df = df.sort_values(["TERMINAL_ID", "TX_DATETIME"]).copy()
    parts = []
    for _, group in df.groupby("TERMINAL_ID", sort=False):
        parts.append(_terminal_risk_for_group(group, windows_days, delay_days))

    features = pd.concat(parts).sort_index()
    df = df.join(features)

    for col in features.columns:
        if "nb_tx" in col:
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna(0.0)

    return df


def add_geo_proxy_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    required = {"x_customer_id", "y_customer_id", "x_terminal_id", "y_terminal_id"}
    if required.issubset(df.columns):
        df["distance_customer_terminal"] = np.sqrt(
            (df["x_customer_id"] - df["x_terminal_id"]) ** 2
            + (df["y_customer_id"] - df["y_terminal_id"]) ** 2
        )
    else:
        df["distance_customer_terminal"] = 0.0
    return df


def build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["TX_DATETIME"] = pd.to_datetime(df["TX_DATETIME"])

    df = add_time_features(df)
    df = add_customer_behavior_features(df)
    df = add_velocity_novelty_features(df)
    df = add_terminal_risk_features(df)
    df = add_geo_proxy_features(df)

    df["CUSTOMER_ID"] = df["CUSTOMER_ID"].astype(str)
    df["TERMINAL_ID"] = df["TERMINAL_ID"].astype(str)

    return df.sort_values("TX_DATETIME").reset_index(drop=True)


def get_model_columns(df: pd.DataFrame) -> list[str]:
    drop_cols = {
        "TX_FRAUD",
        "TX_FRAUD_SCENARIO",
        "TRANSACTION_ID",
        "TX_DATETIME",
        "CUSTOMER_ID",
        "TERMINAL_ID",
        "TX_TIME_SECONDS",
        "TX_TIME_DAYS",
    }

    return [
        c for c in df.columns
        if c not in drop_cols and pd.api.types.is_numeric_dtype(df[c])
    ]
