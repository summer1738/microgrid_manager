import os
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model

from .train_lstm_pv import (
    BASE_DIR,
    LOOKBACK_HOURS,
    MODEL_PATH,
    SCALER_PATH,
    METADATA_PATH,
    CSV_PATH,
    HOURLY_CSV_PATH,
)


def _load_metadata():
    if os.path.isfile(METADATA_PATH):
        import json
        with open(METADATA_PATH) as f:
            return json.load(f)
    return {"hourly": True, "n_features": 3}


def _get_hourly_df(csv_path: str | None = None) -> pd.DataFrame:
    if csv_path is None:
        csv_path = CSV_PATH
    if os.path.isfile(HOURLY_CSV_PATH):
        df = pd.read_csv(HOURLY_CSV_PATH)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.sort_values("timestamp").reset_index(drop=True)
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"Data not found: {csv_path}. Run generate_training_data.py or generate_training_data_hourly.py")
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    hourly = df.set_index("timestamp")[["pv_generation"]].resample("1h").mean().dropna().reset_index()
    return hourly


def _build_input_3feat(pv_values: np.ndarray, hours: np.ndarray, scaler) -> np.ndarray:
    """Build (1, 24, 3) input: pv_scaled, sin(h), cos(h)."""
    pv_scaled = scaler.transform(pv_values.reshape(-1, 1)).flatten()
    h = hours if len(hours) == LOOKBACK_HOURS else hours[-LOOKBACK_HOURS:]
    h = np.asarray(h, dtype=float)
    if len(h) != LOOKBACK_HOURS:
        raise ValueError(f"Need {LOOKBACK_HOURS} hour values, got {len(h)}")
    sin_h = np.sin(2 * np.pi * h / 24)
    cos_h = np.cos(2 * np.pi * h / 24)
    feats = np.stack([pv_scaled, sin_h, cos_h], axis=1)
    return feats.reshape(1, LOOKBACK_HOURS, 3).astype(np.float32)


def load_pv_model_and_scaler():
    model = load_model(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def predict_next_hour_from_history(history_pv: Sequence[float], history_hours: Sequence[float] | None = None) -> float:
    """
    Predict next-hour PV (W) given the last LOOKBACK_HOURS hourly PV values.
    If history_hours is None, hours are assumed 0..23 (last 24 hours of the day).
    """
    pv = np.array(history_pv, dtype=float)
    if pv.shape[0] != LOOKBACK_HOURS:
        raise ValueError(f"Expected {LOOKBACK_HOURS} history points, got {pv.shape[0]}")
    if history_hours is None:
        history_hours = np.arange(LOOKBACK_HOURS, dtype=float)
    hours = np.array(history_hours, dtype=float)
    model, scaler = load_pv_model_and_scaler()
    meta = _load_metadata()
    if meta.get("n_features", 1) == 1:
        history_scaled = scaler.transform(pv.reshape(-1, 1))
        X = history_scaled.reshape(1, LOOKBACK_HOURS, 1)
    else:
        X = _build_input_3feat(pv, hours, scaler)
    y_scaled = model.predict(X, verbose=0)
    y_inv = scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()
    return float(y_inv[0])


def predict_next_hour_from_csv(csv_path: str | None = None) -> float:
    """Load hourly data (or resample from 1-min), take last 24 hours, predict next hour."""
    hourly = _get_hourly_df(csv_path)
    if len(hourly) < LOOKBACK_HOURS:
        raise ValueError(f"Need at least {LOOKBACK_HOURS} hourly rows, got {len(hourly)}")
    pv = hourly["pv_generation"].values[-LOOKBACK_HOURS:]
    times = pd.to_datetime(hourly["timestamp"])
    hours = (times.dt.hour + times.dt.minute / 60.0).values[-LOOKBACK_HOURS:]
    return predict_next_hour_from_history(pv.tolist(), hours.tolist())


def predict_next_6_from_csv(csv_path: str | None = None) -> list[float]:
    """Rolling 6-step ahead forecast using last 24 hourly values from CSV."""
    hourly = _get_hourly_df(csv_path)
    if len(hourly) < LOOKBACK_HOURS:
        raise ValueError(f"Need at least {LOOKBACK_HOURS} hourly rows, got {len(hourly)}")
    model, scaler = load_pv_model_and_scaler()
    meta = _load_metadata()
    n_feat = meta.get("n_features", 3)

    pv_list = hourly["pv_generation"].values[-LOOKBACK_HOURS:].tolist()
    times = pd.to_datetime(hourly["timestamp"])
    hour_list = (times.dt.hour + times.dt.minute / 60.0).values[-LOOKBACK_HOURS:].tolist()

    forecasts = []
    for step in range(6):
        pv_arr = np.array(pv_list[-LOOKBACK_HOURS:], dtype=float)
        if n_feat == 1:
            X = scaler.transform(pv_arr.reshape(-1, 1)).reshape(1, LOOKBACK_HOURS, 1)
        else:
            hour_arr = np.array(hour_list[-LOOKBACK_HOURS:], dtype=float)
            X = _build_input_3feat(pv_arr, hour_arr, scaler)
        y_scaled = model.predict(X, verbose=0)
        y_inv = scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()[0]
        forecasts.append(float(y_inv))
        next_hour = (hour_list[-1] + 1) % 24 if hour_list else float(step)
        pv_list.append(y_inv)
        hour_list.append(next_hour)

    return forecasts


if __name__ == "__main__":
    forecast = predict_next_hour_from_csv()
    print(f"Next-hour PV forecast (W): {forecast:.2f}")
