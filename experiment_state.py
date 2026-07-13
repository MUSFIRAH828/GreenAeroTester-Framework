# ============================================================================
# utils/experiment_state.py
# ============================================================================
# Session-state-backed workflow manager for the Home page's Experiment
# Control Center. Keeps ALL experiment-run state in one place so 1_Home.py
# stays a thin view layer: it reads/writes through these functions instead of
# poking st.session_state directly everywhere.
#
# Workflow (per the redesign spec):
#   setup -> running -> results
#
#   setup    : Experiment Info + Upload Center + Experiment Summary + Run
#              Controls. Nothing has started yet.
#   running  : Live Monitoring (progress, current scenario/run, elapsed/
#              remaining time, CPU/power/energy/CO2, scrolling log).
#   results  : the existing dashboard (unchanged), fed by the active
#              ExperimentDataProvider.
# ============================================================================

from __future__ import annotations

import time
from typing import Optional

import streamlit as st

from utils.data_provider import get_active_provider, DEMO_RUN_DURATION_SECONDS, MEASUREMENT_SOURCES

# Required vs optional uploads (per the Upload Center spec + SRS §7 repo
# structure: scenarios/, scripts/run_scenario.ps1, configs/, outputs/, data/).
REQUIRED_UPLOADS = ["scenario_csv", "flightgear_exe", "python_runner", "config_file",
                    "output_folder", "dataset_folder"]
OPTIONAL_UPLOADS = ["scenario_folder", "aircraft_model"]
ALL_UPLOADS = REQUIRED_UPLOADS + OPTIONAL_UPLOADS

UPLOAD_LABELS = {
    "scenario_csv": "Scenario CSV",
    "scenario_folder": "Scenario Folder",
    "flightgear_exe": "FlightGear Executable",
    "python_runner": "Python Simulation Runner",
    "config_file": "Configuration File",
    "aircraft_model": "Aircraft Model",
    "output_folder": "Output Folder",
    "dataset_folder": "Dataset Folder",
}

DEFAULT_CONFIG = dict(
    name="", description="", project="GreenAeroTester — Prototype",
    flightgear_version="2024.1", repeat_count=5, run_mode="Sequential",
    parallel_workers=4, carbon_intensity=475.0, idle_power=8.0, max_power=75.0,
    measurement_source=MEASUREMENT_SOURCES[0], hw_mode="Not Connected",
    timeout_limit_s=900, scenario_selection="All Scenarios",
)


