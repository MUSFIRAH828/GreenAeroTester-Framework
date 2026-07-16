"""
run_pilot.py  ─  GreenAeroTest Prototype  ─  v1.1
==================================================
Reads scenarios.csv, runs each scenario 3 times through FlightGear
via the PowerShell runner, samples CPU usage with psutil, computes
energy / carbon metrics, and writes every result row immediately to
dataset/simulation_energy_dataset.csv.

Energy model (prototype):
    avg_power_watts = (avg_cpu_percent / 100) * 100 + 15
    energy_wh       = avg_power_watts * (runtime_sec / 3600)
    energy_joules   = energy_wh * 3600
    carbon_gco2     = (energy_wh / 1000) * 400      # 400 g CO2 / kWh

v1.1 changes (fixes for crash/timeout issues):
    - FIX #1 (Garmin196 crash) and FIX #2 (missing scenery path / hang):
      these live in scripts/run_one_scenario.ps1, since that's the script
      that actually builds the fgfs.exe command line. This file now
      resolves a scenery folder on the Python side too (so you get a clear
      warning early, before PowerShell even launches) and passes it down
      to the PS1 script via -SceneryPath.
    - FIX #3 (CodeCarbon hanging on Windows CPU-socket / geolocation
      lookups): start_codecarbon()/stop_codecarbon() now run inside a
      worker thread with a hard timeout, so a hung CodeCarbon call can
      never freeze the whole pilot. We also pass country_iso_code
      explicitly to skip CodeCarbon's default network geolocation call,
      which is the single most common cause of these hangs.

Usage:
    python run_pilot.py
"""

from __future__ import annotations  # lets "str | None" hints work on Python < 3.10

import concurrent.futures
import csv
import os
import subprocess
import sys
import time
from datetime import datetime

import pandas as pd
import psutil

# ──────────────────────────────────────────────────────────────────────────────
# CODECARBON  (real-world energy / CO2 measurement)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from codecarbon import EmissionsTracker
    CODECARBON_AVAILABLE = True
except ImportError:
    CODECARBON_AVAILABLE = False
    print(
        "[WARN] 'codecarbon' package not found. Install it with:\n"
        "       pip install codecarbon\n"
        "       Continuing WITHOUT CodeCarbon energy/CO2 tracking for now."
    )

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
SCENARIOS_CSV       = "scenarios.csv"
DATASET_CSV         = os.path.join("dataset", "simulation_energy_dataset.csv")
PS_SCRIPT            = os.path.join("scripts", "run_one_scenario.ps1")
OUTPUTS_DIR          = "outputs"
REPETITIONS          = 3
CPU_SAMPLE_INTERVAL  = 0.5          # seconds between psutil CPU samples
CARBON_INTENSITY     = 400          # g CO2 per kWh
MEASUREMENT_SOURCE   = "cpu_based_estimate_for_pilot"

# FIX #3: CodeCarbon config.
#
# The reported "socket error" is CodeCarbon's Windows hardware-detection
# path: when it can't read RAPL counters directly, it enumerates CPU/RAM
# info via WMI/PowerShell (Get-CimInstance) to look up a TDP-based power
# estimate, and *that* subprocess call is what hangs on some machines.
# force_cpu_power / force_ram_power make CodeCarbon skip hardware
# detection entirely and just use the wattage you give it — no WMI/
# PowerShell calls, no hang. Adjust these to roughly match the actual
# test machine if you want more realistic cc_energy_kwh figures; they
# don't affect our own avg_power_watts/energy_wh columns, only the cc_*
# ones. force_carbon_intensity_g_co2e_kwh similarly skips CodeCarbon's
# default network geolocation lookup (the other common hang source).
CODECARBON_FORCE_CPU_POWER_W = 45.0
CODECARBON_FORCE_RAM_POWER_W = 6.0
CODECARBON_FORCE_CARBON_INTENSITY = CARBON_INTENSITY  # reuse our 400 g/kWh constant
CODECARBON_START_TIMEOUT_SEC = 12
CODECARBON_STOP_TIMEOUT_SEC  = 12

# FIX #2: optional explicit scenery override. Leave as None to let
# resolve_scenery_path() auto-detect; set a real path here if auto-detect
# doesn't find one on your machine (see the printed warning).
SCENERY_PATH_OVERRIDE = None  # e.g. r"C:\Program Files\FlightGear 2024.1\data\Scenery"

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
    # ── CodeCarbon columns (real hardware-based measurement) ────────────────
    "cc_duration_sec",       # wall-clock time CodeCarbon measured
    "cc_energy_kwh",         # energy consumed, in kWh, measured by CodeCarbon
    "cc_emissions_kgco2",    # CO2 emissions, in kg, measured by CodeCarbon
    "scenery_path",          # which scenery folder was actually used
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
    """
    Write the CSV header if the file does not already exist.

    Defensive schema check: if the file DOES exist but its header doesn't
    match the current FIELDNAMES (e.g. it was created by an older version
    of this script), appending new rows would corrupt it. Instead, we back
    up the old file and start a fresh one with the correct header.
    """
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
        print(f"[INIT] Created dataset file: {path}")
        return

    with open(path, "r", newline="", encoding="utf-8") as f:
        first_line = f.readline().strip()
    existing_header = first_line.split(",") if first_line else []

    if existing_header != FIELDNAMES:
        backup_path = path + ".old_schema_backup.csv"
        i = 1
        while os.path.exists(backup_path):
            backup_path = f"{path}.old_schema_backup_{i}.csv"
            i += 1
        os.rename(path, backup_path)
        print(
            f"[SCHEMA] Existing dataset had an outdated column format.\n"
            f"         Old file backed up to: {backup_path}\n"
            f"         Starting a fresh {path} with the current schema."
        )
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
        print(f"[INIT] Created dataset file: {path}")
    else:
        print(f"[INIT] Existing dataset file has matching schema: {path}")


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


