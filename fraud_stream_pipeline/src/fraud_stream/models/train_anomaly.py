from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, RobustScaler

from fraud_stream.config import ARTIFACTS_DIR, RANDOM_STATE, TARGET
from fraud_stream.features.build_features import get_model_columns
from fraud_stream.models.metrics import evaluate_scores, threshold_for_target_recall
from fraud_stream.models.torch_autoencoder import (
    VAEConfig,
    load_vae_anomaly_model,
    score_vae_anomaly_model,
    serializable_vae_bundle,
    torch_available,
    train_vae_anomaly_model,
)

MAX_ANOMALY_CALIBRATION_ROWS = 50_000


def build_numeric_preprocessor(X: pd.DataFrame) -> tuple[ColumnTransformer, list[str]]:
    # For anomaly models we intentionally avoid high-cardinality raw IDs.
    drop = {"CUSTOMER_ID", "TERMINAL_ID"}
    numeric_cols = [
        c for c in X.columns if c not in drop and pd.api.types.is_numeric_dtype(X[c])
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", RobustScaler()),
                    ]
                ),
                numeric_cols,
            )
        ],
        remainder="drop",
    )
    return preprocessor, numeric_cols


def minmax_fit_transform_scores(train_scores, valid_scores, test_scores):
    scaler = MinMaxScaler()
    train_scores = sanitize_scores(train_scores, "train_score")
    valid_scores = sanitize_scores(valid_scores, "valid_score")
    test_scores = sanitize_scores(test_scores, "test_score")
    scaler.fit(np.asarray(train_scores).reshape(-1, 1))
    return (
        scaler.transform(np.asarray(train_scores).reshape(-1, 1)).ravel(),
        scaler.transform(np.asarray(valid_scores).reshape(-1, 1)).ravel(),
        scaler.transform(np.asarray(test_scores).reshape(-1, 1)).ravel(),
        scaler,
    )


def nonfinite_counts(values) -> dict:
    values = np.asarray(values, dtype=float)
    return {
        "nan": int(np.isnan(values).sum()),
        "posinf": int(np.isposinf(values).sum()),
        "neginf": int(np.isneginf(values).sum()),
    }


def sanitize_scores(values, name: str) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        print(f"[WARN] {name} contains no finite values; replacing with zeros.")
        return np.zeros_like(values, dtype=float)

    max_finite = float(np.max(finite))
    min_finite = float(np.min(finite))
    fill_nan = float(np.median(finite))
    return np.nan_to_num(values, nan=fill_nan, posinf=max_finite, neginf=min_finite)


def sanitize_matrix(values) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    return np.nan_to_num(values, nan=0.0, posinf=1e6, neginf=-1e6)


def calibration_sample(
    X: np.ndarray, max_rows: int = MAX_ANOMALY_CALIBRATION_ROWS
) -> np.ndarray:
    if len(X) <= max_rows:
        return X
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(X), size=max_rows, replace=False)
    return X[np.sort(idx)]


def percentile_scores(reference_scores, scores) -> np.ndarray:
    reference = np.sort(
        sanitize_scores(reference_scores, "reference_percentile_scores")
    )
    scores = sanitize_scores(scores, "percentile_scores")
    if len(reference) == 0:
        return np.zeros_like(scores, dtype=float)
    return np.searchsorted(reference, scores, side="right") / len(reference)


def reconstruction_error(ae: MLPRegressor, X: np.ndarray) -> np.ndarray:
    pred = ae.predict(X)
    return np.mean((X - pred) ** 2, axis=1)


def train_mlp_reconstruction_model(
    X_train_normal: np.ndarray,
) -> tuple[MLPRegressor, list[dict]]:
    ae = MLPRegressor(
        hidden_layer_sizes=(64, 32, 8, 32, 64),
        activation="relu",
        solver="adam",
        max_iter=120,
        random_state=RANDOM_STATE,
        early_stopping=True,
        validation_fraction=0.1,
        learning_rate_init=1e-3,
        alpha=1e-4,
    )
    ae.fit(X_train_normal, X_train_normal)
    history = [
        {"epoch": idx + 1, "train_loss": float(loss)}
        for idx, loss in enumerate(getattr(ae, "loss_curve_", []))
    ]
    return ae, history


