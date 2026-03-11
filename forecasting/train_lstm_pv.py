import os

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.models import Sequential


# -----------------------------
# Parameters
# -----------------------------
LOOKBACK_HOURS = 24          # Input window
PREDICTION_HOURS = 1         # Predict next hour

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(
    BASE_DIR,
    "..",
    "data",
    "processed",
    "training_data_30_days.csv",
)
MODEL_PATH = os.path.join(BASE_DIR, "pv_lstm_model.keras")
SCALER_PATH = os.path.join(BASE_DIR, "pv_scaler.joblib")


def prepare_dataset(csv_path: str = CSV_PATH):
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    pv_data = df[["pv_generation"]].values

    scaler = MinMaxScaler()
    pv_scaled = scaler.fit_transform(pv_data)

    X, y = [], []
    for i in range(LOOKBACK_HOURS, len(pv_scaled) - PREDICTION_HOURS):
        X.append(pv_scaled[i - LOOKBACK_HOURS : i])
        y.append(pv_scaled[i : i + PREDICTION_HOURS])

    X = np.array(X)
    y = np.array(y)

    split = int(0.8 * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    return X_train, X_test, y_train, y_test, scaler


def build_model(input_shape):
    model = Sequential(
        [
            LSTM(64, input_shape=input_shape),
            Dense(PREDICTION_HOURS),
        ]
    )
    model.compile(optimizer="adam", loss="mse")
    return model


def train_and_evaluate():
    X_train, X_test, y_train, y_test, scaler = prepare_dataset()

    model = build_model((X_train.shape[1], X_train.shape[2]))
    model.summary()

    early_stop = EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True,
    )

    history = model.fit(
        X_train,
        y_train,
        validation_split=0.2,
        epochs=30,
        batch_size=32,
        callbacks=[early_stop],
        verbose=1,
    )

    y_pred = model.predict(X_test)

    y_test_flat = y_test.reshape(-1)
    y_pred_flat = y_pred.reshape(-1)

    y_test_inv = scaler.inverse_transform(y_test_flat.reshape(-1, 1)).flatten()
    y_pred_inv = scaler.inverse_transform(y_pred_flat.reshape(-1, 1)).flatten()

    # Evaluate only on non-nighttime values to avoid division by ~0
    mask = y_test_inv > 0.05
    y_true = y_test_inv[mask]
    y_hat = y_pred_inv[mask]

    mape = np.mean(np.abs((y_true - y_hat) / y_true)) * 100
    mae = np.mean(np.abs(y_true - y_hat))

    print(f"\n📊 PV Forecast MAPE: {mape:.2f}%")
    print(f"📊 PV Forecast MAE : {mae:.3f} (same units as pv_generation)")

    plt.figure()
    plt.plot(y_test_inv[:200], label="Actual PV")
    plt.plot(y_pred_inv[:200], label="Predicted PV")
    plt.legend()
    plt.title("PV Generation Forecast (Next Hour)")
    plt.savefig(os.path.join(BASE_DIR, "pv_forecast_plot.png"))
    print("📈 Forecast plot saved")

    model.save(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"✅ Model saved to {MODEL_PATH}")
    print(f"✅ Scaler saved to {SCALER_PATH}")


if __name__ == "__main__":
    train_and_evaluate()