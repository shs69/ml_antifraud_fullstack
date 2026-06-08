from __future__ import annotations

import pandas as pd


def temporal_split_by_days(
    df: pd.DataFrame,
    train_end_day: int = 90,
    valid_end_day: int = 120,
):
    """Split by TX_TIME_DAYS.

    train: TX_TIME_DAYS <= train_end_day
    valid: train_end_day < TX_TIME_DAYS <= valid_end_day
    test: TX_TIME_DAYS > valid_end_day
    """
    train = df[df["TX_TIME_DAYS"] <= train_end_day].copy()
    valid = df[(df["TX_TIME_DAYS"] > train_end_day) & (df["TX_TIME_DAYS"] <= valid_end_day)].copy()
    test = df[df["TX_TIME_DAYS"] > valid_end_day].copy()
    return train, valid, test


def unseen_scenario_split(
    df: pd.DataFrame,
    heldout_scenario: int = 3,
    train_end_day: int = 90,
):
    """Train without one fraud scenario, test on later data containing that scenario.

    Normal transactions are kept in test, because a detector must distinguish held-out fraud from normal behavior.
    """
    early = df[df["TX_TIME_DAYS"] <= train_end_day].copy()
    later = df[df["TX_TIME_DAYS"] > train_end_day].copy()

    train = early[early["TX_FRAUD_SCENARIO"] != heldout_scenario].copy()
    test = later[(later["TX_FRAUD"] == 0) | (later["TX_FRAUD_SCENARIO"] == heldout_scenario)].copy()
    return train, test
