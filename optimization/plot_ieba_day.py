import os

import matplotlib.pyplot as plt
import pandas as pd

from ieba import SOC_MIN, simulate_ieba_day


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def plot_ieba_day():
    schedule, stats = simulate_ieba_day()

    schedule["timestamp"] = pd.to_datetime(schedule["timestamp"])

    ts = schedule["timestamp"]

    # Plot SOC profile
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(ts, schedule["soc"], label="Battery SOC (%)")
    ax.axhline(SOC_MIN, color="red", linestyle="--", label=f"SOC min ({SOC_MIN:.0f}%)")
    ax.set_ylabel("SOC (%)")
    ax.set_xlabel("Time")
    ax.set_title("Battery State of Charge Over One Day (IEBA Simulation)")
    ax.legend()
    fig.autofmt_xdate()
    soc_path = os.path.join(BASE_DIR, "ieba_soc_profile.png")
    fig.savefig(soc_path, bbox_inches="tight")
    plt.close(fig)

    # Plot load status (fridge/pump on/off)
    fig2, ax2 = plt.subplots(figsize=(10, 3))
    ax2.step(ts, schedule["fridge_on"], where="post", label="Fridge (critical)")
    ax2.step(ts, schedule["pump_on"], where="post", label="Pump (shed-able)")
    ax2.set_ylim(-0.2, 1.2)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["OFF", "ON"])
    ax2.set_xlabel("Time")
    ax2.set_title("Appliance Status Over One Day (IEBA Decisions)")
    ax2.legend()
    fig2.autofmt_xdate()
    loads_path = os.path.join(BASE_DIR, "ieba_load_status.png")
    fig2.savefig(loads_path, bbox_inches="tight")
    plt.close(fig2)

    print("📈 Saved IEBA plots:")
    print(f" - SOC profile    : {soc_path}")
    print(f" - Load statuses  : {loads_path}")
    print(
        f"\nSummary: critical uptime={stats.critical_uptime_pct:.2f}%, "
        f"pump uptime={stats.pump_uptime_pct:.2f}%, "
        f"SOC violations={stats.soc_violations}"
    )


if __name__ == "__main__":
    plot_ieba_day()

