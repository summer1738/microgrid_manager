"""
In-memory store for sensor/hardware data.
Virtual hardware (simulator) or real IoT devices POST to /api/hardware/ingest;
the rest of the system reads via get_sensor_state() or GET /api/sensors.
Same contract real hardware would use.
"""
import threading
from datetime import datetime
from typing import Any, Dict, Optional

# Single source of truth for latest sensor readings
_state: Dict[str, Any] = {}
_lock = threading.Lock()

# Defaults when no hardware has reported yet (for backward compatibility)
DEFAULTS = {
    "battery_soc": 75.0,
    "battery_voltage_v": 48.0,
    "battery_current_a": 0.0,
    "battery_temperature_c": 25.0,
    "pv_power_w": 0.0,
    "pv_irradiance_wm2": 0.0,
    "pv_temperature_c": 25.0,
    "load_total_w": 0.0,
    "load_critical_w": 0.0,
    "load_shedable_w": 0.0,
    "ambient_temperature_c": 25.0,
    "household_loads_w": {},  # e.g. {"House A": 450, "House B": 320}
    "grid_connected": False,
    "grid_import_w": 0.0,
    "source": None,  # "simulator" | "hardware" | None
    "updated_at": None,  # ISO timestamp
    "shedable_curtailed": False,  # computed: True when shedable load should be off
}

# Shed logic: same thresholds as IEBA
SOC_MIN = 40.0  # do not discharge below this
SOC_SHED_HYSTERESIS = 50.0  # below this, shed if PV cannot cover critical load


def _compute_shed_decision(state: Dict[str, Any]) -> bool:
    """Decide whether to curtail shedable load based on SOC and power balance."""
    soc = state.get("battery_soc")
    pv_w = state.get("pv_power_w") or 0.0
    critical_w = state.get("load_critical_w") or 0.0
    if soc is None:
        return False
    if soc <= SOC_MIN:
        return True  # at floor, must shed
    if soc < SOC_SHED_HYSTERESIS and (pv_w - critical_w) < -10:
        return True  # PV cannot cover critical; preserve battery
    return False


def ingest(payload: Dict[str, Any], source: str = "simulator") -> None:
    """Merge incoming sensor payload into state. Thread-safe. Accepts any sensor keys."""
    with _lock:
        _state["source"] = source
        _state["updated_at"] = datetime.utcnow().isoformat() + "Z"
        for key, value in payload.items():
            if key in ("source", "updated_at"):
                continue
            if value is None:
                continue
            _state[key] = value
        if "household_loads" in payload and "household_loads_w" not in payload:
            _state["household_loads_w"] = payload["household_loads"]


def get_sensor_state() -> Dict[str, Any]:
    """Return current sensor state (merged with defaults). Thread-safe. Includes shed decision."""
    with _lock:
        out = dict(DEFAULTS)
        out.update(_state)
        out["shedable_curtailed"] = _compute_shed_decision(out)
        return out


def is_live() -> bool:
    """True if we have received at least one ingest (simulator or hardware)."""
    with _lock:
        return _state.get("updated_at") is not None