def train_isolation_forest(
    train: pd.DataFrame, valid: pd.DataFrame, test: pd.DataFrame
) -> dict:
    print("[anomaly] isolation_forest started", flush=True)
    feature_cols = get_model_columns(train)
    X_valid, X_test = valid[feature_cols], test[feature_cols]
    y_valid, y_test = valid[TARGET].astype(int), test[TARGET].astype(int)

    normal_train = train[train[TARGET] == 0]
    X_train_normal = normal_train[feature_cols]

    preprocessor, numeric_cols = build_numeric_preprocessor(X_train_normal)
    model = IsolationForest(
        n_estimators=300,
        contamination="auto",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )

    pipe = Pipeline([("preprocessor", preprocessor), ("model", model)])
    print(
        f"[anomaly] isolation_forest fitting rows={len(X_train_normal):,}", flush=True
    )
    pipe.fit(X_train_normal)
    print("[anomaly] isolation_forest scoring", flush=True)

    # decision_function: higher = more normal. We invert to anomaly score.
    train_raw = -pipe.decision_function(X_train_normal)
    valid_raw = -pipe.decision_function(X_valid)
    test_raw = -pipe.decision_function(X_test)

    _, valid_score, test_score, scaler = minmax_fit_transform_scores(
        train_raw, valid_raw, test_raw
    )
    threshold = threshold_for_target_recall(y_valid, valid_score, target_recall=0.70)

    metrics = {
        "valid": evaluate_scores(y_valid, valid_score, threshold),
        "test": evaluate_scores(y_test, test_score, threshold),
        "threshold": threshold,
        "numeric_cols": numeric_cols,
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"pipeline": pipe, "score_scaler": scaler},
        ARTIFACTS_DIR / "isolation_forest_anomaly.joblib",
    )
    print("[anomaly] isolation_forest finished", flush=True)
    return metrics


