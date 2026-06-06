from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal
import sys
import types

import joblib
import numpy as np
import pandas as pd
import shap


# The worker is responsible for building these features from DB/history.
# Keep this order identical to the training schema.
MODEL_COLUMNS_32: list[str] = [
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


# ---------------------------------------------------------------------------
# Self-contained VAE inference support
# ---------------------------------------------------------------------------
# The saved VAE artifact was pickled from fraud_stream.models.torch_autoencoder.
# Production inference should not import that training module, so we register a
# tiny compatibility module in sys.modules before joblib.load(...). This lets
# existing artifacts unpickle while keeping all runtime scoring code here.

torch = None
nn = None
VariationalAutoencoder = None
_TORCH_THREADS_CONFIGURED = False


@dataclass
class VAEConfig:
    hidden_dims: tuple[int, ...] = (64, 32)
    latent_dim: int = 8
    dropout: float = 0.10
    learning_rate: float = 5e-4
    batch_size: int = 2048
    max_epochs: int = 40
    patience: int = 5
    beta: float = 0.05
    device: str = "auto"
    progress_batches: int = 50


def _coerce_vae_config(config: Any) -> VAEConfig:
    if isinstance(config, VAEConfig):
        return config
    if isinstance(config, dict):
        field_names = {field.name for field in fields(VAEConfig)}
        return VAEConfig(**{key: value for key, value in config.items() if key in field_names})
    return VAEConfig()


def _ensure_torch():
    global torch, nn, VariationalAutoencoder, _TORCH_THREADS_CONFIGURED
    if torch is not None and nn is not None and VariationalAutoencoder is not None:
        return torch, nn, VariationalAutoencoder

    import torch as torch_module
    from torch import nn as nn_module

    torch = torch_module
    nn = nn_module
    if not _TORCH_THREADS_CONFIGURED:
        torch_module.set_num_threads(1)
        try:
            torch_module.set_num_interop_threads(1)
        except RuntimeError:
            pass
        _TORCH_THREADS_CONFIGURED = True

    class _VariationalAutoencoder(nn_module.Module):
        def __init__(self, input_dim: int, config: VAEConfig):
            super().__init__()
            config = _coerce_vae_config(config)

            encoder_layers: list[nn_module.Module] = []
            current_dim = input_dim
            for hidden_dim in config.hidden_dims:
                encoder_layers.extend([
                    nn_module.Linear(current_dim, hidden_dim),
                    nn_module.BatchNorm1d(hidden_dim),
                    nn_module.ReLU(),
                    nn_module.Dropout(config.dropout),
                ])
                current_dim = hidden_dim

            self.encoder = nn_module.Sequential(*encoder_layers)
            self.mu = nn_module.Linear(current_dim, config.latent_dim)
            self.logvar = nn_module.Linear(current_dim, config.latent_dim)

            decoder_layers: list[nn_module.Module] = []
            current_dim = config.latent_dim
            for hidden_dim in reversed(config.hidden_dims):
                decoder_layers.extend([
                    nn_module.Linear(current_dim, hidden_dim),
                    nn_module.BatchNorm1d(hidden_dim),
                    nn_module.ReLU(),
                    nn_module.Dropout(config.dropout),
                ])
                current_dim = hidden_dim
            decoder_layers.append(nn_module.Linear(current_dim, input_dim))
            self.decoder = nn_module.Sequential(*decoder_layers)

        def forward(self, x):
            encoded = self.encoder(x)
            mu = self.mu(encoded)
            logvar = torch_module.clamp(self.logvar(encoded), min=-8.0, max=8.0)
            std = torch_module.exp(0.5 * logvar)
            eps = torch_module.randn_like(std)
            z = mu + eps * std
            return self.decoder(z), mu, logvar

    _VariationalAutoencoder.__name__ = "VariationalAutoencoder"
    _VariationalAutoencoder.__qualname__ = "VariationalAutoencoder"
    _VariationalAutoencoder.__module__ = "fraud_stream.models.torch_autoencoder"
    VariationalAutoencoder = _VariationalAutoencoder
    return torch, nn, VariationalAutoencoder


def _resolve_vae_device(config: VAEConfig):
    torch_module, _, _ = _ensure_torch()
    config = _coerce_vae_config(config)
    if config.device != "auto":
        return torch_module.device(config.device)
    return torch_module.device("cpu")


def score_vae_anomaly_model(model_bundle: dict[str, Any], X: np.ndarray, label: str = "vae") -> np.ndarray:
    torch_module, _, vae_cls = _ensure_torch()

    config = _coerce_vae_config(model_bundle.get("config"))
    device = _resolve_vae_device(config)
    X = np.asarray(X, dtype=np.float32)

    if "model" in model_bundle:
        model = model_bundle["model"]
    elif "vae" in model_bundle and isinstance(model_bundle["vae"], dict):
        vae_bundle = model_bundle["vae"]
        config = _coerce_vae_config(vae_bundle.get("config", config))
        device = _resolve_vae_device(config)
        model = vae_cls(input_dim=vae_bundle["input_dim"], config=config)
        model.load_state_dict(vae_bundle["state_dict"])
    else:
        model = vae_cls(input_dim=model_bundle["input_dim"], config=config)
        model.load_state_dict(model_bundle["state_dict"])

    model = model.to(device)
    model.eval()

    scores = []
    batch_size = 1024
    with torch_module.no_grad():
        for start in range(0, len(X), batch_size):
            batch = torch_module.from_numpy(X[start : start + batch_size]).to(device)
            reconstructed, mu, logvar = model(batch)
            reconstruction = torch_module.mean(
                torch_module.nn.functional.smooth_l1_loss(
                    reconstructed,
                    batch,
                    reduction="none",
                ),
                dim=1,
            )
            kl = -0.5 * torch_module.mean(
                1 + logvar - mu.pow(2) - logvar.exp(),
                dim=1,
                )
            scores.append(reconstruction + config.beta * kl)

    if not scores:
        return np.array([], dtype=float)
    return torch_module.cat(scores).cpu().numpy().astype(float)


def _register_vae_pickle_compat() -> None:
    models_module_name = "fraud_stream.models"
    vae_module_name = "fraud_stream.models.torch_autoencoder"

    if models_module_name not in sys.modules:
        sys.modules[models_module_name] = types.ModuleType(models_module_name)

    compat_module = sys.modules.get(vae_module_name)
    if compat_module is None:
        compat_module = types.ModuleType(vae_module_name)
        sys.modules[vae_module_name] = compat_module

    compat_module.VAEConfig = VAEConfig
    compat_module.VariationalAutoencoder = _ensure_torch()[2]
    compat_module.score_vae_anomaly_model = score_vae_anomaly_model



FusionName = Literal["weighted_average", "max", "probabilistic_or"]
DecisionName = Literal["approve", "manual_review", "decline"]


REASON_TEMPLATES: dict[str, str] = {
    "TX_AMOUNT": "Сумма транзакции влияет на повышение риска",
    "hour": "Время совершения операции отличается от типичного профиля риска",
    "dayofweek": "День недели влияет на оценку риска операции",
    "is_weekend": "Операция совершена в выходной день",
    "is_night": "Операция совершена в ночное время",
    "customer_nb_tx_1d": "За последние сутки у клиента было необычно много операций",
    "customer_avg_amount_1d": "Средний размер операций клиента за сутки влияет на оценку риска",
    "customer_sum_amount_1d": "Суммарный объем операций за сутки повышает риск",
    "customer_nb_tx_7d": "Частота операций клиента за последние 7 дней повышает риск",
    "customer_avg_amount_7d": "Средний размер операций клиента за неделю влияет на оценку риска",
    "customer_sum_amount_7d": "Суммарный объем операций клиента за неделю влияет на оценку риска",
    "customer_nb_tx_30d": "Количество операций клиента за последний месяц влияет на оценку риска",
    "customer_avg_amount_30d": "Средний размер операций клиента за месяц влияет на оценку риска",
    "customer_sum_amount_30d": "Суммарный объем операций клиента за месяц влияет на оценку риска",
    "amount_ratio_to_customer_avg_7d": "Сумма выше обычного поведения клиента за последние 7 дней",
    "amount_zscore_customer": "Сумма нетипична относительно истории клиента",
    "customer_tx_count_10min": "За короткий промежуток времени у клиента было несколько операций",
    "customer_tx_count_1h": "За последний час у клиента была повышенная активность",
    "customer_amount_sum_1h": "Общая сумма операций клиента за последний час влияет на риск",
    "customer_amount_max_24h": "Крупнейшая операция клиента за сутки влияет на оценку риска",
    "amount_ratio_to_customer_median_30d": "Сумма операции отличается от типичного размера покупок клиента за месяц",
    "time_since_last_customer_tx": "Интервал с предыдущей операции клиента влияет на оценку риска",
    "terminal_tx_count_1h": "У торговой точки была повышенная активность за последний час",
    "customer_terminal_seen_before": "История взаимодействий клиента с этой торговой точкой влияет на риск",
    "customer_terminal_tx_count_30d": "Частота операций клиента в этой торговой точке за месяц влияет на риск",
    "terminal_nb_tx_1d_delay7": "Историческая активность терминала за сутки влияет на оценку риска",
    "terminal_risk_1d_delay7": "У терминала повышенный краткосрочный исторический fraud-risk",
    "terminal_nb_tx_7d_delay7": "Историческая активность терминала за неделю влияет на оценку риска",
    "terminal_risk_7d_delay7": "У терминала повышенный исторический fraud-risk",
    "terminal_nb_tx_30d_delay7": "Историческая активность терминала за месяц влияет на оценку риска",
    "terminal_risk_30d_delay7": "У терминала повышенный долгосрочный fraud-risk",
    "distance_customer_terminal": "Терминал находится далеко от типичной зоны клиента",
}


@dataclass(frozen=True)
class ProductionInferenceConfig:
    """Configuration for pure production inference.

    Put real local model paths here in your project settings or pass them from the worker.
    This module does not train models and does not build features.
    """

    lightgbm_path: Path = Path("/path/to/lightgbm_pipeline.joblib")
    autoencoder_path: Path | None = Path("/path/to/autoencoder_anomaly.joblib")
    feature_columns: list[str] = field(default_factory=lambda: MODEL_COLUMNS_32.copy())
    supervised_threshold: float = 0.5
    hybrid_threshold: float = 0.5
    decline_threshold: float = 0.8
    fusion_method: FusionName = "probabilistic_or"
    supervised_weight: float = 0.7


class FeatureValidationError(ValueError):
    """Raised when incoming feature dict is not compatible with the model schema."""


def _as_numeric_frame(rows: pd.DataFrame | list[dict[str, Any]] | dict[str, Any], columns: list[str]) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()
    elif isinstance(rows, dict):
        frame = pd.DataFrame([rows])
    else:
        frame = pd.DataFrame(rows)

    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise FeatureValidationError(f"Missing required model features: {missing}")

    frame = frame.loc[:, columns].copy()
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if frame.isna().any().any():
        bad_columns = frame.columns[frame.isna().any()].tolist()
        raise FeatureValidationError(f"Features contain non-numeric or null values: {bad_columns}")

    return frame


def _predict_probability(model: Any, X: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)
        return np.asarray(proba)[:, 1].astype(float)

    raw = np.asarray(model.predict(X), dtype=float).reshape(-1)
    return np.clip(raw, 0.0, 1.0)


def _clean_feature_name(name: str) -> str:
    return name.split("__", 1)[-1]


def _get_transformed_feature_names(pipeline: Any, fallback_columns: list[str]) -> list[str]:
    preprocessor = pipeline.named_steps.get("preprocessor") if hasattr(pipeline, "named_steps") else None
    if preprocessor is None:
        return fallback_columns.copy()

    try:
        names = list(preprocessor.get_feature_names_out())
    except Exception:
        return fallback_columns.copy()

    return [_clean_feature_name(name) for name in names]


def _get_tree_model(pipeline: Any) -> Any:
    if hasattr(pipeline, "named_steps"):
        return pipeline.named_steps.get("model", pipeline)
    return pipeline


def _transform_for_explanation(pipeline: Any, X: pd.DataFrame) -> Any:
    if hasattr(pipeline, "named_steps") and "preprocessor" in pipeline.named_steps:
        return pipeline.named_steps["preprocessor"].transform(X)
    return X


def _positive_class_shap_values(values: Any) -> np.ndarray:
    if isinstance(values, list):
        values = values[1]

    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, -1]

    return values


