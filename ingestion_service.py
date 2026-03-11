import time
import csv
from datetime import datetime
from sensors.simulated_sensor import SimulatedSensor

sensor = SimulatedSensor()

# Prepare the CSV to store multivariate time-series data 
with open("data/raw/energy_log.csv", "a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "pv_generation", "battery_soc", "fridge_load", "pump_load", "status"])

    print("Starting Data Collection... Press Ctrl+C to stop.")
    while True:
        pv = sensor.read_pv()
        soc = sensor.read_battery_soc()
        loads = sensor.read_load_demand()
        
        # If SOC is low, we turn off the pump (shedding)
        if soc < 40.0:
            loads['essential_pump'] = 0
            status = "SHEDDING ACTIVE"
        else:
            status = "NORMAL"
        
        # After applying shedding, update battery SOC for this interval
        sensor.update_soc(pv, loads, duration_seconds=60)
        soc = sensor.read_battery_soc()

        # Log the decision to your CSV
        writer.writerow([datetime.now(), pv, soc, loads['critical_fridge'], loads['essential_pump'], status])
        print(f"[{status}] Logged: PV={pv}W, SOC={soc}%")
            
        time.sleep(60) # Log data every 60 seconds [cite: 84]