# ──────────────────────────────────────────────────────────────────────────────
# FIX #2 (Python side): scenery path resolution
# ──────────────────────────────────────────────────────────────────────────────
_SCENERY_WARNED = False  # only print the "no scenery found" warning once


def resolve_scenery_path() -> str | None:
    """
    Try to find a real FlightGear scenery folder so we can pass it
    explicitly to run_one_scenario.ps1 via -SceneryPath, which overrides
    whatever stale/broken path is saved in FlightGear's own preferences
    (the root cause of the observed
    '[WARN]:general scenery path not found: .../geenareo/default' error).

    Returns the first existing candidate path, or None if nothing was
    found (in which case the PS1 script will try its own fallback list
    and, failing that, run with --disable-terrasync and no explicit
    scenery override).
    """
    global _SCENERY_WARNED

    candidates = [
        SCENERY_PATH_OVERRIDE,
        os.environ.get("FG_SCENERY"),
        r"C:\Program Files\FlightGear 2024.1\data\Scenery",
        r"C:\FlightGear\data\Scenery",
        os.path.expandvars(r"%USERPROFILE%\FlightGear\Scenery"),
    ]
    for path in candidates:
        if path and os.path.isdir(path):
            return path

    if not _SCENERY_WARNED:
        print(
            "[WARN] Could not auto-detect a valid FlightGear scenery folder "
            "from Python. run_one_scenario.ps1 will try its own fallback "
            "list; if that also fails, set SCENERY_PATH_OVERRIDE at the top "
            "of run_pilot.py or the FG_SCENERY environment variable."
        )
        _SCENERY_WARNED = True
    return None


# ──────────────────────────────────────────────────────────────────────────────
# FIX #3: CodeCarbon with a hard timeout so it can never hang the pilot
# ──────────────────────────────────────────────────────────────────────────────
def start_codecarbon(test_id: str, run_no: int):
    """
    Create and start a CodeCarbon EmissionsTracker for one scenario run.

    Runs inside a worker thread with a hard timeout: if CodeCarbon's
    internal CPU-socket enumeration or geolocation lookup hangs (the
    reported Windows issue), we give up after CODECARBON_START_TIMEOUT_SEC
    and continue the pilot without it, rather than freezing forever.

    Note: Python threads cannot be forcibly killed, so a truly stuck call
    may keep running in the background after we time out on it — this is
    a limitation of wrapping blocking I/O this way, but it guarantees the
    *pilot* keeps making progress, which is what matters for the dataset.
    """
    if not CODECARBON_AVAILABLE:
        return None

    def _start():
        tracker = EmissionsTracker(
            project_name=f"GreenAeroTest_{test_id}_run{run_no}",
            save_to_file=False,             # we save our own dataset CSV instead
            log_level="error",              # keep console output clean
            tracking_mode="process",        # avoid full machine-wide socket enumeration
            force_cpu_power=CODECARBON_FORCE_CPU_POWER_W,   # skip WMI/PowerShell CPU query (the hang)
            force_ram_power=CODECARBON_FORCE_RAM_POWER_W,   # skip RAM hardware detection too
            force_carbon_intensity_g_co2e_kwh=CODECARBON_FORCE_CARBON_INTENSITY,  # skip geolocation call
            allow_multiple_runs=True,       # we intentionally start/stop a tracker per run
        )
        tracker.start()
        return tracker

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_start)
            return future.result(timeout=CODECARBON_START_TIMEOUT_SEC)
    except concurrent.futures.TimeoutError:
        print(
            f"  [WARN] CodeCarbon start() timed out after "
            f"{CODECARBON_START_TIMEOUT_SEC}s (likely a CPU-socket or "
            f"geolocation lookup hang) — continuing without it for this run."
        )
        return None
    except Exception as e:
        print(f"  [WARN] CodeCarbon failed to start ({e}). Continuing without it.")
        return None


