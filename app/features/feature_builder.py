from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

import numpy as np
from sqlmodel import Session, select

from app.models import Transactions

MODEL_COLUMNS_32 = [
    "TX_AMOUNT",
    "hour",
    "dayofweek",
    "is_weekend",
    "is_night",
    "customer_nb_tx_1d",
    "customer_avg_amount_1d",
    "customer_sum_amount_1d",
    "customer_nb_tx_7d",
    "customer_avg_amount_7d",
    "customer_sum_amount_7d",
    "customer_nb_tx_30d",
    "customer_avg_amount_30d",
    "customer_sum_amount_30d",
    "amount_ratio_to_customer_avg_7d",
    "amount_zscore_customer",
    "customer_tx_count_10min",
    "customer_tx_count_1h",
    "customer_amount_sum_1h",
    "customer_amount_max_24h",
    "amount_ratio_to_customer_median_30d",
    "time_since_last_customer_tx",
    "terminal_tx_count_1h",
    "customer_terminal_seen_before",
    "customer_terminal_tx_count_30d",
    "terminal_nb_tx_1d_delay7",
    "terminal_risk_1d_delay7",
    "terminal_nb_tx_7d_delay7",
    "terminal_risk_7d_delay7",
    "terminal_nb_tx_30d_delay7",
    "terminal_risk_30d_delay7",
    "distance_customer_terminal",
]


def normalize_terminal_id(shop_name: str | None, shop_adress: str | None) -> str:
    name = (shop_name or "").strip().lower()
    adress = (shop_adress or "").strip().lower()
    return f"{name}|{adress}"


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return to_naive_utc(value)

    if value is None:
        return datetime.utcnow()

    text = str(value)

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    return to_naive_utc(datetime.fromisoformat(text))


def to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parse_uuid(value: Any) -> uuid.UUID | Any:
    if isinstance(value, uuid.UUID):
        return value

    try:
        return uuid.UUID(str(value))
    except Exception:
        return value


def tx_amount(row: Transactions) -> float:
    return float(getattr(row, "size", 0.0) or 0.0) / 100.0


def tx_fraud(row: Transactions) -> int:
    value = getattr(row, "fraud", 0)

    if value is None:
        return 0

    return int(bool(value))


def avg(values: list[float]) -> float:
    if not values:
        return 0.0

    return float(sum(values) / len(values))


def safe_ratio(numerator: float, denominator: float, default: float = 1.0) -> float:
    if denominator is None or denominator == 0:
        return float(default)

    return float(numerator / denominator)


def zscore(value: float, values: list[float]) -> float:
    if len(values) < 2:
        return 0.0

    std = float(np.std(values, ddof=0))

    if std == 0.0:
        return 0.0

    mean = float(np.mean(values))
    return float((value - mean) / std)


def row_created_at(row: Transactions) -> datetime:
    return to_naive_utc(row.created_at)


def filter_since(
        rows: list[Transactions],
        *,
        now: datetime,
        delta: timedelta,
) -> list[Transactions]:
    start = now - delta

    return [
        row
        for row in rows
        if start <= row_created_at(row) < now
    ]


def filter_between(
        rows: list[Transactions],
        *,
        start: datetime,
        end: datetime,
) -> list[Transactions]:
    return [
        row
        for row in rows
        if start <= row_created_at(row) < end
    ]


def terminal_delay_features(
        terminal_rows_37d: list[Transactions],
        *,
        now: datetime,
        window_days: int,
        delay_days: int = 7,
) -> tuple[int, float]:
    end = now - timedelta(days=delay_days)
    start = end - timedelta(days=window_days)

    window = filter_between(
        terminal_rows_37d,
        start=start,
        end=end,
    )

    count = len(window)

    if count == 0:
        return 0, 0.0

    fraud_count = sum(tx_fraud(row) for row in window)
    risk = fraud_count / count

    return int(count), float(risk)


def get_customer_history_30d(
        *,
        session: Session,
        user_id: uuid.UUID | Any,
        tx_time: datetime,
        current_transaction_id: uuid.UUID | Any | None,
) -> list[Transactions]:
    statement = (
        select(Transactions)
        .where(Transactions.user_id == user_id)
        .where(Transactions.created_at < tx_time)
        .where(Transactions.created_at >= tx_time - timedelta(days=30))
        .order_by(Transactions.created_at.asc())
    )

    if current_transaction_id is not None:
        statement = statement.where(Transactions.id != current_transaction_id)

    return list(session.exec(statement).all())


def get_terminal_candidates_37d(
        *,
        session: Session,
        tx_time: datetime,
        current_transaction_id: uuid.UUID | Any | None,
) -> list[Transactions]:
    statement = (
        select(Transactions)
        .where(Transactions.created_at < tx_time)
        .where(Transactions.created_at >= tx_time - timedelta(days=37))
    )

    if current_transaction_id is not None:
        statement = statement.where(Transactions.id != current_transaction_id)

    return list(session.exec(statement).all())


