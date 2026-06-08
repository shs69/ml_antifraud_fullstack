from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from fraud_stream.inference.risk_engine import FraudRiskEngine


app = FastAPI(title="Explainable Hybrid Anti-Fraud API")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = FraudRiskEngine()
    return _engine


class EngineeredTransaction(BaseModel):
    # В production сюда лучше подавать уже engineered features из feature store.
    TX_AMOUNT: float
    TX_TIME_SECONDS: int = 0
    TX_TIME_DAYS: int = 0
    CUSTOMER_ID: str
    TERMINAL_ID: str

    hour: int = 12
    dayofweek: int = 0
    is_weekend: int = 0
    is_night: int = 0

    customer_nb_tx_1d: float = 0
    customer_avg_amount_1d: float = 0
    customer_sum_amount_1d: float = 0
    customer_nb_tx_7d: float = 0
    customer_avg_amount_7d: float = 0
    customer_sum_amount_7d: float = 0
    customer_nb_tx_30d: float = 0
    customer_avg_amount_30d: float = 0
    customer_sum_amount_30d: float = 0

    amount_ratio_to_customer_avg_7d: float = 1
    amount_zscore_customer: float = 0

    terminal_nb_tx_1d_delay7: float = 0
    terminal_risk_1d_delay7: float = 0
    terminal_nb_tx_7d_delay7: float = 0
    terminal_risk_7d_delay7: float = 0
    terminal_nb_tx_30d_delay7: float = 0
    terminal_risk_30d_delay7: float = 0

    distance_customer_terminal: float = 0


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score")
def score(tx: EngineeredTransaction):
    return get_engine().score_feature_row(tx.model_dump())
