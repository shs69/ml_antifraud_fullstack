from celery import Celery
from app.ml.utils import load_model, get_parsed_predict
from app.models import TransactionDataForModel
from app.redis import redis_sync
from app.core.config import settings
import json
import logging
import pandas as pd

celery_app = Celery(
    "worker",
    broker_url="redis://127.0.0.1:6379/0",
    result_backend="redis://127.0.0.1:6379/1"
)

lr = load_model(settings.LR_PATH)
xgb = load_model(settings.XGB_PATH)
xgb.named_steps['classifier'].set_params(verbosity=0)

logger = logging.getLogger(__name__)


@celery_app.task
def check_transaction(transaction_data: str):
    try:
        data = json.loads(transaction_data)
        id = data.pop("id")
        logger.info(f"Transaction data: {data}")

        df = pd.DataFrame([data])
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        result_lr = get_parsed_predict(xgb, df)
        logger.info(f"Prediction result: {result_lr}")

        for elem in result_lr:
            redis_sync.publish(f"transaction:{id}", f"LR|{str(elem)}")

    except Exception:
        logger.exception("Ошибка при предсказании модели")
        raise
