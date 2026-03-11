"""
Generate 30-day hourly PV training data with a clear diurnal pattern for LSTM forecasting.
Use this for better MAPE: 24h lookback predicts next hour with a learnable solar curve.
"""
import csv
import math
import random
from datetime import datetime, timedelta

DAYS = 30
PV_PEAK_W = 2500

# Clear-sky curve: sine from sunrise (~6) to sunset (~18)
def solar_power_hourly(hour_float: float, clear_sky: bool = True, day_noise: float = 0.0) -> float:
    # hour_float in 0..24
    h = hour_float % 24
    if h < 6 or h > 18:
        return 0.0
    # Sine shape between 6 and 18
    x = (h - 6) / 12.0 * math.pi
    base = math.sin(x) * PV_PEAK_W
    if not clear_sky:
        base *= random.uniform(0.35, 0.7)  # cloudy: reduce but not to zero
    # Small per-hour noise (W)
    noise = random.gauss(0, 40)
    return max(0.0, base + noise + day_noise)


def main():
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS)
    rows = []
    for day in range(DAYS):
        current = start + timedelta(days=day)
        # Slight day-to-day variation (e.g. seasonal or clear vs cloudy day)
        day_clear = random.random() > 0.25  # 75% clear days
        day_noise = random.gauss(0, 30)
        for hour in range(24):
            ts = current + timedelta(hours=hour)
            hour_float = hour + 0.5  # use mid-hour
            pv = solar_power_hourly(hour_float, clear_sky=day_clear, day_noise=day_noise)
            rows.append([ts, round(pv, 2)])

    out_path = "data/processed/training_data_30_days_hourly.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "pv_generation"])
        writer.writerows(rows)

    print("✅ Hourly PV training data generated:")
    print(f"   {out_path}")
    print(f"   Rows: {len(rows)} (30 days × 24 h)")


if __name__ == "__main__":
    main()
