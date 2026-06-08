from __future__ import annotations

from dataclasses import dataclass, fields, replace
from importlib.util import find_spec
from pathlib import Path

import numpy as np

from fraud_stream.config import RANDOM_STATE

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
            encoder_layers: list[nn_module.Module] = []
            current_dim = input_dim
            for hidden_dim in config.hidden_dims:
                encoder_layers.extend(
                    [
                        nn_module.Linear(current_dim, hidden_dim),
                        nn_module.BatchNorm1d(hidden_dim),
                        nn_module.ReLU(),
                        nn_module.Dropout(config.dropout),
                    ]
                )
                current_dim = hidden_dim

            self.encoder = nn_module.Sequential(*encoder_layers)
            self.mu = nn_module.Linear(current_dim, config.latent_dim)
            self.logvar = nn_module.Linear(current_dim, config.latent_dim)

            decoder_layers: list[nn_module.Module] = []
            current_dim = config.latent_dim
            for hidden_dim in reversed(config.hidden_dims):
                decoder_layers.extend(
                    [
                        nn_module.Linear(current_dim, hidden_dim),
                        nn_module.BatchNorm1d(hidden_dim),
                        nn_module.ReLU(),
                        nn_module.Dropout(config.dropout),
                    ]
                )
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
    _VariationalAutoencoder.__module__ = __name__
    VariationalAutoencoder = _VariationalAutoencoder
    return torch, nn, VariationalAutoencoder


def torch_available() -> bool:
    return find_spec("torch") is not None


def resolve_device(config: VAEConfig):
    torch_module, _, _ = _ensure_torch()
    if config.device != "auto":
        return torch_module.device(config.device)
    # Keep the default on CPU for tabular VAE runs. On macOS, MPS can stall
    # during inference after sklearn/XGBoost/LightGBM have used native thread
    # pools earlier in the same process. Users can still opt in with
    # --vae-device mps when they specifically want to test that backend.
    return torch_module.device("cpu")


def _coerce_vae_config(config) -> VAEConfig:
    if isinstance(config, VAEConfig):
        return config
    if isinstance(config, dict):
        field_names = {field.name for field in fields(VAEConfig)}
        return VAEConfig(**{k: v for k, v in config.items() if k in field_names})
    return VAEConfig()


def _infer_input_dim_from_state_dict(state_dict: dict) -> int | None:
    weight = state_dict.get("encoder.0.weight")
    if weight is None or not hasattr(weight, "shape") or len(weight.shape) != 2:
        return None
    return int(weight.shape[1])


def load_vae_anomaly_model(
    model_path: str | Path,
    input_dim: int | None = None,
    device: str = "auto",
    history_path: str | Path | None = None,
) -> dict:
    """Load a previously trained VAE bundle or state_dict from a .pt file."""
    torch_module, _, vae_cls = _ensure_torch()
    import json

    model_path = Path(model_path)
    checkpoint = torch_module.load(model_path, map_location="cpu")

    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
        config = _coerce_vae_config(checkpoint.get("config"))
        loaded_input_dim = checkpoint.get("input_dim")
        history = checkpoint.get("history", [])
    elif isinstance(checkpoint, dict):
        state_dict = checkpoint
        config = VAEConfig()
        loaded_input_dim = None
        history = []
    else:
        raise ValueError(
            f"Unsupported VAE checkpoint format in {model_path}. "
            "Expected a state_dict or a dict with 'state_dict'."
        )

    if device is not None:
        config = replace(config, device=device)

    loaded_input_dim = loaded_input_dim or _infer_input_dim_from_state_dict(state_dict)
    model_input_dim = input_dim or loaded_input_dim
    if model_input_dim is None:
        raise ValueError(
            f"Could not infer VAE input_dim from {model_path}; pass input_dim explicitly."
        )
    if loaded_input_dim is not None and int(loaded_input_dim) != int(model_input_dim):
        raise ValueError(
            f"VAE input_dim mismatch: checkpoint has {loaded_input_dim}, "
            f"current features have {model_input_dim}."
        )

    if not history and history_path is not None and Path(history_path).exists():
        with open(history_path, encoding="utf-8") as f:
            history = json.load(f)

    model = vae_cls(input_dim=int(model_input_dim), config=config)
    model.load_state_dict(state_dict)

    return {
        "model": model,
        "config": config,
        "history": history,
        "input_dim": int(model_input_dim),
        "device": str(resolve_device(config)),
    }


