from sensors.simulated_sensor import SimulatedSensor

sensor = SimulatedSensor()

print("Starting quick SOC simulation test (5 iterations, 60s each)...")
for i in range(5):
    pv = sensor.read_pv()
    loads = sensor.read_load_demand()
    before = sensor.read_battery_soc()
    # apply same shedding logic as ingestion_service
    if before < 40.0:
        loads['essential_pump'] = 0
    print(f"Iter {i}: PV={pv}W, loads={loads}, SOC_before={before}%")
    sensor.update_soc(pv, loads, duration_seconds=60)
    after = sensor.read_battery_soc()
    print(f"Iter {i}: SOC_after={after}%\n")

print("Test complete.")
