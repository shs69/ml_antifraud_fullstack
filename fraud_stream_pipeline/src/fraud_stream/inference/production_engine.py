from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from fraud_stream.config import ARTIFACTS_DIR, PROCESSED_DIR, TARGET
from fraud_stream.data.features_io import load_feature_table
from fraud_stream.data.load_handbook import load_transactions
from fraud_stream.explain.shap_reasons import REASON_TEMPLATES, simple_reason_codes
from fraud_stream.features.build_features import build_feature_table, get_model_columns
from fraud_stream.models.hybrid import fuse_scores, score_autoencoder
from fraud_stream.models.metrics import evaluate_scores, threshold_for_target_recall
from fraud_stream.models.splits import temporal_split_by_days
from fraud_stream.models.train_anomaly import train_autoencoder
from fraud_stream.models.train_supervised import (
    _optional_lgbm,
    build_preprocessor,
    scale_pos_weight_for,
)


@dataclass(frozen=True)
class ProductionInferenceConfig:
    begin_date: str = "2018-04-01"
    end_date: str = "2018-07-09"
    train_end_day: int = 60
    valid_end_day: int = 80
    supervised_target_recall: float = 0.80
    hybrid_target_recall: float = 0.80
    vae_device: str = "auto"
    train_if_missing: bool = True
    lightgbm_path: Path = ARTIFACTS_DIR / "lightgbm_pipeline.joblib"
    autoencoder_path: Path = ARTIFACTS_DIR / "autoencoder_anomaly.joblib"
    metadata_path: Path = ARTIFACTS_DIR / "production_inference_metadata.json"


def _clean_feature_names(pipeline) -> list[str]:
    preprocessor = pipeline.named_steps["preprocessor"]
    try:
        names = list(preprocessor.get_feature_names_out())
    except Exception:
        names = []
    return [name.split("__", 1)[-1] for name in names]


def _load_or_build_features(config: ProductionInferenceConfig) -> pd.DataFrame:
    try:
        return load_feature_table()
    except FileNotFoundError:
        raw = load_transactions(config.begin_date, config.end_date)
        features = build_feature_table(raw)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        features.to_parquet(PROCESSED_DIR / "handbook_features.parquet", index=False)
        return features


def train_lightgbm_for_inference(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    config: ProductionInferenceConfig | None = None,
) -> dict[str, Any]:
    config = config or ProductionInferenceConfig()
    feature_cols = get_model_columns(train)
    X_train, y_train = train[feature_cols], train[TARGET].astype(int)
    X_valid, y_valid = valid[feature_cols], valid[TARGET].astype(int)
    X_test, y_test = test[feature_cols], test[TARGET].astype(int)

    estimator = _optional_lgbm(scale_pos_weight_for(y_train))
    if estimator is None:
        raise RuntimeError("LightGBM is not installed, but production inference requires it.")

    pipe = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor(X_train)),
            ("model", estimator),
        ]
    )
    print("[production] training lightgbm", flush=True)
    pipe.fit(X_train, y_train)

    valid_score = pipe.predict_proba(X_valid)[:, 1]
    test_score = pipe.predict_proba(X_test)[:, 1]
    threshold = threshold_for_target_recall(
        y_valid, valid_score, target_recall=config.supervised_target_recall
    )

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, config.lightgbm_path)

    return {
        "artifact": str(config.lightgbm_path),
        "threshold": float(threshold),
        "feature_cols": feature_cols,
        "valid": evaluate_scores(y_valid, valid_score, threshold),
        "test": evaluate_scores(y_test, test_score, threshold),
    }


