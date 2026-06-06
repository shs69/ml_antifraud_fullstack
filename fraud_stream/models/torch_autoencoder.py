from app.ml.inference import (
    VAEConfig,
    score_vae_anomaly_model,
)

from app.ml.inference import _ensure_torch

VariationalAutoencoder = _ensure_torch()[2]