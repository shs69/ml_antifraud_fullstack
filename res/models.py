# %% [markdown]
# # Модели без SMOTE
# %% [markdown]
# ## Разделение данных
# %%
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

plt.rcParams['figure.figsize'] = (8, 6)
plt.rcParams['figure.dpi'] = 300
# %%
df = pd.read_csv("../card_transdata.csv")
# %%
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

X = df.drop("fraud", axis=1)
y = df["fraud"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

print("Train class distribution:")
print(y_train.value_counts(normalize=True))

print("\nTest class distribution:")
print(y_test.value_counts(normalize=True))

scaler = StandardScaler()

X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print("\nShapes:")
print("X_train:", X_train.shape)
print("X_test:", X_test.shape)
print("X_train_scaled:", X_train_scaled.shape)
print("X_test_scaled:", X_test_scaled.shape)
# %% [markdown]
# На этапе подготовки данных исходная выборка была разделена на матрицу признаков и целевую переменную fraud. Далее данные были разделены на обучающую и тестовую выборки в соотношении 80/20 с использованием стратификации по целевому признаку. Это позволило сохранить исходное соотношение классов в обеих выборках, что особенно важно при наличии дисбаланса классов. После разделения было выполнено масштабирование признаков с помощью StandardScaler. Масштабирование применялось только после разделения данных, при этом параметры стандартизации рассчитывались исключительно на обучающей выборке, что позволило избежать утечки данных.
# %% [markdown]
# ## Baseline модель
# %%
from sklearn.linear_model import LogisticRegression

lr = LogisticRegression()

lr.fit(X_train_scaled, y_train)

y_pred_lr = lr.predict(X_test_scaled)
y_proba_lr = lr.predict_proba(X_test_scaled)[:, 1]
# %%
from sklearn.metrics import (
    confusion_matrix,
    ConfusionMatrixDisplay,
    roc_auc_score,
    RocCurveDisplay,
)

cm = confusion_matrix(y_test, y_pred_lr)
disp = ConfusionMatrixDisplay(confusion_matrix=cm)
disp.plot()
# %%
from sklearn.metrics import (
    classification_report,
    precision_recall_curve,
    average_precision_score,
    PrecisionRecallDisplay
)

print(classification_report(y_test, y_pred_lr))

roc_auc = roc_auc_score(y_test, y_proba_lr)

print("ROC-AUC:", roc_auc)

RocCurveDisplay.from_predictions(
    y_test,
    y_proba_lr
)

plt.title("ROC Curve - Logistic Regression")
plt.show()

ap_score = average_precision_score(
    y_test,
    y_proba_lr
)

print("Average Precision:", ap_score)

# PR Curve
PrecisionRecallDisplay.from_predictions(
    y_test,
    y_proba_lr
)

plt.title("Precision-Recall Curve")
plt.show()
# %%
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

thresholds = np.arange(0.1, 0.91, 0.1)

rows = []

for threshold in thresholds:
    y_pred_threshold = (y_proba_lr >= threshold).astype(int)

    rows.append({
        "threshold": threshold,
        "precision_fraud": precision_score(y_test, y_pred_threshold),
        "recall_fraud": recall_score(y_test, y_pred_threshold),
        "f1_fraud": f1_score(y_test, y_pred_threshold),
        "predicted_fraud_count": y_pred_threshold.sum()
    })

threshold_results = pd.DataFrame(rows)

threshold_results
# %%
plt.plot(
    threshold_results["threshold"],
    threshold_results["precision_fraud"],
    label="Precision"
)

plt.plot(
    threshold_results["threshold"],
    threshold_results["recall_fraud"],
    label="Recall"
)

plt.plot(
    threshold_results["threshold"],
    threshold_results["f1_fraud"],
    label="F1-score"
)

plt.xlabel("Threshold")
plt.ylabel("Score")

plt.title("Threshold Tuning - Logistic Regression")

plt.legend()

plt.grid(True)

plt.show()
# %%
