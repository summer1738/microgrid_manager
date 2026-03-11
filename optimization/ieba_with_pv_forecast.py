import os

import joblib
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model

from optimization.ieba import CSV_PATH, SOC_START, load_single_day, run_ieba_series

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

MODEL_PATH = os.path.join(PROJECT_ROOT, "forecasting", "pv_lstm_model.keras")
SCALER_PATH = os.path.join(PROJECT_ROOT, "forecasting", "pv_scaler.joblib")
LOOKBACK_HOURS = 24


def load_pv_model_and_scaler():
    model = load_model(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def build_pv_forecast_for_day(csv_path: str = CSV_PATH):
    """
    Build a recursive multi-step PV forecast for one day,
    using the trained LSTM model and previous-day history.
    """
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    df["date"] = df["timestamp"].dt.date
    dates = sorted(df["date"].unique())
    if len(dates) < 2:
        raise ValueError("Need at least two days of data for forecast history")

    target_date = dates[-2]
    prev_date = dates[-3] if len(dates) >= 3 else dates[-2]

    prev_df = df[df["date"] == prev_date].copy()
    day_df = df[df["date"] == target_date].copy().reset_index(drop=True)

    pv_prev = prev_df["pv_generation"].values
    if pv_prev.shape[0] < LOOKBACK_HOURS:
        raise ValueError("Previous day does not have enough samples for history window")

    # Use last LOOKBACK_HOURS points from previous day as starting history
    history = list(pv_prev[-LOOKBACK_HOURS:])

    model, scaler = load_pv_model_and_scaler()

    pv_forecast = []
    for _ in range(len(day_df)):
        hist_arr = np.array(history[-LOOKBACK_HOURS:], dtype=float)
        hist_scaled = scaler.transform(hist_arr.reshape(-1, 1))
        X = hist_scaled.reshape(1, LOOKBACK_HOURS, 1)
        y_scaled = model.predict(X, verbose=0)
        y_inv = scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()[0]
        pv_forecast.append(y_inv)
        # Append forecast (not ground truth) to maintain a pure recursive forecast
        history.append(y_inv)

    pv_forecast = np.array(pv_forecast)
    return day_df, pv_forecast


def compare_perfect_vs_forecast_ieba():
    # Perfect-information IEBA using true PV
    day_df = load_single_day(CSV_PATH)
    timestamps = day_df["timestamp"].values
    pv_true = day_df["pv_generation"].values
    fridge_w = day_df["fridge_load"].values
    pump_w = day_df["pump_load"].values

    perfect_schedule, perfect_stats = run_ieba_series(
        timestamps, pv_true, fridge_w, pump_w, soc_start=SOC_START
    )

    # Forecast-driven IEBA
    forecast_day_df, pv_forecast = build_pv_forecast_for_day(CSV_PATH)
    ts_f = forecast_day_df["timestamp"].values
    fridge_f = forecast_day_df["fridge_load"].values
    pump_f = forecast_day_df["pump_load"].values

    forecast_schedule, forecast_stats = run_ieba_series(
        ts_f, pv_forecast, fridge_f, pump_f, soc_start=SOC_START
    )

    print("\n=== IEBA Comparison: Perfect vs Forecasted PV ===")
    print("Perfect-information IEBA:")
    print(
        f"  Critical uptime={perfect_stats.critical_uptime_pct:.2f}%, "
        f"pump uptime={perfect_stats.pump_uptime_pct:.2f}%, "
        f"SOC violations={perfect_stats.soc_violations}"
    )

    print("\nForecast-driven IEBA:")
    print(
        f"  Critical uptime={forecast_stats.critical_uptime_pct:.2f}%, "
        f"pump uptime={forecast_stats.pump_uptime_pct:.2f}%, "
        f"SOC violations={forecast_stats.soc_violations}"
    )

    return (
        (perfect_schedule, perfect_stats),
        (forecast_schedule, forecast_stats),
    )


if __name__ == "__main__":
    compare_perfect_vs_forecast_ieba()

