"""
Build critical and shed-able load time series from registered appliances.
Used by IEBA to apply UCLPI priorities: P1 = critical (always serve), P2/P3 = shed-able.
Also provides per-appliance and per-household series for consumption visualisation.
"""
from typing import List, Dict, Any

import numpy as np
import pandas as pd


def _shedable_mask(timestamps, shedable_hours: tuple) -> np.ndarray:
    """Boolean mask True where shedable load is on (by hour)."""
    if isinstance(timestamps, pd.DatetimeIndex):
        hours = timestamps.hour.values
    elif isinstance(timestamps, pd.Series) and hasattr(timestamps.dt, "hour"):
        hours = timestamps.dt.hour.values
    elif hasattr(timestamps, "hour"):
        hours = timestamps.hour
    else:
        hours = np.array([pd.Timestamp(t).hour for t in timestamps], dtype=int)
    start_h, end_h = shedable_hours
    return (hours >= start_h) & (hours <= end_h)


def build_load_series_from_appliances(
    appliances: List[dict],
    timestamps: np.ndarray,
    shedable_hours: tuple = (10, 12),
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build per-timestep critical_w and shedable_w from appliance list.

    appliances: list of dicts with "power_w" and "priority" (1=critical, 2=essential, 3=non-essential).
    timestamps: array of datetime-like (must support .hour or be pandas Series).
    shedable_hours: (start_hour, end_hour) when shed-able load is assumed on (simplified schedule).

    Returns:
        critical_w: shape (n,) — total power of priority-1 appliances (constant).
        shedable_w: shape (n,) — total power of priority-2 and -3, on only during shedable_hours.
    """
    # Exclude appliances the user has manually shed
    active = [a for a in appliances if not a.get("manually_shed", False)]
    n = len(timestamps)
    critical_total = sum(
        float(a.get("power_w", 0))
        for a in active
        if int(a.get("priority", 0)) == 1
    )
    shedable_total = sum(
        float(a.get("power_w", 0))
        for a in active
        if int(a.get("priority", 0)) in (2, 3)
    )

    critical_w = np.full(n, critical_total, dtype=float)
    shedable_w = np.zeros(n, dtype=float)

    if shedable_total > 0:
        mask = _shedable_mask(timestamps, shedable_hours)
        shedable_w[mask] = shedable_total

    return critical_w, shedable_w


def build_appliance_series_from_appliances(
    appliances: List[dict],
    timestamps: np.ndarray,
    shedable_hours: tuple = (10, 12),
) -> List[Dict[str, Any]]:
    """
    Build per-appliance power (W) time series for visualisation.
    Returns list of dicts: id, name, priority, power_w, household (optional), series (list of float).
    """
    active = [a for a in appliances if not a.get("manually_shed", False)]
    n = len(timestamps)
    mask = _shedable_mask(timestamps, shedable_hours)
    result = []
    for a in active:
        power_w = float(a.get("power_w", 0))
        priority = int(a.get("priority", 0))
        if priority == 1:
            series = np.full(n, power_w, dtype=float).tolist()
        elif priority in (2, 3):
            series = (np.where(mask, power_w, 0.0)).tolist()
        else:
            series = [0.0] * n
        result.append({
            "id": a.get("id", ""),
            "name": a.get("name", "Unknown"),
            "priority": priority,
            "power_w": power_w,
            "household": a.get("household") or None,
            "series": series,
        })
    return result


def aggregate_consumption_by_household(
    appliance_series: List[Dict[str, Any]],
    timestamps: np.ndarray,
) -> List[Dict[str, Any]]:
    """
    Aggregate per-appliance series by household for community view.
    Returns list of dicts: household (name), total_series (list), appliances (list of names).
    Appliances without household go under "Site" or "Unassigned".
    """
    from collections import defaultdict
    n = len(timestamps)
    by_household: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"series": np.zeros(n), "appliances": []})
    for a in appliance_series:
        h = (a.get("household") or "").strip() or "Site"
        by_household[h]["series"] += np.array(a["series"], dtype=float)
        by_household[h]["appliances"].append(a["name"])
    result = []
    for name, data in sorted(by_household.items()):
        result.append({
            "household": name,
            "total_series": data["series"].tolist(),
            "appliances": data["appliances"],
        })
    return result