def ensure_production_models(
    config: ProductionInferenceConfig | None = None,
) -> dict[str, Any]:
    config = config or ProductionInferenceConfig()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    need_lightgbm = not config.lightgbm_path.exists()
    need_autoencoder = not config.autoencoder_path.exists()
    if (need_lightgbm or need_autoencoder) and not config.train_if_missing:
        missing = [
            str(path)
            for path, needed in [
                (config.lightgbm_path, need_lightgbm),
                (config.autoencoder_path, need_autoencoder),
            ]
            if needed
        ]
        raise FileNotFoundError(f"Missing production artifacts: {missing}")

    metadata: dict[str, Any] = {}
    if need_lightgbm or need_autoencoder:
        print("[production] loading/building feature table for missing models", flush=True)
        features = _load_or_build_features(config)
        train, valid, test = temporal_split_by_days(
            features,
            train_end_day=config.train_end_day,
            valid_end_day=config.valid_end_day,
        )

        if need_lightgbm:
            metadata["lightgbm"] = train_lightgbm_for_inference(
                train, valid, test, config=config
            )

        if need_autoencoder:
            print("[production] training autoencoder", flush=True)
            metadata["autoencoder"] = train_autoencoder(
                train,
                valid,
                test,
                vae_device=config.vae_device,
            )

    existing_metadata = {}
    if config.metadata_path.exists():
        with open(config.metadata_path, encoding="utf-8") as f:
            existing_metadata = json.load(f)

    merged = {
        **existing_metadata,
        **metadata,
        "lightgbm_path": str(config.lightgbm_path),
        "autoencoder_path": str(config.autoencoder_path),
        "train_end_day": config.train_end_day,
        "valid_end_day": config.valid_end_day,
    }
    with open(config.metadata_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    return merged


class ProductionFraudInferenceEngine:
    """Production-oriented inference wrapper for LightGBM + autoencoder + SHAP.

    Incoming rows must already contain the engineered feature columns used during
    training. In a real service these columns should come from an online feature
    store or the same feature builder used offline.
    """

    def __init__(self, config: ProductionInferenceConfig | None = None):
        self.config = config or ProductionInferenceConfig()
        self.metadata = ensure_production_models(self.config)
        self.lightgbm = joblib.load(self.config.lightgbm_path)
        self.autoencoder = joblib.load(self.config.autoencoder_path)
        self.feature_cols = list(
            self.metadata.get("lightgbm", {}).get(
                "feature_cols", _clean_feature_names(self.lightgbm)
            )
        )
        self.supervised_threshold = float(
            self.metadata.get("lightgbm", {}).get("threshold", 0.5)
        )
        self.hybrid_threshold = float(self.metadata.get("hybrid_threshold", 0.5))

    def score_features(
        self,
        rows: pd.DataFrame,
        include_shap: bool = True,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        X = rows.copy()
        supervised_scores = self.lightgbm.predict_proba(X)[:, 1]
        anomaly_scores = score_autoencoder(self.autoencoder, X)
        final_scores = fuse_scores(
            supervised_scores,
            anomaly_scores,
            method="probabilistic_or",
        )
        shap_items = self._shap_explanations(X, top_k=top_k) if include_shap else None

        results = []
        for idx, row in enumerate(X.to_dict(orient="records")):
            final_score = float(final_scores[idx])
            if final_score >= 0.8:
                decision = "decline"
            elif final_score >= self.hybrid_threshold:
                decision = "manual_review"
            else:
                decision = "approve"

            results.append(
                {
                    "fraud_probability": float(supervised_scores[idx]),
                    "anomaly_score": float(anomaly_scores[idx]),
                    "final_risk_score": final_score,
                    "decision": decision,
                    "supervised_alert": bool(
                        supervised_scores[idx] >= self.supervised_threshold
                    ),
                    "reasons": simple_reason_codes(pd.Series(row), top_k=top_k),
                    "shap": shap_items[idx] if shap_items is not None else [],
                }
            )

        return results

    def score_feature_row(
        self,
        row: dict[str, Any],
        include_shap: bool = True,
        top_k: int = 5,
    ) -> dict[str, Any]:
        return self.score_features(
            pd.DataFrame([row]), include_shap=include_shap, top_k=top_k
        )[0]

    def _shap_explanations(
        self,
        X: pd.DataFrame,
        top_k: int = 5,
    ) -> list[list[dict[str, Any]]]:
        try:
            import shap

            Xt = self.lightgbm.named_steps["preprocessor"].transform(X)
            model = self.lightgbm.named_steps["model"]
            feature_names = _clean_feature_names(self.lightgbm)
            if not feature_names or len(feature_names) != Xt.shape[1]:
                feature_names = [f"f_{i}" for i in range(Xt.shape[1])]

            explainer = shap.TreeExplainer(model)
            values = explainer.shap_values(Xt)
            if isinstance(values, list):
                values = values[1]
            values = np.asarray(values)
            if values.ndim == 3:
                values = values[:, :, -1]

            explanations = []
            for row_values in values:
                order = np.argsort(np.abs(row_values))[::-1][:top_k]
                explanations.append(
                    [
                        {
                            "feature": feature_names[i],
                            "contribution": float(row_values[i]),
                            "reason": REASON_TEMPLATES.get(feature_names[i]),
                        }
                        for i in order
                    ]
                )
            return explanations
        except Exception as exc:
            return [[{"error": f"SHAP explanation unavailable: {exc}"}] for _ in range(len(X))]