def init_experiment_state() -> None:
    """Call once near the top of the Home page. Idempotent."""
    defaults = {
        "gat_exp_stage": "setup",
        "gat_exp_config": dict(DEFAULT_CONFIG),
        "gat_exp_uploads": {k: None for k in ALL_UPLOADS},
        "gat_exp_id": None,
        "gat_exp_progress": 0.0,
        "gat_exp_start_time": None,
        "gat_exp_paused_at": None,
        "gat_exp_paused_elapsed": 0.0,
        "gat_exp_status": "Idle",
        "gat_exp_log": [],
        "gat_exp_history": [],  # completed experiments: [{id, name, timestamp, config}]
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------
def get_stage() -> str:
    return st.session_state["gat_exp_stage"]


def set_stage(stage: str) -> None:
    st.session_state["gat_exp_stage"] = stage


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def get_config() -> dict:
    return st.session_state["gat_exp_config"]


def update_config(key: str, value) -> None:
    st.session_state["gat_exp_config"][key] = value


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------
def get_uploads() -> dict:
    return st.session_state["gat_exp_uploads"]


def set_upload(key: str, value: Optional[str]) -> None:
    st.session_state["gat_exp_uploads"][key] = value


def missing_required_uploads() -> list:
    uploads = get_uploads()
    return [k for k in REQUIRED_UPLOADS if not uploads.get(k)]


def can_start_experiment() -> bool:
    config = get_config()
    if not config.get("name", "").strip():
        return False
    if int(config.get("repeat_count", 0)) < 1:
        return False
    if missing_required_uploads():
        return False
    return True


# ---------------------------------------------------------------------------
# Experiment ID (SRS §6.1 common ID format: EXP001, EXP002, ...)
# ---------------------------------------------------------------------------
def _generate_experiment_id() -> str:
    n = len(st.session_state["gat_exp_history"]) + 1
    return f"EXP{str(n).zfill(3)}"


# ---------------------------------------------------------------------------
# Run controls
# ---------------------------------------------------------------------------
def start_experiment() -> None:
    st.session_state["gat_exp_id"] = _generate_experiment_id()
    st.session_state["gat_exp_progress"] = 0.0
    st.session_state["gat_exp_start_time"] = time.time()
    st.session_state["gat_exp_paused_at"] = None
    st.session_state["gat_exp_paused_elapsed"] = 0.0
    st.session_state["gat_exp_status"] = "Running"
    st.session_state["gat_exp_log"] = [
        f"[{st.session_state['gat_exp_id']}] Experiment started — "
        f"{get_config().get('name', 'Untitled')}"
    ]
    set_stage("running")


def pause_experiment() -> None:
    if st.session_state["gat_exp_status"] == "Running":
        st.session_state["gat_exp_paused_at"] = time.time()
        st.session_state["gat_exp_status"] = "Paused"
        st.session_state["gat_exp_log"].append("Experiment paused by user")


def resume_experiment() -> None:
    if st.session_state["gat_exp_status"] == "Paused" and st.session_state["gat_exp_paused_at"]:
        st.session_state["gat_exp_paused_elapsed"] += time.time() - st.session_state["gat_exp_paused_at"]
        st.session_state["gat_exp_paused_at"] = None
        st.session_state["gat_exp_status"] = "Running"
        st.session_state["gat_exp_log"].append("Experiment resumed by user")


def stop_experiment() -> None:
    st.session_state["gat_exp_status"] = "Stopped"
    st.session_state["gat_exp_log"].append("Experiment stopped by user")
    set_stage("setup")


def reset_experiment() -> None:
    st.session_state["gat_exp_stage"] = "setup"
    st.session_state["gat_exp_config"] = dict(DEFAULT_CONFIG)
    st.session_state["gat_exp_uploads"] = {k: None for k in ALL_UPLOADS}
    st.session_state["gat_exp_id"] = None
    st.session_state["gat_exp_progress"] = 0.0
    st.session_state["gat_exp_start_time"] = None
    st.session_state["gat_exp_paused_at"] = None
    st.session_state["gat_exp_paused_elapsed"] = 0.0
    st.session_state["gat_exp_status"] = "Idle"
    st.session_state["gat_exp_log"] = []


def load_previous_experiment(exp_id: str) -> bool:
    """Loads a completed experiment's config back into state and jumps
    straight to Results. Returns False if the id wasn't found."""
    for entry in st.session_state["gat_exp_history"]:
        if entry["id"] == exp_id:
            st.session_state["gat_exp_config"] = dict(entry["config"])
            st.session_state["gat_exp_id"] = exp_id
            st.session_state["gat_exp_status"] = "Completed"
            st.session_state["gat_exp_progress"] = 1.0
            set_stage("results")
            return True
    return False


# ---------------------------------------------------------------------------
# Progress tick — call once per rerun while stage == "running"
# ---------------------------------------------------------------------------
def tick_progress() -> dict:
    """Advances the demo clock and appends a log line if warranted. Returns a
    dict with progress_fraction, elapsed_s, remaining_s, finished (bool)."""
    status = st.session_state["gat_exp_status"]
    start = st.session_state["gat_exp_start_time"]

    if start is None:
        return dict(progress_fraction=0.0, elapsed_s=0.0, remaining_s=DEMO_RUN_DURATION_SECONDS, finished=False)

    now = st.session_state["gat_exp_paused_at"] or time.time()
    elapsed = (now - start) - st.session_state["gat_exp_paused_elapsed"]
    elapsed = max(0.0, elapsed)

    progress = min(1.0, elapsed / DEMO_RUN_DURATION_SECONDS)
    st.session_state["gat_exp_progress"] = progress
    remaining = max(0.0, DEMO_RUN_DURATION_SECONDS - elapsed)
    finished = progress >= 1.0

    if status == "Running" and not finished:
        provider = get_active_provider()
        line = provider.get_live_log_line(progress, rng_seed=hash(st.session_state["gat_exp_id"]) & 0xFFFF)
        log = st.session_state["gat_exp_log"]
        if line and (not log or log[-1] != line):
            log.append(line)
            if len(log) > 200:
                del log[: len(log) - 200]

    if finished and status == "Running":
        st.session_state["gat_exp_status"] = "Completed"
        st.session_state["gat_exp_log"].append(f"[{st.session_state['gat_exp_id']}] Experiment completed ✅")
        # Record into history so "Load Previous Experiment" has something to show.
        st.session_state["gat_exp_history"].append({
            "id": st.session_state["gat_exp_id"],
            "name": get_config().get("name", "Untitled"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": dict(get_config()),
        })

    return dict(progress_fraction=progress, elapsed_s=elapsed, remaining_s=remaining, finished=finished)
