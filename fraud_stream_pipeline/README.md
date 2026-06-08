# Fraud Stream Pipeline для ВКР

Готовый модуль для экспериментов с транзакционным потоком Fraud Detection Handbook:

- загрузка simulated-data-raw;
- построение time/customer/terminal/geo features;
- temporal split;
- supervised fraud detection: Logistic Regression, Random Forest, XGBoost, LightGBM;
- anomaly detection: Isolation Forest + Autoencoder/VAE branch;
- hybrid risk score;
- SHAP reason codes;
- EDA/research report plots for ВКР;
- FastAPI endpoint для realtime scoring.

## Быстрый запуск

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/run_all.py --begin-date 2018-04-01 --end-date 2018-07-09
python scripts/make_research_report.py
```

Почему до 2018-07-09 по умолчанию: в публичном GitHub view видна часть файлов до этой даты. Если ты склонируешь полный репозиторий и там есть даты до 2018-09-30, можно поставить `--end-date 2018-09-30`.

## Запуск API

```bash
uvicorn fraud_stream.api.app:app --reload --app-dir src
```

Пример запроса:

```bash
curl -X POST http://127.0.0.1:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "TX_DATETIME": "2018-07-10T12:30:00",
    "CUSTOMER_ID": 123,
    "TERMINAL_ID": 456,
    "TX_AMOUNT": 250.0
  }'
```

## Что важно для ВКР

1. Card Transdata оставляется как baseline.
2. Этот pipeline используется как реалистичный поток транзакций.
3. Валидация делается по времени, а не random split.
4. Отдельно есть эксперимент unseen fraud scenario:
   - train без выбранного `TX_FRAUD_SCENARIO`;
   - test только на этом сценарии.
5. SHAP используется не просто как график, а для генерации analyst-readable reason codes.
6. Anomaly branch обучается только на normal transactions и использует velocity/novelty features.
7. Если PyTorch установлен, anomaly autoencoder запускается как VAE; иначе используется воспроизводимый MLP reconstruction fallback.

## Исследовательские артефакты

После обучения запусти:

```bash
python scripts/make_research_report.py
```

Скрипт сохранит в `artifacts/research_report/`:

- EDA-графики по объёму транзакций, fraud rate, сценариям и суммам;
- сравнение precision/recall/F1/PR-AUC/ROC-AUC для моделей и hybrid;
- график обучения autoencoder/VAE, если история обучения есть в `anomaly_results.json`;
- `research_notes.json` с тезисами для выводов.

Для полноценного VAE установи PyTorch отдельно под совместимую версию Python. На Python 3.14 PyTorch может быть недоступен, поэтому fallback оставлен намеренно.