def _shap_reason_text(feature: str, contribution: float) -> str:
    template = REASON_TEMPLATES.get(feature)
    if template:
        return template

    direction = "повышает" if contribution >= 0 else "снижает"
    return f"Признак {feature} {direction} оценку риска модели"


def _shap_reason_codes(shap_items: list[dict[str, Any]]) -> list[str]:
    risk_increasing = [item for item in shap_items if item["contribution"] > 0]
    selected = risk_increasing or shap_items

    if not selected:
        return ["Риск сформирован совокупностью слабых факторов без одного доминирующего признака"]

    return [item["reason"] for item in selected]


def _score_vae_anomaly_bundle(bundle: Any, X: pd.DataFrame) -> np.ndarray:
    """Return normalized VAE anomaly scores for the saved anomaly bundle.

    Production supports only the VAE artifact. No classic autoencoder branch and
    no import from fraud_stream.models are used here.
    """
    if bundle is None:
        return np.zeros(len(X), dtype=float)

    if not isinstance(bundle, dict):
        raise TypeError("VAE artifact must be a dict-like bundle")

    if bundle.get("model_type") not in (None, "vae"):
        raise ValueError(f"Unsupported anomaly model_type for production: {bundle.get('model_type')!r}")

    preprocessor = bundle["preprocessor"]
    scaler = bundle["score_scaler"]
    Xt = preprocessor.transform(X)

    vae_bundle = bundle.get("vae", bundle)
    err = score_vae_anomaly_model(vae_bundle, Xt)

    scores = np.asarray(scaler.transform(err.reshape(-1, 1))).reshape(-1).astype(float)
    return np.clip(scores, 0.0, 1.0)


