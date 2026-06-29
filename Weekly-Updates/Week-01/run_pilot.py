"""
run_pilot.py  ─  GreenAeroTest Prototype  ─  v1.0
==================================================
Reads scenarios.csv, runs each scenario 3 times through FlightGear
via the PowerShell runner, samples CPU usage with psutil, computes
energy / carbon metrics, and writes every result row immediately to
dataset/simulation_energy_dataset.csv.

Energy model (prototype):
    avg_power_watts = (avg_cpu_percent / 100) * 100 + 15
    energy_wh       = avg_power_watts * (runtime_sec / 3600)
    energy_joules   = energy_wh * 3600
    carbon_gco2     = (energy_wh / 1000) * 400      # 400 g CO₂ / kWh

Usage:
    python run_pilot.py
"""

import csv
import os
import subprocess
import sys
import time
from datetime import datetime

import pandas as pd
import psutil

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
SCENARIOS_CSV       = "scenarios.csv"
DATASET_CSV         = os.path.join("dataset", "simulation_energy_dataset.csv")
PS_SCRIPT           = os.path.join("scripts", "run_one_scenario.ps1")
OUTPUTS_DIR         = "outputs"
REPETITIONS         = 3
CPU_SAMPLE_INTERVAL = 0.5          # seconds between psutil CPU samples
CARBON_INTENSITY    = 400          # g CO₂ per kWh
MEASUREMENT_SOURCE  = "cpu_based_estimate_for_pilot"

# CSV column order (fixed — every row must match this)
FIELDNAMES = [
    "test_id",
    "scenario_name",
    "scenario_file",
    "run_no",
    "mandatory_flag",
    "assurance_score",
    "start_time",
    "end_time",
    "runtime_sec",
    "avg_cpu_percent",
    "avg_power_watts",
    "energy_wh",
    "energy_joules",
    "carbon_intensity_g_per_kwh",
    "carbon_gco2",
    "output_csv",
    "return_code",
    "result",
    "measurement_source",
]


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def ensure_dirs():
    """Create output directories if they don't exist yet."""
    os.makedirs("dataset", exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)


def init_csv(path: str):
    """Write the CSV header if the file does not already exist."""
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
        print(f"[INIT] Created dataset file: {path}")


def append_row(path: str, row: dict):
    """Append a single result dict to the CSV immediately after each run."""
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)


def compute_energy(avg_cpu_pct: float, runtime_sec: float) -> dict:
    """
    Apply the prototype energy model and return a dict of all derived metrics.

        avg_power_watts = (avg_cpu_percent / 100) * 100 + 15
        energy_wh       = avg_power_watts * (runtime_sec / 3600)
        energy_joules   = energy_wh * 3600
        carbon_gco2     = (energy_wh / 1000) * 400
    """
    avg_power_watts = (avg_cpu_pct / 100.0) * 100.0 + 15.0
    energy_wh       = avg_power_watts * (runtime_sec / 3600.0)
    energy_joules   = energy_wh * 3600.0
    carbon_gco2     = (energy_wh / 1000.0) * CARBON_INTENSITY
    return {
        "avg_power_watts"           : round(avg_power_watts, 4),
        "energy_wh"                 : round(energy_wh, 6),
        "energy_joules"             : round(energy_joules, 4),
        "carbon_intensity_g_per_kwh": CARBON_INTENSITY,
        "carbon_gco2"               : round(carbon_gco2, 6),
    }


def kill_tree(pid: int):
    """Kill a process and all its children (handles FlightGear sub-processes)."""
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        print(f"  [KILL] Terminated process tree for PID {pid}")
    except psutil.NoSuchProcess:
        pass


def classify_result(return_code, timed_out: bool) -> str:
    """Map (return_code, timed_out) to a human-readable result label."""
    if timed_out:
        return "timeout"
    if return_code is None or return_code == -1:
        return "crash"
    if return_code == 99:
        return "incomplete"   # fgfs.exe not found
    if return_code == 0:
        return "pass"
    return "fail"


