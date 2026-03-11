import os
from typing import Sequence

import joblib
import numpy as np
from tensorflow.keras.models import load_model

from .train_lstm_pv import LOOKBACK_HOURS, MODEL_PATH, SCALER_PATH, BASE_DIR


def load_pv_model_and_scaler():
    model = load_model(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def predict_next_hour_from_history(history_pv: Sequence[float]) -> float:
    """
    Predict next-hour PV generation given the last LOOKBACK_HOURS PV values.

    history_pv: iterable of recent PV values (same units as training CSV)
    """
    history = np.array(history_pv, dtype=float)
    if history.shape[0] != LOOKBACK_HOURS:
        raise ValueError(f"Expected {LOOKBACK_HOURS} history points, got {history.shape[0]}")

    model, scaler = load_pv_model_and_scaler()

    history_scaled = scaler.transform(history.reshape(-1, 1))
    X = history_scaled.reshape(1, LOOKBACK_HOURS, 1)

    y_scaled = model.predict(X)
    y_inv = scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()
    return float(y_inv[0])


def predict_next_hour_from_csv(csv_path: str | None = None) -> float:
    """
    Convenience helper: load the training CSV, take the last LOOKBACK_HOURS
    PV values, and predict the next hour.
    """
    import pandas as pd

    if csv_path is None:
        csv_path = os.path.join(
            BASE_DIR,
            "..",
            "data",
            "processed",
            "training_data_30_days.csv",
        )

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    pv_series = df["pv_generation"].values
    if pv_series.shape[0] < LOOKBACK_HOURS:
        raise ValueError("Not enough data to build history window")

    history = pv_series[-LOOKBACK_HOURS:]
    return predict_next_hour_from_history(history)


if __name__ == "__main__":
    forecast = predict_next_hour_from_csv()
    print(f"Next-hour PV forecast (simulated data): {forecast:.3f}")

