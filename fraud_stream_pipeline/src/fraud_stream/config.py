from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

RAW_REPO_URL = "https://github.com/Fraud-Detection-Handbook/simulated-data-raw.git"
RAW_REPO_DIR = RAW_DIR / "simulated-data-raw"
RAW_DATA_DIR = RAW_REPO_DIR / "data"

TARGET = "TX_FRAUD"
SCENARIO_COL = "TX_FRAUD_SCENARIO"

RANDOM_STATE = 42

# Признаки, которые нельзя давать модели.
# TX_FRAUD_SCENARIO нельзя использовать как feature: это почти прямая подсказка label/scenario.
LEAKAGE_COLUMNS = [
    "TX_FRAUD",
    "TX_FRAUD_SCENARIO",
    "TRANSACTION_ID",
    "TX_DATETIME",
]