# ──────────────────────────────────────────────────────────────────────────────
# CORE RUN FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def run_one(scenario: dict, run_no: int) -> dict:
    """
    Execute a single scenario repetition.

    Launches scripts/run_one_scenario.ps1 via subprocess, polls psutil for CPU
    samples until the process exits or the timeout is reached, then assembles
    and returns a fully populated result row dict.
    """
    test_id       = scenario["test_id"]
    scenario_name = scenario["scenario_name"]
    scenario_file = scenario["scenario_file"]
    mandatory     = int(scenario["mandatory_flag"])
    assurance     = float(scenario["assurance_score"])
    timeout_sec   = float(scenario["timeout_sec"])
    output_csv    = os.path.join(OUTPUTS_DIR, f"{test_id}_run{run_no}.csv")

    # Build the PowerShell command
    cmd = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", PS_SCRIPT,
        "-ScenarioFile", scenario_file,
        "-OutputCsv", output_csv,
    ]

    print(f"\n{'─'*60}")
    print(f"  {test_id}  |  {scenario_name}  |  rep {run_no}/{REPETITIONS}")
    print(f"  timeout={timeout_sec}s  mandatory={bool(mandatory)}  assurance={assurance}")
    print(f"{'─'*60}")

    start_dt  = datetime.now()
    t_start   = time.monotonic()
    cpu_samples: list[float] = []
    timed_out = False
    proc      = None

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        # powershell.exe not available (Linux / macOS CI environment)
        print("  [WARN] powershell.exe not found — recording as 'incomplete'.")
        end_dt    = datetime.now()
        runtime   = time.monotonic() - t_start
        energy    = compute_energy(0.0, runtime)
        return _assemble_row(
            test_id, scenario_name, scenario_file, run_no,
            mandatory, assurance, start_dt, end_dt, runtime,
            0.0, energy, output_csv, -1, "incomplete",
        )

    # ── CPU sampling loop ────────────────────────────────────────────────────
    # psutil.cpu_percent(interval=None) returns usage since the last call.
    # Prime it with a short blocking call so the first sample is meaningful.
    psutil.cpu_percent(interval=None)

    while True:
        elapsed = time.monotonic() - t_start
        ret     = proc.poll()

        if ret is not None:
            print(f"  [EXIT] FlightGear exited after {elapsed:.1f}s (code {ret})")
            break

        if elapsed >= timeout_sec:
            timed_out = True
            print(f"  [TIMEOUT] {timeout_sec}s exceeded — killing process tree...")
            kill_tree(proc.pid)
            proc.wait()
            break

        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_samples.append(cpu_pct)
        time.sleep(CPU_SAMPLE_INTERVAL)

    # ── Collect final sample and stderr/stdout ───────────────────────────────
    try:
        stdout, stderr = proc.communicate(timeout=5)
        if stdout.strip():
            print(f"  [PS] {stdout.strip()[:300]}")
        if stderr.strip():
            print(f"  [PS ERR] {stderr.strip()[:300]}")
    except Exception:
        pass

    end_dt      = datetime.now()
    runtime     = time.monotonic() - t_start
    return_code = proc.returncode if proc.returncode is not None else -1
    avg_cpu     = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    result      = classify_result(return_code, timed_out)
    energy      = compute_energy(avg_cpu, runtime)

    print(
        f"  [DONE] result={result}  cpu={avg_cpu:.1f}%  "
        f"power={energy['avg_power_watts']:.1f}W  "
        f"energy={energy['energy_wh']:.5f}Wh  "
        f"CO₂={energy['carbon_gco2']:.5f}g"
    )

    return _assemble_row(
        test_id, scenario_name, scenario_file, run_no,
        mandatory, assurance, start_dt, end_dt, runtime,
        avg_cpu, energy, output_csv, return_code, result,
    )


def _assemble_row(
    test_id, scenario_name, scenario_file, run_no,
    mandatory, assurance, start_dt, end_dt, runtime,
    avg_cpu, energy: dict, output_csv, return_code, result,
) -> dict:
    """Pack every field into a flat dict that matches FIELDNAMES."""
    return {
        "test_id"                   : test_id,
        "scenario_name"             : scenario_name,
        "scenario_file"             : scenario_file,
        "run_no"                    : run_no,
        "mandatory_flag"            : mandatory,
        "assurance_score"           : assurance,
        "start_time"                : start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time"                  : end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_sec"               : round(runtime, 3),
        "avg_cpu_percent"           : round(avg_cpu, 2),
        "avg_power_watts"           : energy["avg_power_watts"],
        "energy_wh"                 : energy["energy_wh"],
        "energy_joules"             : energy["energy_joules"],
        "carbon_intensity_g_per_kwh": energy["carbon_intensity_g_per_kwh"],
        "carbon_gco2"               : energy["carbon_gco2"],
        "output_csv"                : output_csv,
        "return_code"               : return_code,
        "result"                    : result,
        "measurement_source"        : MEASUREMENT_SOURCE,
    }


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  GreenAeroTest  ─  run_pilot.py  ─  v1.0")
    print("=" * 60)

    if not os.path.exists(SCENARIOS_CSV):
        sys.exit(f"[ERROR] {SCENARIOS_CSV} not found. Run from the greenaerotest_pilot/ folder.")

    scenarios_df = pd.read_csv(SCENARIOS_CSV)
    print(f"\n[LOAD] {len(scenarios_df)} scenarios loaded from {SCENARIOS_CSV}:")
    print(scenarios_df.to_string(index=False))
    print()

    ensure_dirs()
    init_csv(DATASET_CSV)

    total = len(scenarios_df) * REPETITIONS
    done  = 0

    for _, scenario in scenarios_df.iterrows():
        for rep in range(1, REPETITIONS + 1):
            done += 1
            print(f"\n[{done}/{total}]  Starting {scenario['test_id']}  rep {rep} ...")
            row = run_one(scenario.to_dict(), rep)
            append_row(DATASET_CSV, row)
            print(f"  [SAVED] Row written to {DATASET_CSV}")

    # ── Final summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ALL RUNS COMPLETE")
    print("=" * 60)
    df = pd.read_csv(DATASET_CSV)
    summary = (
        df.groupby("test_id")
        .agg(
            scenario_name  =("scenario_name",   "first"),
            total_runs     =("run_no",           "count"),
            passes         =("result",           lambda x: (x == "pass").sum()),
            timeouts       =("result",           lambda x: (x == "timeout").sum()),
            avg_runtime_sec=("runtime_sec",      "mean"),
            avg_energy_wh  =("energy_wh",        "mean"),
            avg_cpu_pct    =("avg_cpu_percent",  "mean"),
        )
        .reset_index()
    )
    print(summary.to_string(index=False))
    print(f"\n[DONE] Dataset: {DATASET_CSV}")
    print("[NEXT] Run:  python prioritize.py")


if __name__ == "__main__":
    main()
