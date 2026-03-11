import csv
import math
import random
from datetime import datetime, timedelta

# -----------------------------
# Simulation Parameters
# -----------------------------
DAYS = 30
INTERVAL_SECONDS = 60
BATTERY_CAPACITY_WH = 5000     # 5 kWh battery
SOC_MIN = 20.0
SOC_MAX = 100.0
SOC_SHED_THRESHOLD = 40.0
PV_PEAK_W = 2500

# -----------------------------
# Helper Functions
# -----------------------------
def solar_power(hour, cloudy=False):
    """Simulate PV generation"""
    base = max(0, math.sin((hour - 6) / 12 * math.pi)) * PV_PEAK_W
    if cloudy:
        base *= random.uniform(0.2, 0.4)  # heavy cloud
    noise = random.uniform(-50, 50)
    return max(0, base + noise)

def fridge_load(hour):
    return 150  # always on (critical)

def pump_load(hour):
    return 800 if 10 <= hour <= 12 else 0

# -----------------------------
# Main Generator
# -----------------------------
start_time = datetime.now() - timedelta(days=DAYS)
current_time = start_time
soc = 75.0  # starting SOC %

rows = []

for _ in range(int((DAYS * 24 * 3600) / INTERVAL_SECONDS)):
    hour = current_time.hour

    # Randomly decide if today is cloudy
    cloudy = random.random() < 0.25

    pv = solar_power(hour, cloudy)
    fridge = fridge_load(hour)
    pump = pump_load(hour)

    status = "NORMAL"

    # Load shedding rule
    if soc < SOC_SHED_THRESHOLD:
        pump = 0
        status = "SHEDDING ACTIVE"

    total_load = fridge + pump

    # Energy balance
    net_power = pv - total_load
    net_energy_wh = net_power * (INTERVAL_SECONDS / 3600)

    soc += (net_energy_wh / BATTERY_CAPACITY_WH) * 100
    soc = max(SOC_MIN, min(SOC_MAX, soc))

    rows.append([
        current_time,
        round(pv, 2),
        round(soc, 2),
        fridge,
        pump,
        status
    ])

    current_time += timedelta(seconds=INTERVAL_SECONDS)

# -----------------------------
# Write CSV
# -----------------------------
with open("data/processed/training_data_30_days.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp",
        "pv_generation",
        "battery_soc",
        "fridge_load",
        "pump_load",
        "status"
    ])
    writer.writerows(rows)

print("✅ 30-day synthetic dataset generated:")
print("   data/processed/training_data_30_days.csv")
print(f"   Total rows: {len(rows)}")