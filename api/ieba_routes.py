import os
import sys

from flask import Blueprint, jsonify

# Ensure project root is on sys.path so we can import optimization.*
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from optimization.ieba import (
    load_single_day,
    run_ieba_series,
    simulate_ieba_day,
    SOC_START,
)
from optimization.ieba_with_pv_forecast import compare_perfect_vs_forecast_ieba
from optimization.load_from_appliances import build_load_series_from_appliances

from database import load_appliances


ieba_bp = Blueprint("ieba", __name__, url_prefix="/ieba")


@ieba_bp.route("/perfect")
def ieba_perfect():
    schedule, stats = simulate_ieba_day()
    return jsonify(
        {
            "mode": "perfect_information",
            "critical_uptime_pct": stats.critical_uptime_pct,
            "pump_uptime_pct": stats.pump_uptime_pct,
            "soc_violations": stats.soc_violations,
            "timesteps": len(schedule),
        }
    )


@ieba_bp.route("/forecast")
def ieba_forecast():
    (perfect_schedule, perfect_stats), (forecast_schedule, forecast_stats) = (
        compare_perfect_vs_forecast_ieba()
    )

    return jsonify(
        {
            "perfect": {
                "critical_uptime_pct": perfect_stats.critical_uptime_pct,
                "pump_uptime_pct": perfect_stats.pump_uptime_pct,
                "soc_violations": perfect_stats.soc_violations,
                "timesteps": len(perfect_schedule),
            },
            "forecast": {
                "critical_uptime_pct": forecast_stats.critical_uptime_pct,
                "pump_uptime_pct": forecast_stats.pump_uptime_pct,
                "soc_violations": forecast_stats.soc_violations,
                "timesteps": len(forecast_schedule),
            },
        }
    )


@ieba_bp.route("/custom")
def ieba_custom():
    """Run IEBA with load profile from registered appliances (UCLPI priorities)."""
    day_df = load_single_day()
    timestamps = day_df["timestamp"].values
    pv_w = day_df["pv_generation"].values

    appliances = load_appliances()
    if appliances:
        appliance_dicts = [a.to_dict() for a in appliances]
        critical_w, shedable_w = build_load_series_from_appliances(
            appliance_dicts, day_df["timestamp"]
        )
    else:
        critical_w = day_df["fridge_load"].values
        shedable_w = day_df["pump_load"].values

    schedule, stats = run_ieba_series(
        timestamps, pv_w, critical_w, shedable_w, soc_start=SOC_START
    )
    return jsonify(
        {
            "mode": "custom_appliances",
            "critical_uptime_pct": stats.critical_uptime_pct,
            "pump_uptime_pct": stats.pump_uptime_pct,
            "soc_violations": stats.soc_violations,
            "timesteps": len(schedule),
            "appliance_count": len(appliances),
        }
    )

