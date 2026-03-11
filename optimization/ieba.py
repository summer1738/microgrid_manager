import os
from dataclasses import dataclass

import numpy as np
import pandas as pd


TIME_STEP_SECONDS = 60
BATTERY_CAPACITY_WH = 5000
SOC_MIN = 40.0
SOC_MAX = 100.0
SOC_START = 80.0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(
    BASE_DIR,
    "..",
    "data",
    "processed",
    "training_data_30_days.csv",
)


@dataclass
class IEBAStats:
    critical_uptime_pct: float
    pump_uptime_pct: float
    soc_violations: int


def load_single_day(csv_path: str = CSV_PATH, day_index: int = -2) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    df["date"] = df["timestamp"].dt.date
    dates = sorted(df["date"].unique())
    if not dates:
        raise ValueError("No dates found in CSV")

    target_date = dates[day_index]
    day_df = df[df["date"] == target_date].copy()
    day_df = day_df.reset_index(drop=True)

    return day_df


def run_ieba_series(
    timestamps: np.ndarray,
    pv_w: np.ndarray,
    fridge_w: np.ndarray,
    pump_w: np.ndarray,
    soc_start: float = SOC_START,
) -> tuple[pd.DataFrame, IEBAStats]:
    soc = soc_start
    soc_violations = 0

    records: list[dict] = []

    critical_on_count = 0
    pump_on_count = 0
    total_steps = len(timestamps)

    for i in range(total_steps):
        ts = timestamps[i]
        pv_power_w = float(pv_w[i])
        f_w = float(fridge_w[i])
        p_w = float(pump_w[i])

        pv_energy_wh = pv_power_w * TIME_STEP_SECONDS / 3600.0
        fridge_energy_wh = f_w * TIME_STEP_SECONDS / 3600.0
        pump_energy_wh = p_w * TIME_STEP_SECONDS / 3600.0

        fridge_on = True

        net_after_fridge = pv_energy_wh - fridge_energy_wh

        if net_after_fridge >= 0:
            soc_after_fridge = soc
        else:
            needed_wh = -net_after_fridge
            available_batt_wh = max(0.0, (soc - SOC_MIN) / 100.0 * BATTERY_CAPACITY_WH)

            if needed_wh <= available_batt_wh:
                soc_after_fridge = soc - (needed_wh / BATTERY_CAPACITY_WH) * 100.0
            else:
                soc_after_fridge = max(
                    SOC_MIN,
                    soc - (available_batt_wh / BATTERY_CAPACITY_WH) * 100.0,
                )
                soc_violations += 1

        pump_on = False
        soc_after_pump = soc_after_fridge

        if p_w > 0:
            net_after_pump = net_after_fridge - pump_energy_wh

            if net_after_pump >= 0:
                pump_on = True
                soc_after_pump = soc_after_fridge
            else:
                needed_wh_pump = -net_after_pump
                available_batt_wh = max(
                    0.0,
                    (soc_after_fridge - SOC_MIN) / 100.0 * BATTERY_CAPACITY_WH,
                )

                if needed_wh_pump <= available_batt_wh:
                    pump_on = True
                    soc_after_pump = soc_after_fridge - (
                        needed_wh_pump / BATTERY_CAPACITY_WH
                    ) * 100.0
                else:
                    pump_on = False
                    soc_after_pump = soc_after_fridge

        total_load_w = f_w + (p_w if pump_on else 0.0)
        total_load_wh = total_load_w * TIME_STEP_SECONDS / 3600.0
        net_wh = pv_energy_wh - total_load_wh
        if net_wh > 0:
            soc_after_pump = min(
                SOC_MAX,
                soc_after_pump + (net_wh / BATTERY_CAPACITY_WH) * 100.0,
            )

        soc = soc_after_pump

        if fridge_on:
            critical_on_count += 1
        if pump_on:
            pump_on_count += 1

        records.append(
            {
                "timestamp": ts,
                "pv_w": pv_power_w,
                "fridge_w": f_w,
                "pump_w": p_w,
                "fridge_on": int(fridge_on),
                "pump_on": int(pump_on),
                "soc": soc,
            }
        )

    schedule_df = pd.DataFrame.from_records(records)

    critical_uptime_pct = (
        100.0 * critical_on_count / total_steps if total_steps else 0.0
    )
    pump_uptime_pct = 100.0 * pump_on_count / total_steps if total_steps else 0.0

    stats = IEBAStats(
        critical_uptime_pct=critical_uptime_pct,
        pump_uptime_pct=pump_uptime_pct,
        soc_violations=soc_violations,
    )

    return schedule_df, stats


def simulate_ieba_day(csv_path: str = CSV_PATH) -> tuple[pd.DataFrame, IEBAStats]:
    day_df = load_single_day(csv_path)

    timestamps = day_df["timestamp"].values
    pv_w = day_df["pv_generation"].values
    fridge_w = day_df["fridge_load"].values
    pump_w = day_df["pump_load"].values

    return run_ieba_series(timestamps, pv_w, fridge_w, pump_w, soc_start=SOC_START)


if __name__ == "__main__":
    schedule, stats = simulate_ieba_day()
    print("\n=== IEBA One-Day Simulation Summary ===")
    print(f"Critical (fridge) uptime : {stats.critical_uptime_pct:.2f}%")
    print(f"Pump uptime              : {stats.pump_uptime_pct:.2f}%")
    print(f"SOC violations (<{SOC_MIN:.0f}%): {stats.soc_violations}")
    print("\nLast few rows of schedule:")
    print(schedule.tail())

