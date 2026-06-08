from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fraud_stream.config import ARTIFACTS_DIR
from fraud_stream.data.features_io import load_feature_table
from fraud_stream.research.reporting import (
    save_anomaly_training_curve,
    save_eda_report,
    save_metric_comparison,
    write_research_notes,
)


def load_json_if_exists(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(ARTIFACTS_DIR / "research_report"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] Loading feature table")
    df = load_feature_table()

    print("[2/4] Saving EDA plots")
    save_eda_report(df, out_dir)

    print("[3/4] Saving metric comparisons")
    result_files = {
        "supervised": ARTIFACTS_DIR / "supervised_results.json",
        "anomaly": ARTIFACTS_DIR / "anomaly_results.json",
        "hybrid": ARTIFACTS_DIR / "hybrid_results.json",
        "unseen_scenario_2": ARTIFACTS_DIR / "unseen_scenario_2_v2_results.json",
        "unseen_scenario_3": ARTIFACTS_DIR / "unseen_scenario_3_v2_results.json",
    }
    results = {
        name: loaded
        for name, path in result_files.items()
        if (loaded := load_json_if_exists(path)) is not None
    }
    save_metric_comparison(results, out_dir)

    anomaly_results = results.get("anomaly")
    if anomaly_results is not None:
        save_anomaly_training_curve(anomaly_results, out_dir)

    print("[4/4] Writing research notes")
    write_research_notes(out_dir)
    print(f"Research report saved to {out_dir}")


if __name__ == "__main__":
    main()