def train_vae_anomaly_model(
    X_train: np.ndarray, config: VAEConfig | None = None
) -> dict:
    """Train a compact VAE on normal transactions only.

    The import is intentionally local so the project still works without PyTorch.
    """
    torch_module, nn_module, vae_cls = _ensure_torch()
    from torch.utils.data import DataLoader, TensorDataset, random_split

    config = config or VAEConfig()
    torch_module.manual_seed(RANDOM_STATE)
    np.random.seed(RANDOM_STATE)
    device = resolve_device(config)
    print(
        "[vae] training started "
        f"rows={len(X_train):,} batch_size={config.batch_size} "
        f"max_epochs={config.max_epochs} patience={config.patience} device={device}",
        flush=True,
    )

    X_train = np.asarray(X_train, dtype=np.float32)
    dataset = TensorDataset(torch_module.from_numpy(X_train))
    valid_size = max(1, int(len(dataset) * 0.1))
    train_size = len(dataset) - valid_size
    if train_size <= 0:
        raise ValueError(
            "VAE needs at least two normal transactions for train/validation split."
        )

    generator = torch_module.Generator().manual_seed(RANDOM_STATE)
    train_dataset, valid_dataset = random_split(
        dataset, [train_size, valid_size], generator=generator
    )
    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    valid_loader = DataLoader(
        valid_dataset, batch_size=config.batch_size, shuffle=False
    )
    total_train_batches = len(train_loader)
    total_valid_batches = len(valid_loader)
    print(
        "[vae] data ready "
        f"train_rows={train_size:,} valid_rows={valid_size:,} "
        f"train_batches={total_train_batches:,} valid_batches={total_valid_batches:,}",
        flush=True,
    )

    model = vae_cls(input_dim=X_train.shape[1], config=config).to(device)
    optimizer = torch_module.optim.Adam(model.parameters(), lr=config.learning_rate)
    recon_loss = nn_module.SmoothL1Loss(reduction="mean")
    print("[vae] model ready", flush=True)

    def batch_loss(batch):
        (x,) = batch
        x = x.to(device)
        reconstructed, mu, logvar = model(x)
        reconstruction = recon_loss(reconstructed, x)
        kl = -0.5 * torch_module.mean(1 + logvar - mu.pow(2) - logvar.exp())
        return reconstruction + config.beta * kl

    best_state = None
    best_valid_loss = float("inf")
    bad_epochs = 0
    history = []

    for epoch in range(config.max_epochs):
        model.train()
        train_losses = []
        for batch_idx, batch in enumerate(train_loader, start=1):
            optimizer.zero_grad()
            loss = batch_loss(batch)
            if not torch_module.isfinite(loss):
                continue
            loss.backward()
            torch_module.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            train_losses.append(float(loss.detach().cpu()))
            if (
                batch_idx == 1
                or batch_idx == total_train_batches
                or batch_idx % config.progress_batches == 0
            ):
                print(
                    f"[vae] epoch {epoch + 1:03d}/{config.max_epochs} "
                    f"train batch {batch_idx:,}/{total_train_batches:,}",
                    flush=True,
                )

        model.eval()
        valid_losses = []
        with torch_module.no_grad():
            for batch_idx, batch in enumerate(valid_loader, start=1):
                valid_losses.append(float(batch_loss(batch).detach().cpu()))
                if (
                    batch_idx == 1
                    or batch_idx == total_valid_batches
                    or batch_idx % config.progress_batches == 0
                ):
                    print(
                        f"[vae] epoch {epoch + 1:03d}/{config.max_epochs} "
                        f"valid batch {batch_idx:,}/{total_valid_batches:,}",
                        flush=True,
                    )

        train_loss = float(np.mean(train_losses))
        valid_loss = float(np.mean(valid_losses))
        history.append(
            {"epoch": epoch + 1, "train_loss": train_loss, "valid_loss": valid_loss}
        )
        print(
            f"[vae] epoch {epoch + 1:03d}/{config.max_epochs} "
            f"train_loss={train_loss:.6f} valid_loss={valid_loss:.6f}",
            flush=True,
        )

        if valid_loss < best_valid_loss:
            best_valid_loss = valid_loss
            best_state = {
                key: value.cpu().clone() for key, value in model.state_dict().items()
            }
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= config.patience:
                print(f"[vae] early stopping after epoch {epoch + 1}", flush=True)
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    return {
        "model": model,
        "config": config,
        "history": history,
        "input_dim": int(X_train.shape[1]),
        "device": str(device),
    }


def _score_vae_batches(
    model,
    X: np.ndarray,
    config: VAEConfig,
    device,
    batch_size: int,
    label: str = "vae",
) -> np.ndarray:
    torch_module, _, _ = _ensure_torch()

    scores = []
    total_batches = int(np.ceil(len(X) / batch_size))

    model.eval()

    with torch_module.no_grad():
        for batch_idx, start in enumerate(range(0, len(X), batch_size), start=1):
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

            if batch_idx == 1 or batch_idx == total_batches or batch_idx % 10 == 0:
                print(
                    f"[vae] scoring {label}: batch {batch_idx}/{total_batches}",
                    flush=True,
                )

    return torch_module.cat(scores).cpu().numpy()


def serializable_vae_bundle(model_bundle: dict) -> dict:
    model = model_bundle["model"]
    return {
        "state_dict": {key: value.cpu() for key, value in model.state_dict().items()},
        "config": model_bundle["config"],
        "history": model_bundle["history"],
        "input_dim": model_bundle["input_dim"],
        "device": model_bundle["device"],
    }


def score_vae_anomaly_model(
    model_bundle: dict, X: np.ndarray, label: str = "vae"
) -> np.ndarray:
    torch_module, _, vae_cls = _ensure_torch()

    if "model" in model_bundle:
        model = model_bundle["model"]
    else:
        model = vae_cls(
            input_dim=model_bundle["input_dim"], config=model_bundle["config"]
        )
        model.load_state_dict(model_bundle["state_dict"])

    config: VAEConfig = model_bundle["config"]
    device = resolve_device(config)
    X = np.asarray(X, dtype=np.float32)

    model = model.to(device)
    return _score_vae_batches(
        model,
        X,
        config,
        device,
        batch_size=1024,
        label=label,
    )
