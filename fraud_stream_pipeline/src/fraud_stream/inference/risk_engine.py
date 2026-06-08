from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from fraud_stream.config import ARTIFACTS_DIR
from fraud_stream.explain.shap_reasons import simple_reason_codes
from fraud_stream.models.hybrid import make_hybrid_scores, score_autoencoder


class FraudRiskEngine:
    """Inference wrapper.

    Important:
    For a real streaming API, you should compute rolling customer/terminal features
    from an online feature store. This class assumes the incoming row already contains
    the same engineered columns as training data.
    """

    def __init__(self):
        self.supervised = joblib.load(ARTIFACTS_DIR / "best_supervised_pipeline.joblib")
        self.anomaly = joblib.load(ARTIFACTS_DIR / "autoencoder_anomaly.joblib")

    def score_feature_row(self, row: dict) -> dict:
        X = pd.DataFrame([row])
        supervised_score = float(self.supervised.predict_proba(X)[:, 1][0])
        anomaly_score = float(score_autoencoder(self.anomaly, X)[0])
        final_score = float(make_hybrid_scores(np.array([supervised_score]), np.array([anomaly_score]))[0])

        if final_score >= 0.8:
            decision = "decline"
        elif final_score >= 0.5:
            decision = "manual_review"
        else:
            decision = "approve"

        return {
            "fraud_probability": supervised_score,
            "anomaly_score": anomaly_score,
            "final_risk_score": final_score,
            "decision": decision,
            "reasons": simple_reason_codes(pd.Series(row)),
        }
