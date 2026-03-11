import math
import random
from datetime import datetime

class SimulatedSensor:
    def __init__(self):
        self.soc = 75.2  # Initial State-of-Charge as per your Object Diagram [cite: 374]

    def read_pv(self):
        # Simulates solar curve: Peak at noon, 0 at night
        hour = datetime.now().hour
        pv_power = max(0, math.sin((hour - 6) / 12 * math.pi)) * 2450.5
        return round(pv_power + random.uniform(-20, 20), 2)

    def read_battery_soc(self):
        return round(self.soc, 2)

    def read_load_demand(self):
        # Simulates user consumption patterns [cite: 190]
        fridge = 1500 if 6 <= datetime.now().hour <= 22 else 200
        pump = 800 if 10 <= datetime.now().hour <= 12 else 0
        return {"critical_fridge": fridge, "essential_pump": pump}

    def update_soc(self, pv_power, loads, duration_seconds=60, capacity_kwh=10):
        """
        Update battery SOC based on PV production and loads.
        - pv_power: float (watts)
        - loads: dict with keys 'critical_fridge' and 'essential_pump' (watts)
        - duration_seconds: time window to simulate (seconds)
        - capacity_kwh: battery capacity in kWh (used to convert energy -> SOC)
        """
        loads_total = loads.get("critical_fridge", 0) + loads.get("essential_pump", 0)
        net = pv_power - loads_total  # watts (positive -> charging, negative -> discharging)
        energy_Wh = net * (duration_seconds / 3600.0)
        capacity_Wh = capacity_kwh * 1000.0
        # percent SOC change = energy (Wh) / capacity (Wh) * 100
        percent_change = (energy_Wh / capacity_Wh) * 100.0
        # small self-discharge (approx 0.01% per hour)
        self_discharge = -0.01 * (duration_seconds / 3600.0)
        self.soc += percent_change + self_discharge
        # clamp
        if self.soc > 100.0:
            self.soc = 100.0
        if self.soc < 0.0:
            self.soc = 0.0