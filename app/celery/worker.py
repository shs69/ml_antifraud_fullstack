import json
import logging

import pandas as pd
from celery import Celery

from app.core.config import settings
from app.features.feature_builder import MODEL_COLUMNS_32, build_online_features_32
from app.ml.inference import ProductionFraudInferenceEngine, ProductionInferenceConfig
from app.ml.utils import get_parsed_predict, load_model
from app.redis import redis_sync
from app.utils import calculate_transaction_distances, str_coord_to_tuple
from app.core.database import engine
from sqlmodel import Session
from pathlib import Path

celery_app = Celery(
    "worker", broker_url="redis://127.0.0.1:6379/0", result_backend="redis://127.0.0.1:6379/1"
)

lr = load_model(settings.LR_PATH)
xgb = load_model(settings.XGB_PATH)
xgb.named_steps["classifier"].set_params(verbosity=0)

logger = logging.getLogger(__name__)

inf_module = ProductionFraudInferenceEngine(
    ProductionInferenceConfig(
        lightgbm_path=Path("app/ml/weights/lightgbm_pipeline.joblib"),
        autoencoder_path=Path("app/ml/weights/autoencoder_anomaly.joblib"),
    )
)


@celery_app.task
def check_transaction(transaction_data: str):
    with Session(engine) as session:
        try:
            data = json.loads(transaction_data)
            id = data.pop("id")

            coords = calculate_transaction_distances(
                current_shop_address=data["current_shop_address"],
                home_coords=str_coord_to_tuple(coord_string=data["user_home_coords"]),
                last_transaction_shop_address=data["last_transaction_address"],
            )

            if coords is None:
                redis_sync.publish(f"transaction:error", f"{id}")
                return

            shop_coords, distance_from_home, distance_from_last_transaction = coords

            model_data = {
                "distance_from_home": distance_from_home,
                "distance_from_last_transaction": distance_from_last_transaction,
                "ratio_to_median_purchase_price": data["ratio_to_median_purchase_price"],
                "repeat_retailer": data["repeat_retailer"],
                "used_chip": data["used_chip"],
                "used_pin_number": data["online_order"],
                "online_order": data["online_order"],
            }

            features_32 = build_online_features_32(
                session=session,
                data=data,
                distance_from_home=distance_from_home,
            )

            print(features_32)
            res = inf_module.score_feature_row(features_32)
            print(res)

            # df = pd.DataFrame([model_data])
            # for col in df.columns:
            #     if df[col].dtype == object:
            #         df[col] = pd.to_numeric(df[col], errors="coerce")

            # result_lr = get_parsed_predict(xgb, df)
            # print(f"lr: {result_lr}")

            result_json = json.dumps(
                {
                    "fraud": str(int(res["fraud"])),
                    "distance_from_home": distance_from_home,
                    "distance_from_last_transaction": distance_from_last_transaction,
                    "shop_coords": f"({shop_coords[0]}, {shop_coords[1]})",
                    "reasons": str(res["reasons"]),
                }
            )
            redis_sync.publish(f"transaction:{id}", f"{result_json}")

        except Exception:
            logger.exception("Ошибка при предсказании модели")
            raise
