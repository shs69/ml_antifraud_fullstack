from __future__ import annotations

import json
import os
import tempfile
import textwrap
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "fraud_stream_matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "fraud_stream_cache"))

import matplotlib.pyplot as plt
import pandas as pd

from fraud_stream.config import TARGET


METRIC_LABELS = {
    "precision": "Точность",
    "recall": "Полнота",
    "f1": "F1-мера",
    "pr_auc": "PR AUC",
    "roc_auc": "ROC AUC",
}

EXPERIMENT_LABELS = {
    "supervised": "Обучение с учителем",
    "anomaly": "Поиск аномалий",
    "hybrid": "Гибридный подход",
    "unseen_scenario_2": "Новый сценарий 2",
    "unseen_scenario_3": "Новый сценарий 3",
}

MODEL_LABELS = {
    "logreg": "Логистическая регрессия",
    "logistic_regression": "Логистическая регрессия",
    "random_forest": "Случайный лес",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "isolation_forest": "Isolation Forest",
    "autoencoder": "Автоэнкодер",
    "vae": "VAE",
    "supervised": "Модель с учителем",
    "anomaly": "Аномальная модель",
    "hybrid": "Гибридная модель",
    "supervised_lightgbm": "LightGBM с учителем",
    "lightgbm_only": "LightGBM",
    "autoencoder_recall_threshold": "Автоэнкодер, порог по полноте",
    "autoencoder_quantile_threshold": "Автоэнкодер, квантильный порог",
    "hybrid_or": "Гибридное ИЛИ",
    "hybrid_weighted": "Взвешенный гибрид",
    "hybrid_weighted_average": "Взвешенный гибрид",
    "hybrid_max": "Гибрид по максимуму",
    "hybrid_probabilistic_or": "Вероятностное ИЛИ",
    "hybrid_two_threshold_or": "Гибрид с двумя порогами",
}


def _label_from_mapping(value: object, mapping: dict[str, str]) -> str:
    text = str(value)
    return mapping.get(text, text.replace("_", " "))


def _wrap_label(value: object, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(value), width=width, break_long_words=False))


def _savefig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight", pad_inches=0.2)
    plt.close()


