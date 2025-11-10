from typing import Tuple
import pandas as pd
import numpy as np
from imblearn.pipeline import Pipeline
import joblib


def load_model(filename: str) -> Pipeline:
    with open(filename, 'rb') as f:
        model = joblib.load(f)
    return model


def predict_with_saved_model(model: Pipeline, new_data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:

    if isinstance(new_data, pd.Series):
        new_data = new_data.to_frame().T

    predictions = model.predict(new_data)
    probabilities = model.predict_proba(new_data)

    return predictions, probabilities


def get_parsed_predict(model: Pipeline, data: pd.DataFrame) -> list[int]:
    pred, _ = predict_with_saved_model(model, data)
    return [int(x) for x in pred.tolist()]
