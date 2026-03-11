import json
import os

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import LSTM, Dense, Input
from tensorflow.keras.models import Model

# -----------------------------
# Parameters
# -----------------------------
LOOKBACK_HOURS = 24
PREDICTION_HOURS = 1
TARGET_MAPE_PCT = 15.0  # Target for "reliable" forecasts; report met/not met

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "processed")
CSV_PATH = os.path.join(DATA_DIR, "training_data_30_days.csv")
HOURLY_CSV_PATH = os.path.join(DATA_DIR, "training_data_30_days_hourly.csv")
MODEL_PATH = os.path.join(BASE_DIR, "pv_lstm_model.keras")
SCALER_PATH = os.path.join(BASE_DIR, "pv_scaler.joblib")
METADATA_PATH = os.path.join(BASE_DIR, "pv_model_metadata.json")


def load_hourly_pv(csv_path: str) -> pd.DataFrame:
    """Load or create hourly PV series. Prefer hourly CSV; else resample 1-min."""
    if os.path.isfile(HOURLY_CSV_PATH):
        df = pd.read_csv(HOURLY_CSV_PATH)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.sort_values("timestamp").reset_index(drop=True)

    if not os.path.isfile(csv_path):
        raise FileNotFoundError(
            f"Training data not found: {csv_path}. Run generate_training_data.py or generate_training_data_hourly.py"
        )

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    hourly = df.set_index("timestamp")[["pv_generation"]].resample("1h").mean().dropna()
    hourly = hourly.reset_index()
    hourly.to_csv(HOURLY_CSV_PATH, index=False)
    print(f"📁 Resampled to hourly and saved: {HOURLY_CSV_PATH}")
    return hourly


def prepare_dataset(csv_path: str = CSV_PATH):
    """Build sequences: 24 hours of (pv_scaled, hour_sin, hour_cos) -> next hour PV."""
    hourly = load_hourly_pv(csv_path)
    pv = hourly["pv_generation"].values.reshape(-1, 1)
    times = pd.to_datetime(hourly["timestamp"])

    scaler = MinMaxScaler()
    pv_scaled = scaler.fit_transform(pv).flatten()

    hours = times.dt.hour.values + times.dt.minute.values / 60.0
    hour_sin = np.sin(2 * np.pi * hours / 24)
    hour_cos = np.cos(2 * np.pi * hours / 24)

    X, y = [], []
    for i in range(LOOKBACK_HOURS, len(pv_scaled) - PREDICTION_HOURS):
        feats = np.stack([
            pv_scaled[i - LOOKBACK_HOURS : i],
            hour_sin[i - LOOKBACK_HOURS : i],
            hour_cos[i - LOOKBACK_HOURS : i],
        ], axis=1)
        X.append(feats)
        y.append(pv_scaled[i : i + PREDICTION_HOURS])

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)

    split = int(0.8 * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    return X_train, X_test, y_train, y_test, scaler


def build_model(input_shape):
    """LSTM on 24h of (pv, sin_h, cos_h) -> next hour PV."""
    inp = Input(shape=input_shape)
    x = LSTM(64, return_sequences=True)(inp)
    x = LSTM(32)(x)
    x = Dense(16, activation="relu")(x)
    out = Dense(PREDICTION_HOURS)(x)
    model = Model(inp, out)
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def train_and_evaluate():
    X_train, X_test, y_train, y_test, scaler = prepare_dataset()
    print(f"📊 Samples: train={len(X_train)}, test={len(X_test)}")

    model = build_model((X_train.shape[1], X_train.shape[2]))
    model.summary()

    early_stop = EarlyStopping(
        monitor="val_loss",
        patience=8,
        restore_best_weights=True,
    )
    reduce_lr = ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=3,
        min_lr=1e-5,
    )

    history = model.fit(
        X_train,
        y_train,
        validation_split=0.2,
        epochs=80,
        batch_size=32,
        callbacks=[early_stop, reduce_lr],
        verbose=1,
    )

    y_pred = model.predict(X_test)
    y_test_flat = y_test.reshape(-1)
    y_pred_flat = y_pred.reshape(-1)

    y_test_inv = scaler.inverse_transform(y_test_flat.reshape(-1, 1)).flatten()
    y_pred_inv = scaler.inverse_transform(y_pred_flat.reshape(-1, 1)).flatten()

    mask = y_test_inv > 5.0
    if mask.sum() == 0:
        mask = np.ones_like(y_test_inv, dtype=bool)
    y_true = y_test_inv[mask]
    y_hat = y_pred_inv[mask]

    mape = np.mean(np.abs((y_true - y_hat) / (y_true + 1e-6))) * 100
    mae = np.mean(np.abs(y_true - y_hat))

    print(f"\n📊 PV Forecast MAPE: {mape:.2f}%")
    print(f"📊 PV Forecast MAE : {mae:.2f} W")
    met = mape <= TARGET_MAPE_PCT
    print(f"📊 Target MAPE ≤{TARGET_MAPE_PCT}%: {'✅ Met' if met else '❌ Not met'}")

    metrics = {"mae": float(mae), "mape_pct": float(mape), "target_mape_pct": TARGET_MAPE_PCT, "target_met": met}
    metrics_path = os.path.join(BASE_DIR, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    plt.figure(figsize=(10, 4))
    plt.plot(y_test_inv[:168], label="Actual PV (W)")
    plt.plot(y_pred_inv[:168], label="Predicted PV (W)")
    plt.legend()
    plt.title("PV Generation Forecast (Next Hour) — Hourly Model")
    plt.xlabel("Hour index")
    plt.tight_layout()
    plt.savefig(os.path.join(BASE_DIR, "pv_forecast_plot.png"))
    plt.close()
    print("📈 Forecast plot saved")

    model.save(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    with open(METADATA_PATH, "w") as f:
        json.dump({"hourly": True, "lookback_hours": LOOKBACK_HOURS, "n_features": 3}, f)
    print(f"✅ Model saved to {MODEL_PATH}")
    print(f"✅ Scaler saved to {SCALER_PATH}")
    print(f"✅ Metadata saved to {METADATA_PATH}")


if __name__ == "__main__":
    train_and_evaluate()