def save_eda_report(df: pd.DataFrame, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    df["TX_DATETIME"] = pd.to_datetime(df["TX_DATETIME"])

    overview = {
        "rows": int(len(df)),
        "date_min": str(df["TX_DATETIME"].min()),
        "date_max": str(df["TX_DATETIME"].max()),
        "fraud_count": int(df[TARGET].sum()),
        "fraud_rate": float(df[TARGET].mean()),
        "customers": int(df["CUSTOMER_ID"].nunique()) if "CUSTOMER_ID" in df else None,
        "terminals": int(df["TERMINAL_ID"].nunique()) if "TERMINAL_ID" in df else None,
        "amount_mean": float(df["TX_AMOUNT"].mean()),
        "amount_median": float(df["TX_AMOUNT"].median()),
        "amount_p99": float(df["TX_AMOUNT"].quantile(0.99)),
    }

    daily = df.set_index("TX_DATETIME").resample("D")[TARGET].agg(["count", "sum"])
    daily["fraud_rate"] = daily["sum"] / daily["count"].clip(lower=1)
    daily_plot = daily[["count", "sum"]].rename(
        columns={
            "count": "Всего транзакций",
            "sum": "Мошеннические операции",
        }
    )
    ax = daily_plot.plot(figsize=(10, 4), secondary_y="Мошеннические операции")
    ax.set_title("Дневной объем транзакций и число мошеннических операций")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Количество транзакций")
    _savefig(out_dir / "eda_daily_volume_fraud.png")

    ax = daily["fraud_rate"].plot(figsize=(10, 4))
    ax.set_title("Дневная доля мошеннических операций")
    ax.set_xlabel("Дата")
    ax.set_ylabel("Доля мошенничества")
    _savefig(out_dir / "eda_daily_fraud_rate.png")

    amount_sample = df[["TX_AMOUNT", TARGET]].sample(min(len(df), 100_000), random_state=42)
    ax = amount_sample.boxplot(column="TX_AMOUNT", by=TARGET, figsize=(7, 4), showfliers=False)
    ax.set_title("Сумма транзакции по классам")
    ax.set_xlabel("Метка мошенничества")
    ax.set_ylabel("Сумма")
    plt.suptitle("")
    _savefig(out_dir / "eda_amount_by_label.png")

    if "TX_FRAUD_SCENARIO" in df:
        scenario_counts = df[df[TARGET] == 1]["TX_FRAUD_SCENARIO"].value_counts().sort_index()
        ax = scenario_counts.plot(kind="bar", figsize=(7, 4))
        ax.set_title("Распределение количества мошеннических операций по сценариям")
        ax.set_xlabel("Сценарии")
        ax.set_ylabel("Количество мошеннических операций")
        _savefig(out_dir / "eda_fraud_scenarios.png")

    if "hour" in df:
        hourly = df.groupby("hour")[TARGET].mean()
        ax = hourly.plot(kind="bar", figsize=(8, 4))
        ax.set_title("Доля мошеннических операций по часам")
        ax.set_xlabel("Час")
        ax.set_ylabel("Доля мошенничества")
        _savefig(out_dir / "eda_fraud_rate_by_hour.png")

    with open(out_dir / "eda_overview.json", "w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)
    return overview


def _flatten_model_results(results: dict) -> pd.DataFrame:
    rows = []
    for model_name, model_result in results.items():
        if not isinstance(model_result, dict) or "test" not in model_result:
            continue
        metrics = model_result["test"]
        if not isinstance(metrics, dict):
            continue
        rows.append(
            {
                "model": model_name,
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1": metrics.get("f1"),
                "pr_auc": metrics.get("pr_auc"),
                "roc_auc": metrics.get("roc_auc"),
                "fp": metrics.get("fp"),
                "fn": metrics.get("fn"),
                "tp": metrics.get("tp"),
            }
        )
    return pd.DataFrame(rows)


def save_metric_comparison(results_by_file: dict[str, dict], out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for source_name, results in results_by_file.items():
        frame = _flatten_model_results(results)
        if not frame.empty:
            frame.insert(0, "experiment", source_name)
            frames.append(frame)

    if not frames:
        return pd.DataFrame()

    metrics = pd.concat(frames, ignore_index=True)
    metrics.to_csv(out_dir / "model_metric_comparison.csv", index=False)

    for metric in ["precision", "recall", "f1", "pr_auc", "roc_auc"]:
        plot_df = metrics.dropna(subset=[metric])
        if plot_df.empty:
            continue
        labels = [
            _wrap_label(
                f"{_label_from_mapping(row.experiment, EXPERIMENT_LABELS)}: "
                f"{_label_from_mapping(row.model, MODEL_LABELS)}"
            )
            for row in plot_df.itertuples(index=False)
        ]
        figure_width = max(12, len(labels) * 1.05)
        ax = plot_df.set_index(pd.Index(labels))[metric].plot(kind="bar", figsize=(figure_width, 6))
        ax.set_title(f"Тестовая метрика: {METRIC_LABELS.get(metric, metric)}")
        ax.set_xlabel("Модель")
        ax.set_ylabel(METRIC_LABELS.get(metric, metric))
        ax.tick_params(axis="x", labelrotation=35)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")
        plt.subplots_adjust(bottom=0.35)
        _savefig(out_dir / f"comparison_{metric}.png")

    return metrics


def save_anomaly_training_curve(anomaly_results: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    autoencoder = anomaly_results.get("autoencoder", {})
    history = autoencoder.get("train_history") or []
    if not history:
        return

    history_df = pd.DataFrame(history)
    history_df.to_csv(out_dir / "autoencoder_training_history.csv", index=False)

    loss_columns = {
        "train_loss": "Ошибка на обучении",
        "valid_loss": "Ошибка на валидации",
    }
    available_loss_columns = [c for c in loss_columns if c in history_df]
    history_plot_df = history_df.rename(columns=loss_columns)
    ax = history_plot_df.plot(
        x="epoch",
        y=[loss_columns[c] for c in available_loss_columns],
        figsize=(8, 4),
    )
    model_type = autoencoder.get("model_type", "unknown")
    ax.set_title(f"Кривая обучения автоэнкодера ({_label_from_mapping(model_type, MODEL_LABELS)})")
    ax.set_xlabel("Эпоха")
    ax.set_ylabel("Функция потерь")
    _savefig(out_dir / "training_autoencoder_curve.png")


def write_research_notes(out_dir: Path) -> None:
    notes = {
        "main_findings_to_check": [
            "Сравнить модели с учителем с веткой поиска аномалий на временном тестовом разбиении.",
            "Для экспериментов с неизвестными сценариями мошенничества подчеркнуть компромисс между точностью, полнотой и количеством ложных срабатываний.",
            "Если полнота поиска аномалий улучшается после добавления признаков скорости и новизны, значит прежняя слабость частично была связана с набором признаков.",
            "Если сценарий 3 остается слабым, описать его как хуже отделимый текущими поведенческими сигналами.",
        ],
        "defense_materials": [
            "EDA-графики по дисбалансу датасета, временной динамике, распределению сценариев и поведению сумм транзакций.",
            "Графики сравнения метрик для моделей с учителем, поиска аномалий и гибридного подхода.",
            "Кривая обучения автоэнкодера/VAE и описание стратегии выбора порога.",
            "Явный вывод о том, что поиск аномалий полезен для неизвестного мошенничества, но требует калибровки.",
        ],
    }
    with open(out_dir / "research_notes.json", "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
