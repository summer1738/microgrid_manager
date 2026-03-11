import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("data/processed/training_data_30_days.csv")

df["timestamp"] = pd.to_datetime(df["timestamp"])

plt.figure()
plt.plot(df["timestamp"], df["pv_generation"], label="PV Generation (W)")
plt.plot(df["timestamp"], df["fridge_load"] + df["pump_load"], label="Load (W)")
plt.legend()
plt.title("PV vs Load (30-Day Simulation)")
plt.show()

plt.figure()
plt.plot(df["timestamp"], df["battery_soc"], label="Battery SOC (%)")
plt.axhline(40, linestyle="--", label="Shedding Threshold")
plt.legend()
plt.title("Battery SOC Over Time")
plt.show()