def train_autoencoder(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    vae_model_path: str | Path | None = None,
    vae_device: str = "auto",
) -> dict:
    """Train an anomaly autoencoder on normal transactions only.

    Uses a compact PyTorch VAE when PyTorch is available. In lightweight local
    environments it falls back to a deeper MLP reconstruction model.
    """
    print("[anomaly] autoencoder started", flush=True)
    feature_cols = get_model_columns(train)
    normal_train = train[train[TARGET] == 0]

    X_train_normal_raw = normal_train[feature_cols]
    X_valid_raw = valid[feature_cols]
    X_test_raw = test[feature_cols]

    y_valid, y_test = valid[TARGET].astype(int), test[TARGET].astype(int)

    preprocessor, numeric_cols = build_numeric_preprocessor(X_train_normal_raw)
    X_train_normal = preprocessor.fit_transform(X_train_normal_raw)
    X_valid = preprocessor.transform(X_valid_raw)
    X_test = preprocessor.transform(X_test_raw)
    X_train_normal = sanitize_matrix(X_train_normal)
    X_valid = sanitize_matrix(X_valid)
    X_test = sanitize_matrix(X_test)
    X_calibration = calibration_sample(X_train_normal)

    np.savez_compressed(
        ARTIFACTS_DIR / "vae_data.npz",
        X_train_normal=X_train_normal.astype(np.float32),
        X_valid=X_valid.astype(np.float32),
        X_test=X_test.astype(np.float32),
        y_valid=y_valid.to_numpy(dtype=np.int32),
        y_test=y_test.to_numpy(dtype=np.int32),
    )

    print(
        f"[anomaly] autoencoder matrices train_normal={X_train_normal.shape} "
        f"calibration={X_calibration.shape} valid={X_valid.shape} test={X_test.shape}",
        flush=True,
    )

    if vae_model_path is not None:
        if not torch_available():
            raise RuntimeError(
                f"Cannot load VAE model from {vae_model_path}: PyTorch is not installed."
            )
        model_type = "vae"
        ae = None
        vae_model_path = Path(vae_model_path)
        if vae_model_path.is_dir():
            vae_model_path = vae_model_path / "vae_model.pt"
        print(f"[anomaly] loading vae model from {vae_model_path}", flush=True)
        vae_bundle = load_vae_anomaly_model(
            vae_model_path,
            input_dim=X_train_normal.shape[1],
            device=vae_device,
            history_path=vae_model_path.with_name("vae_history.json"),
        )
        history = vae_bundle["history"]
        print("[anomaly] vae scoring calibration", flush=True)
        train_raw = score_vae_anomaly_model(
            vae_bundle, X_calibration, label="calibration"
        )
        print("[anomaly] vae scoring valid", flush=True)
        valid_raw = score_vae_anomaly_model(vae_bundle, X_valid, label="valid")
        print("[anomaly] vae scoring test", flush=True)
        test_raw = score_vae_anomaly_model(vae_bundle, X_test, label="test")
    elif torch_available():
        model_type = "vae"
        ae, history = None, []
        vae_bundle = train_vae_anomaly_model(
            X_train_normal, config=VAEConfig(device=vae_device)
        )
        history = vae_bundle["history"]
        print("[anomaly] vae scoring calibration", flush=True)
        train_raw = score_vae_anomaly_model(
            vae_bundle, X_calibration, label="calibration"
        )
        print("[anomaly] vae scoring valid", flush=True)
        valid_raw = score_vae_anomaly_model(vae_bundle, X_valid, label="valid")
        print("[anomaly] vae scoring test", flush=True)
        test_raw = score_vae_anomaly_model(vae_bundle, X_test, label="test")
    else:
        model_type = "mlp_reconstruction"
        vae_bundle = None
        ae, history = train_mlp_reconstruction_model(X_train_normal)
        train_raw = reconstruction_error(ae, X_calibration)
        valid_raw = reconstruction_error(ae, X_valid)
        test_raw = reconstruction_error(ae, X_test)

    score_quality = {
        "train_raw": nonfinite_counts(train_raw),
        "valid_raw": nonfinite_counts(valid_raw),
        "test_raw": nonfinite_counts(test_raw),
    }
    train_raw = sanitize_scores(train_raw, "train_raw")
    valid_raw = sanitize_scores(valid_raw, "valid_raw")
    test_raw = sanitize_scores(test_raw, "test_raw")

    _, valid_score, test_score, scaler = minmax_fit_transform_scores(
        train_raw, valid_raw, test_raw
    )
    valid_percentile = percentile_scores(train_raw, valid_raw)
    test_percentile = percentile_scores(train_raw, test_raw)
    threshold = threshold_for_target_recall(y_valid, valid_score, target_recall=0.70)
    percentile_threshold = threshold_for_target_recall(
        y_valid, valid_percentile, target_recall=0.70
    )

    metrics = {
        "valid": evaluate_scores(y_valid, valid_score, threshold),
        "test": evaluate_scores(y_test, test_score, threshold),
        "valid_percentile": evaluate_scores(
            y_valid, valid_percentile, percentile_threshold
        ),
        "test_percentile": evaluate_scores(
            y_test, test_percentile, percentile_threshold
        ),
        "threshold": threshold,
        "percentile_threshold": percentile_threshold,
        "model_type": model_type,
        "numeric_cols": numeric_cols,
        "train_history": history,
        "score_quality": score_quality,
        "calibration_rows": int(len(X_calibration)),
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "preprocessor": preprocessor,
        "score_scaler": scaler,
        "reference_scores": np.sort(np.asarray(train_raw, dtype=float)),
        "model_type": model_type,
    }
    if model_type == "vae":
        artifact["vae"] = serializable_vae_bundle(vae_bundle)
    else:
        artifact["autoencoder"] = ae

    joblib.dump(artifact, ARTIFACTS_DIR / "autoencoder_anomaly.joblib")
    print(f"[anomaly] autoencoder finished model_type={model_type}", flush=True)
    return metrics


def train_anomaly_models(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    vae_model_path: str | Path | None = None,
    vae_device: str = "auto",
) -> dict:
    results = {
        "isolation_forest": train_isolation_forest(train, valid, test),
        "autoencoder": train_autoencoder(
            train, valid, test, vae_model_path=vae_model_path, vae_device=vae_device
        ),
    }
    with open(ARTIFACTS_DIR / "anomaly_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return results