def stop_codecarbon(tracker) -> dict:
    """
    Stop the tracker (if any) and pull out the three numbers we care about,
    again bounded by a hard timeout so a hung stop() can't block the pilot.

    Always returns a dict with all three keys, defaulting to 0.0 so the CSV
    row is always complete even if tracking wasn't available for this run.
    """
    cc_result = {"cc_duration_sec": 0.0, "cc_energy_kwh": 0.0, "cc_emissions_kgco2": 0.0}
    if tracker is None:
        return cc_result

    def _stop():
        tracker.stop()
        data = tracker.final_emissions_data
        return {
            "cc_duration_sec"   : round(float(data.duration), 4),
            "cc_energy_kwh"     : round(float(data.energy_consumed), 8),
            "cc_emissions_kgco2": round(float(data.emissions), 8),
        }

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_stop)
            return future.result(timeout=CODECARBON_STOP_TIMEOUT_SEC)
    except concurrent.futures.TimeoutError:
        print(
            f"  [WARN] CodeCarbon stop() timed out after "
            f"{CODECARBON_STOP_TIMEOUT_SEC}s — using zeros for cc_* columns "
            f"on this run."
        )
        return cc_result
    except Exception as e:
        print(f"  [WARN] CodeCarbon failed to stop cleanly ({e}). Using zeros for this run.")
        return cc_result


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

    # FIX #2: resolve scenery on the Python side and pass it down explicitly.
    scenery_path = resolve_scenery_path()

    # Build the PowerShell command
    cmd = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", PS_SCRIPT,
        "-ScenarioFile", scenario_file,
        "-OutputCsv", output_csv,
    ]
    if scenery_path:
        cmd += ["-SceneryPath", scenery_path]

    print(f"\n{'-'*60}")
    print(f"  {test_id}  |  {scenario_name}  |  rep {run_no}/{REPETITIONS}")
    print(f"  timeout={timeout_sec}s  mandatory={bool(mandatory)}  assurance={assurance}")
    if scenery_path:
        print(f"  scenery={scenery_path}")
    print(f"{'-'*60}")

    start_dt  = datetime.now()
    t_start   = time.monotonic()
    cpu_samples: list = []
    timed_out = False
    proc      = None

    # CodeCarbon: start() right before the code we want to measure.
    cc_tracker = start_codecarbon(test_id, run_no)

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
        cc_metrics = stop_codecarbon(cc_tracker)   # stop() even on early exit
        end_dt    = datetime.now()
        runtime   = time.monotonic() - t_start
        energy    = compute_energy(0.0, runtime)
        return _assemble_row(
            test_id, scenario_name, scenario_file, run_no,
            mandatory, assurance, start_dt, end_dt, runtime,
            0.0, energy, cc_metrics, scenery_path, output_csv, -1, "incomplete",
        )

    # ── CPU sampling loop ────────────────────────────────────────────────────
    psutil.cpu_percent(interval=None)  # prime the counter

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

    # ── Collect final stdout/stderr ──────────────────────────────────────────
    try:
        stdout, stderr = proc.communicate(timeout=5)
        if stdout.strip():
            print(f"  [PS] {stdout.strip()[:300]}")
        if stderr.strip():
            print(f"  [PS ERR] {stderr.strip()[:300]}")
    except Exception:
        pass

    # CodeCarbon: stop() right after the measured code finishes.
    cc_metrics = stop_codecarbon(cc_tracker)

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
        f"CO2={energy['carbon_gco2']:.5f}g  |  "
        f"CodeCarbon: energy={cc_metrics['cc_energy_kwh']:.8f}kWh  "
        f"CO2={cc_metrics['cc_emissions_kgco2']:.8f}kg  "
        f"time={cc_metrics['cc_duration_sec']:.2f}s"
    )

    return _assemble_row(
        test_id, scenario_name, scenario_file, run_no,
        mandatory, assurance, start_dt, end_dt, runtime,
        avg_cpu, energy, cc_metrics, scenery_path, output_csv, return_code, result,
    )


def _assemble_row(
    test_id, scenario_name, scenario_file, run_no,
    mandatory, assurance, start_dt, end_dt, runtime,
    avg_cpu, energy: dict, cc_metrics: dict, scenery_path, output_csv, return_code, result,
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
        "cc_duration_sec"           : cc_metrics["cc_duration_sec"],
        "cc_energy_kwh"             : cc_metrics["cc_energy_kwh"],
        "cc_emissions_kgco2"        : cc_metrics["cc_emissions_kgco2"],
        "scenery_path"              : scenery_path or "",
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
    print("  GreenAeroTest  -  run_pilot.py  -  v1.1")
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
            scenario_name        =("scenario_name",   "first"),
            total_runs           =("run_no",           "count"),
            passes               =("result",           lambda x: (x == "pass").sum()),
            timeouts             =("result",           lambda x: (x == "timeout").sum()),
            crashes              =("result",           lambda x: (x == "crash").sum()),
            avg_runtime_sec      =("runtime_sec",      "mean"),
            avg_energy_wh        =("energy_wh",        "mean"),
            avg_cpu_pct          =("avg_cpu_percent",  "mean"),
            avg_cc_energy_kwh    =("cc_energy_kwh",      "mean"),
            avg_cc_emissions_kg  =("cc_emissions_kgco2",  "mean"),
        )
        .reset_index()
    )
    print(summary.to_string(index=False))
    print(f"\n[DONE] Dataset: {DATASET_CSV}")
    print("[NEXT] Run:  python prioritize.py")


if __name__ == "__main__":
    main()