def build_online_features_32(
        *,
        session: Session,
        data: dict[str, Any],
        distance_from_home: float,
) -> dict[str, float | int]:
    current_transaction_id = parse_uuid(data.get("id")) if data.get("id") else None
    user_id = parse_uuid(data["user_id"])
    tx_time = parse_datetime(data.get("created_at"))

    amount = float(
        data.get("size")
        or data.get("TX_AMOUNT")
        or data.get("tx_amount")
        or 0.0
    ) / 100.0

    shop_name = data.get("shop_name")
    shop_adress = (
            data.get("shop_adress")
            or data.get("shop_address")
            or data.get("current_shop_address")
    )

    current_terminal_id = normalize_terminal_id(shop_name, shop_adress)

    customer_rows_30d = get_customer_history_30d(
        session=session,
        user_id=user_id,
        tx_time=tx_time,
        current_transaction_id=current_transaction_id,
    )

    terminal_candidates_37d = get_terminal_candidates_37d(
        session=session,
        tx_time=tx_time,
        current_transaction_id=current_transaction_id,
    )

    terminal_rows_37d = [
        row
        for row in terminal_candidates_37d
        if normalize_terminal_id(row.shop_name, row.shop_adress) == current_terminal_id
    ]

    customer_10min = filter_since(
        customer_rows_30d,
        now=tx_time,
        delta=timedelta(minutes=10),
    )
    customer_1h = filter_since(
        customer_rows_30d,
        now=tx_time,
        delta=timedelta(hours=1),
    )
    customer_1d = filter_since(
        customer_rows_30d,
        now=tx_time,
        delta=timedelta(days=1),
    )
    customer_7d = filter_since(
        customer_rows_30d,
        now=tx_time,
        delta=timedelta(days=7),
    )
    customer_30d = customer_rows_30d

    terminal_1h = filter_since(
        terminal_rows_37d,
        now=tx_time,
        delta=timedelta(hours=1),
    )

    amounts_1h = [tx_amount(row) for row in customer_1h]
    amounts_1d = [tx_amount(row) for row in customer_1d]
    amounts_7d = [tx_amount(row) for row in customer_7d]
    amounts_30d = [tx_amount(row) for row in customer_30d]

    customer_avg_amount_1d = avg(amounts_1d)
    customer_sum_amount_1d = float(sum(amounts_1d))

    customer_avg_amount_7d = avg(amounts_7d)
    customer_sum_amount_7d = float(sum(amounts_7d))

    customer_avg_amount_30d = avg(amounts_30d)
    customer_sum_amount_30d = float(sum(amounts_30d))

    amount_ratio_to_customer_avg_7d = safe_ratio(
        amount,
        customer_avg_amount_7d,
        default=1.0,
    )

    amount_zscore_customer = zscore(amount, amounts_30d)

    if amounts_30d:
        amount_ratio_to_customer_median_30d = safe_ratio(
            amount,
            float(median(amounts_30d)),
            default=1.0,
        )
    else:
        amount_ratio_to_customer_median_30d = 1.0

    if customer_rows_30d:
        last_tx = customer_rows_30d[-1]
        time_since_last_customer_tx = float(
            (tx_time - row_created_at(last_tx)).total_seconds() / 60.0
        )
    else:
        time_since_last_customer_tx = 30.0 * 24.0 * 60.0

    customer_terminal_30d = [
        row
        for row in customer_rows_30d
        if normalize_terminal_id(row.shop_name, row.shop_adress) == current_terminal_id
    ]

    terminal_nb_tx_1d_delay7, terminal_risk_1d_delay7 = terminal_delay_features(
        terminal_rows_37d,
        now=tx_time,
        window_days=1,
        delay_days=7,
    )
    terminal_nb_tx_7d_delay7, terminal_risk_7d_delay7 = terminal_delay_features(
        terminal_rows_37d,
        now=tx_time,
        window_days=7,
        delay_days=7,
    )
    terminal_nb_tx_30d_delay7, terminal_risk_30d_delay7 = terminal_delay_features(
        terminal_rows_37d,
        now=tx_time,
        window_days=30,
        delay_days=7,
    )

    features = {
        "TX_AMOUNT": float(amount),
        "hour": int(tx_time.hour),
        "dayofweek": int(tx_time.weekday()),
        "is_weekend": int(tx_time.weekday() >= 5),
        "is_night": int(tx_time.hour < 6),
        "customer_nb_tx_1d": int(len(customer_1d)),
        "customer_avg_amount_1d": float(customer_avg_amount_1d),
        "customer_sum_amount_1d": float(customer_sum_amount_1d),
        "customer_nb_tx_7d": int(len(customer_7d)),
        "customer_avg_amount_7d": float(customer_avg_amount_7d),
        "customer_sum_amount_7d": float(customer_sum_amount_7d),
        "customer_nb_tx_30d": int(len(customer_30d)),
        "customer_avg_amount_30d": float(customer_avg_amount_30d),
        "customer_sum_amount_30d": float(customer_sum_amount_30d),
        "amount_ratio_to_customer_avg_7d": float(amount_ratio_to_customer_avg_7d),
        "amount_zscore_customer": float(amount_zscore_customer),
        "customer_tx_count_10min": int(len(customer_10min)),
        "customer_tx_count_1h": int(len(customer_1h)),
        "customer_amount_sum_1h": float(sum(amounts_1h)),
        "customer_amount_max_24h": float(max(amounts_1d)) if amounts_1d else 0.0,
        "amount_ratio_to_customer_median_30d": float(
            amount_ratio_to_customer_median_30d
        ),
        "time_since_last_customer_tx": float(time_since_last_customer_tx),
        "terminal_tx_count_1h": int(len(terminal_1h)),
        "customer_terminal_seen_before": int(len(customer_terminal_30d) > 0),
        "customer_terminal_tx_count_30d": int(len(customer_terminal_30d)),
        "terminal_nb_tx_1d_delay7": int(terminal_nb_tx_1d_delay7),
        "terminal_risk_1d_delay7": float(terminal_risk_1d_delay7),
        "terminal_nb_tx_7d_delay7": int(terminal_nb_tx_7d_delay7),
        "terminal_risk_7d_delay7": float(terminal_risk_7d_delay7),
        "terminal_nb_tx_30d_delay7": int(terminal_nb_tx_30d_delay7),
        "terminal_risk_30d_delay7": float(terminal_risk_30d_delay7),
        "distance_customer_terminal": float(distance_from_home or 0.0) / 5.0,
    }

    return {column: features[column] for column in MODEL_COLUMNS_32}
