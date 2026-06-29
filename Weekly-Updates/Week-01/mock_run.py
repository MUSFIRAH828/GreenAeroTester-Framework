import csv
import os
import random
import time

print("--- STARTING MOCK RUN PIPELINE (NO LIBRARIES REQUIRED) ---")

# Ensure dataset folder exists
if not os.path.exists("dataset"):
    os.makedirs("dataset")
    print("[+] Created 'dataset' folder successfully.")

# 1. Create a dummy simulation_energy_dataset.csv
dataset_path = "dataset/simulation_energy_dataset.csv"
fieldnames = ["test_id", "scenario_name", "run_no", "mandatory_flag", "assurance_score", "runtime_sec", "avg_cpu_percent", "energy_wh", "carbon_gco2", "result"]

scenarios = [
    {"id": "T01", "name": "normal_takeoff", "mandatory": 0, "assurance": 6},
    {"id": "T02", "name": "normal_cruise", "mandatory": 0, "assurance": 4},
    {"id": "T03", "name": "landing", "mandatory": 1, "assurance": 10},
    {"id": "T04", "name": "wind_disturbance", "mandatory": 0, "assurance": 7},
    {"id": "T05", "name": "failure_case", "mandatory": 1, "assurance": 9}
]

print("[*] Simulating FlightGear Runs (15 total runs)... Please wait.")
with open(dataset_path, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    
    for sc in scenarios:
        for run in range(1, 4):
            time.sleep(0.1) # Chota sa pause fake simulation feel dene ke liye
            runtime = random.randint(55, 65)
            cpu = random.uniform(20.0, 45.0)
            power = (cpu / 100.0) * 100 + 15
            energy = power * (runtime / 3600.0)
            carbon = (energy / 1000.0) * 400
            
            writer.writerow({
                "test_id": sc["id"],
                "scenario_name": sc["name"],
                "run_no": run,
                "mandatory_flag": sc["mandatory"],
                "assurance_score": sc["assurance"],
                "runtime_sec": runtime,
                "avg_cpu_percent": round(cpu, 2),
                "energy_wh": round(energy, 4),
                "carbon_gco2": round(carbon, 4),
                "result": "pass"
            })
print(f"[+] Successfully generated: {dataset_path}")

# 2. Create a dummy priority_order.csv based on basic sorting rules
priority_path = "dataset/priority_order.csv"
print("[*] Prioritizing Scenarios (Mandatory First, then by Energy efficiency)...")

# Simple logic: put mandatory ones first, then optional ones
mandatory_tests = [sc for sc in scenarios if sc["mandatory"] == 1]
optional_tests = [sc for sc in scenarios if sc["mandatory"] == 0]

final_order = mandatory_tests + optional_tests

with open(priority_path, mode="w", newline="", encoding="utf-8") as f:
    p_writer = csv.writer(f)
    p_writer.writerow(["priority_rank", "test_id", "scenario_name", "mandatory_flag", "assurance_score", "selection_reason"])
    
    rank = 1
    for sc in final_order:
        reason = "Mandatory Test Case (High Priority)" if sc["mandatory"] == 1 else "Optional Test Case (Sorted by Utility)"
        p_writer.writerow([rank, sc["id"], sc["name"], sc["mandatory"], sc["assurance"], reason])
        rank += 1

print(f"[+] Successfully generated: {priority_path}")
print("--- MOCK RUN COMPLETE! ALL DATASET FILES CREATED SUCCESSFULLY ---")