def _fuse_scores(
        supervised_scores: np.ndarray,
        anomaly_scores: np.ndarray,
        *,
        method: FusionName,
        supervised_weight: float,
) -> np.ndarray:
    supervised_scores = np.asarray(supervised_scores, dtype=float)
    anomaly_scores = np.asarray(anomaly_scores, dtype=float)

    if method == "weighted_average":
        return supervised_weight * supervised_scores + (1.0 - supervised_weight) * anomaly_scores
    if method == "max":
        return np.maximum(supervised_scores, anomaly_scores)
    if method == "probabilistic_or":
        return 1.0 - (1.0 - supervised_scores) * (1.0 - anomaly_scores)

    raise ValueError(f"Unknown fusion method: {method}")


def _decision(score: float, *, hybrid_threshold: float, decline_threshold: float) -> DecisionName:
    if score >= decline_threshold:
        return "decline"
    if score >= hybrid_threshold:
        return "manual_review"
    return "approve"


class ProductionFraudInferenceEngine:
    """Pure inference wrapper for already-built online features.

    Responsibilities:
    - load local artifacts;
    - validate/order 32 incoming features;
    - run supervised model;
    - optionally run anomaly model;
    - return production-friendly score and decision.

    Non-responsibilities:
    - no DB access;
    - no feature generation;
    - no training;
    - no offline dataset loading.
    """

    def __init__(self, config: ProductionInferenceConfig | None = None):
        self.config = config or ProductionInferenceConfig()
        self.feature_columns = list(self.config.feature_columns)
        self.supervised = joblib.load(self.config.lightgbm_path)
        self._supervised_model = _get_tree_model(self.supervised)
        self._feature_names = _get_transformed_feature_names(self.supervised, self.feature_columns)
        self._shap_explainer = shap.TreeExplainer(self._supervised_model)
        if self.config.autoencoder_path:
            _register_vae_pickle_compat()
            self.anomaly = joblib.load(self.config.autoencoder_path)
        else:
            self.anomaly = None

    def score_feature_row(
            self,
            features_32: dict[str, Any],
            *,
            include_reasons: bool = True,
            top_k: int = 5,
    ) -> dict[str, Any]:
        return self.score_features([features_32], include_reasons=include_reasons, top_k=top_k)[0]

    def score_features(
            self,
            rows: pd.DataFrame | list[dict[str, Any]],
            *,
            include_reasons: bool = True,
            top_k: int = 5,
    ) -> list[dict[str, Any]]:
        X = _as_numeric_frame(rows, self.feature_columns)

        supervised_scores = _predict_probability(self.supervised, X)
        anomaly_scores = _score_vae_anomaly_bundle(self.anomaly, X)
        final_scores = _fuse_scores(
            supervised_scores,
            anomaly_scores,
            method=self.config.fusion_method,
            supervised_weight=self.config.supervised_weight,
        )
        shap_explanations = self._shap_explanations(X, top_k=top_k) if include_reasons else None

        results: list[dict[str, Any]] = []
        records = X.to_dict(orient="records")
        for idx, row in enumerate(records):
            final_score = float(final_scores[idx])
            supervised_score = float(supervised_scores[idx])
            anomaly_score = float(anomaly_scores[idx])
            result: dict[str, Any] = {
                "fraud_probability": supervised_score,
                "anomaly_score": anomaly_score,
                "final_risk_score": final_score,
                "decision": _decision(
                    final_score,
                    hybrid_threshold=self.config.hybrid_threshold,
                    decline_threshold=self.config.decline_threshold,
                ),
                "fraud": bool(final_score >= self.config.hybrid_threshold),
                "supervised_alert": bool(supervised_score >= self.config.supervised_threshold),
            }
            if include_reasons:
                shap_items = shap_explanations[idx] if shap_explanations is not None else []
                result["reasons"] = _shap_reason_codes(shap_items)
                result["shap"] = shap_items
            results.append(result)

        return results

    def _shap_explanations(self, X: pd.DataFrame, top_k: int = 5) -> list[list[dict[str, Any]]]:
        Xt = _transform_for_explanation(self.supervised, X)
        values = _positive_class_shap_values(self._shap_explainer.shap_values(Xt))

        explanations: list[list[dict[str, Any]]] = []
        for row_values in values:
            order = np.argsort(np.abs(row_values))[::-1][:top_k]
            explanations.append(
                [
                    {
                        "feature": self._feature_names[i],
                        "contribution": float(row_values[i]),
                        "reason": _shap_reason_text(self._feature_names[i], float(row_values[i])),
                    }
                    for i in order
                ]
            )

        return explanations
