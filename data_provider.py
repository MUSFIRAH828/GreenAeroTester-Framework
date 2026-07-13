# ============================================================================
# utils/data_provider.py
# ============================================================================
# Centralized data access layer for GreenAeroTester (SRS §5 shared prototype,
# §6 shared system design rules, §8 backend expectations).
#
# WHY THIS FILE EXISTS
# ---------------------
# Previously every page embedded its own copy of `load_dataset()` (same seed,
# same logic, duplicated). That was fine for a static dashboard, but the new
# Home page is a real Experiment Control Center: it needs to hand data to a
# live-monitoring view, a results dashboard, and (eventually) a real backend
# pipeline — without the page itself caring where the numbers came from.
#
# The fix is the classic "repository" / "data provider" pattern:
#   - ExperimentDataProvider   : the CONTRACT every page/page-section relies on.
#   - DummyDataProvider        : today's implementation — deterministic,
#                                seeded, in-memory synthetic data.
#   - BackendDataProvider      : tomorrow's implementation — reads the real
#                                CSV files the backend team produces
#                                (SRS §6.4 file list). Stubbed for now.
#
# Pages should NEVER call `np.random` or build a dataset inline again.
# They call `get_active_provider()` and use its methods. Swapping Dummy ->
# Backend later is a ONE-LINE change in `get_active_provider()` — nothing
# else in the app needs to change, because both providers return the exact
# same shapes (same dict of DataFrames, same summary dict keys).
# ============================================================================

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Shared constants (SRS §4 Phase 1, §8 measurement, §11 prioritization)
# ---------------------------------------------------------------------------
SEED = 42
N_SCENARIOS = 500                       # SRS §4 Phase 1: target ~500 scenario configurations
CARBON_INTENSITY_G_PER_KWH = 475.0      # SRS §8: documented fixed grid-average assumption
MANDATORY_FRACTION = 0.15

FLIGHT_PHASES = ["Takeoff", "Climb", "Cruise", "Turn", "Descent", "Approach",
                  "Landing", "Go-Around", "Emergency Landing"]
WEATHER = ["Clear", "Crosswind", "Turbulence", "Icing", "Low Visibility", "Storm"]
FAULT_TYPES = ["None", "Sensor Fault", "Navigation Fault", "Communication Fault",
               "Control Degradation", "Engine Degradation"]
SUBSYSTEMS = ["Flight Control", "Navigation", "Propulsion", "Avionics", "Sensors", "Communication"]
SAFETY_LEVELS = ["DAL-A", "DAL-B", "DAL-C", "DAL-D"]
METHODS = ["Default CI Order", "Random Order (median of 30)", "Runtime-Based",
           "Failure-History-Based", "Energy-Aware (Proposed)", "Knapsack (0/1 DP)"]

# SRS §8.5 — software measurement method options intern 1 may choose between.
MEASUREMENT_SOURCES = ["cpu_based_estimate", "psutil_cpu_estimate", "codecarbon", "hwinfo"]

# Demo pacing for the Live Monitoring simulation — NOT a real runtime. A real
# backend run of ~500 scenarios would take hours; the control-center demo
# compresses that into a short, watchable progress bar. Swap this out once
# `BackendDataProvider` streams real progress events instead of a clock.
DEMO_RUN_DURATION_SECONDS = 24.0


# ---------------------------------------------------------------------------
# Prioritization helpers (SRS §11) — used to build the canonical baseline
# snapshot shown on Home/Export. Unchanged logic, just relocated here so it
# lives next to the data it operates on instead of inside a page file.
# ---------------------------------------------------------------------------
def _knapsack_01(optional: pd.DataFrame, budget_remaining: float, n_bins: int = 1500) -> pd.DataFrame:
    """0/1 knapsack maximizing total assurance score within an energy budget,
    solved on a discretized weight grid (DP) — the 'Knapsack (0/1 DP)' method."""
    weights = optional["median_energy_joules"].to_numpy()
    values = optional["assurance_score"].to_numpy()
    n = len(weights)
    if n == 0 or budget_remaining <= 0:
        return optional.iloc[0:0]

    scale = n_bins / budget_remaining
    w_scaled = np.minimum(n_bins, np.round(weights * scale).astype(int))

    dp = np.zeros(n_bins + 1)
    keep = np.zeros((n, n_bins + 1), dtype=bool)
    for i in range(n):
        w = w_scaled[i]
        v = values[i]
        if w > n_bins:
            continue
        prev = dp.copy()
        cand = np.empty_like(dp)
        cand[:w] = -1
        cand[w:] = prev[:n_bins + 1 - w] + v
        take = cand > prev
        dp = np.where(take, cand, prev)
        keep[i] = take

    chosen_idx = []
    cap = n_bins
    for i in range(n - 1, -1, -1):
        if keep[i, cap]:
            chosen_idx.append(i)
            cap -= w_scaled[i]
    return optional.iloc[chosen_idx]


def _select_tests(scoring: pd.DataFrame, method: str, budget_fraction: float, rng_seed: int = 7) -> pd.DataFrame:
    """Selects tests under an energy budget using the requested prioritization
    method (SRS §11). Mandatory tests are always included first."""
    total_energy = scoring["median_energy_joules"].sum()
    budget = total_energy * max(0.0, min(1.0, budget_fraction))
    mandatory = scoring[scoring["mandatory"]]
    optional = scoring[~scoring["mandatory"]].copy()
    budget_remaining = budget - mandatory["median_energy_joules"].sum()

    if method == "Default CI Order":
        optional = optional.sort_values("test_id")
    elif method in ("Random Order", "Random Order (median of 30)"):
        optional = optional.sample(frac=1.0, random_state=rng_seed)
    elif method == "Runtime-Based":
        optional = optional.sort_values("median_runtime_s")
    elif method == "Failure-History-Based":
        optional = optional.sort_values("failure_rate", ascending=False)
    elif method == "Energy-Aware (Proposed)":
        optional = optional.sort_values("utility_score", ascending=False)
    elif method == "Knapsack (0/1 DP)":
        chosen_optional = _knapsack_01(optional, budget_remaining) if budget_remaining > 0 else optional.iloc[0:0]
        return pd.concat([mandatory, chosen_optional])
    else:
        raise ValueError(f"Unknown method: {method}")

    if budget_remaining <= 0:
        chosen_optional = optional.iloc[0:0]
    else:
        cum = optional["median_energy_joules"].cumsum()
        chosen_optional = optional[cum <= budget_remaining]
    return pd.concat([mandatory, chosen_optional])


def _summarize(scoring: pd.DataFrame, selected: pd.DataFrame, carbon_intensity: float) -> dict:
    """Baseline-comparison metrics for one method's selection (SRS §12)."""
    full_energy = scoring["median_energy_joules"].sum()
    full_runtime = scoring["median_runtime_s"].sum()
    full_assurance = scoring["assurance_score"].sum()
    mand_total = scoring["mandatory"].sum()

    sel_energy = selected["median_energy_joules"].sum()
    sel_runtime = selected["median_runtime_s"].sum()
    sel_assurance = selected["assurance_score"].sum()
    sel_mandatory = selected["mandatory"].sum()
    sel_carbon = (sel_energy / 3.6e6) * carbon_intensity

    return dict(
        num_selected=int(len(selected)),
        total_energy_j=float(sel_energy),
        total_runtime_s=float(sel_runtime),
        total_carbon_g=float(sel_carbon),
        assurance_retained_pct=float(100 * sel_assurance / full_assurance),
        mandatory_coverage_pct=float(100 * sel_mandatory / mand_total) if mand_total else 100.0,
        energy_saved_pct=float(100 * (full_energy - sel_energy) / full_energy),
        runtime_saved_pct=float(100 * (full_runtime - sel_runtime) / full_runtime),
    )


@st.cache_data(show_spinner=False)
def _build_dummy_dataset() -> dict:
    """Builds the ONE dummy dataset used by the Dummy provider (SRS §5 files,
    §9 cleaning rules, §11 prioritization). Deterministic seed -> identical
    numbers every run. This is verbatim the logic that used to live inline in
    1_Home.py — only moved, not changed, so existing numbers don't shift."""
    rng = np.random.default_rng(SEED)

    scenario_ids = [f"S{str(i).zfill(4)}" for i in range(1, N_SCENARIOS + 1)]
    test_ids = [f"T{str(i).zfill(4)}" for i in range(1, N_SCENARIOS + 1)]

    phase = rng.choice(FLIGHT_PHASES, N_SCENARIOS)
    weather = rng.choice(WEATHER, N_SCENARIOS, p=[0.35, 0.15, 0.15, 0.1, 0.15, 0.1])
    fault = rng.choice(FAULT_TYPES, N_SCENARIOS, p=[0.4, 0.12, 0.12, 0.12, 0.12, 0.12])
    subsystem = rng.choice(SUBSYSTEMS, N_SCENARIOS)
    safety = rng.choice(SAFETY_LEVELS, N_SCENARIOS, p=[0.2, 0.3, 0.3, 0.2])
    mandatory = (rng.random(N_SCENARIOS) < MANDATORY_FRACTION) | (safety == "DAL-A")

    wind_speed = np.round(rng.uniform(0, 45, N_SCENARIOS), 1)
    wind_dir = rng.integers(0, 360, N_SCENARIOS)
    turbulence = np.round(rng.uniform(0, 1, N_SCENARIOS), 2)
    start_alt = rng.integers(0, 41000, N_SCENARIOS)
    start_speed = rng.integers(80, 560, N_SCENARIOS)
    fail_time = np.where(fault != "None", np.round(rng.uniform(1, 300, N_SCENARIOS), 1), 0.0)
    duration = np.round(rng.uniform(30, 900, N_SCENARIOS), 1)

    scenario_parameters = pd.DataFrame({
        "scenario_id": scenario_ids, "flight_phase": phase, "weather_condition": weather,
        "wind_speed_kt": wind_speed, "wind_dir_deg": wind_dir, "turbulence_level": turbulence,
        "start_altitude_ft": start_alt, "start_airspeed_kt": start_speed,
        "failure_type": fault, "failure_time_s": fail_time, "duration_s": duration,
        "subsystem": subsystem, "safety_level": safety, "mandatory": mandatory,
    })

    test_catalog = pd.DataFrame({
        "test_id": test_ids, "scenario_id": scenario_ids,
        "test_name": [f"{p} / {f}" if f != "None" else f"{p} Nominal" for p, f in zip(phase, fault)],
        "subsystem": subsystem, "safety_level": safety, "mandatory": mandatory,
        "category": phase,
    })

    runs_per_test = rng.integers(4, 9, N_SCENARIOS)
    run_rows = []
    run_counter = 1
    status_choices = np.array(["Clean", "Failed", "Timeout", "Crashed"])
    status_p = [0.85, 0.08, 0.04, 0.03]
    base_power = {"Takeoff": 55, "Climb": 48, "Cruise": 35, "Turn": 40, "Descent": 30,
                  "Approach": 42, "Landing": 50, "Go-Around": 58, "Emergency Landing": 65}

    for i in range(N_SCENARIOS):
        n = runs_per_test[i]
        statuses = rng.choice(status_choices, n, p=status_p)
        bp = base_power[phase[i]]
        for s in statuses:
            rid = f"R{str(run_counter).zfill(6)}"
            run_counter += 1
            runtime = max(5.0, rng.normal(180, 70))
            if s == "Timeout":
                runtime = max(runtime, rng.uniform(400, 900))
            avg_power = max(5.0, rng.normal(bp, bp * 0.15))
            peak_power = avg_power * rng.uniform(1.15, 1.5)
            avg_cpu = min(100, max(5, rng.normal(55, 15)))
            peak_cpu = min(100, avg_cpu + rng.uniform(5, 35))
            avg_mem = max(200, rng.normal(2200, 500))
            peak_mem = avg_mem + rng.uniform(100, 900)
            run_rows.append((rid, test_ids[i], scenario_ids[i], s, runtime,
                              avg_cpu, peak_cpu, avg_mem, peak_mem, avg_power, peak_power))

    test_runs = pd.DataFrame(run_rows, columns=[
        "run_id", "test_id", "scenario_id", "status", "runtime_s",
        "avg_cpu_pct", "peak_cpu_pct", "avg_mem_mb", "peak_mem_mb",
        "avg_power_w", "peak_power_w"])
    test_runs["timestamp"] = pd.date_range("2026-01-01", periods=len(test_runs), freq="min")
    test_runs["output_ref"] = test_runs["run_id"].apply(lambda r: f"outputs/{r}.jsonl")

    energy_joules = test_runs["avg_power_w"] * test_runs["runtime_s"]
    energy_metrics = pd.DataFrame({
        "run_id": test_runs["run_id"],
        "energy_joules": energy_joules,
        "energy_wh": energy_joules / 3600.0,
        "carbon_intensity_g_per_kwh": CARBON_INTENSITY_G_PER_KWH,
        "estimated_carbon_gco2": (energy_joules / 3.6e6) * CARBON_INTENSITY_G_PER_KWH,
        "measurement_source": "cpu_based_estimate",
    })

    merged = test_runs.merge(energy_metrics, on="run_id")

    safety_map = {"DAL-A": 100, "DAL-B": 80, "DAL-C": 55, "DAL-D": 30}
    safety_crit = np.array([safety_map[s] for s in safety])
    req_cov = rng.uniform(40, 100, N_SCENARIOS)
    fault_hist = rng.uniform(0, 100, N_SCENARIOS)
    recent_change = rng.uniform(0, 100, N_SCENARIOS)
    novelty = rng.uniform(0, 100, N_SCENARIOS)
    flakiness = rng.uniform(0, 100, N_SCENARIOS)
    certification = safety_crit * rng.uniform(0.8, 1.0, N_SCENARIOS)

    weights = dict(safety=0.30, coverage=0.20, fault=0.15, recent=0.10,
                   novelty=0.10, flaky=0.05, cert=0.10)
    assurance_score = np.clip(
        weights["safety"] * safety_crit + weights["coverage"] * req_cov +
        weights["fault"] * fault_hist + weights["recent"] * recent_change +
        weights["novelty"] * novelty + weights["flaky"] * (100 - flakiness) +
        weights["cert"] * certification, 0, 100)

    assurance_features = pd.DataFrame({
        "test_id": test_ids, "safety_criticality": safety_crit,
        "requirement_coverage": np.round(req_cov, 1), "fault_history": np.round(fault_hist, 1),
        "recent_change_relevance": np.round(recent_change, 1), "novelty": np.round(novelty, 1),
        "flakiness": np.round(flakiness, 1), "certification_relevance": np.round(certification, 1),
        "assurance_score": np.round(assurance_score, 1),
        "weights_config": ["safety:0.30,coverage:0.20,fault:0.15,recent:0.10,novelty:0.10,flaky:0.05,cert:0.10"] * N_SCENARIOS,
    })

    med_energy = merged.groupby("test_id")["energy_joules"].median().rename("median_energy_joules")
    med_runtime = merged.groupby("test_id")["runtime_s"].median().rename("median_runtime_s")
    fail_rate = (merged["status"] != "Clean").groupby(merged["test_id"]).mean().rename("failure_rate")

    scoring = (test_catalog
               .merge(assurance_features, on="test_id")
               .merge(med_energy, on="test_id")
               .merge(med_runtime, on="test_id")
               .merge(fail_rate, on="test_id"))
    scoring["utility_score"] = scoring["assurance_score"] / scoring["median_energy_joules"]

    environment_metadata = pd.DataFrame([{
        "host_name": "GAT-BENCH-01", "os": "Windows 11 / PowerShell 7",
        "cpu": "Intel Core i7-12700H", "ram_gb": 32,
        "simulator": "FlightGear 2024.1 + JSBSim", "python_version": "3.11",
        "dashboard": "Streamlit", "dataset_seed": SEED,
        "carbon_intensity_source": "fixed grid-average constant (documented assumption)",
        "generated_at": "2026-06-01T00:00:00Z",
    }])

    default_budget = 0.60
    canonical_selected = _select_tests(scoring, "Energy-Aware (Proposed)", default_budget)
    prioritization_decisions = canonical_selected[[
        "test_id", "scenario_id", "assurance_score", "median_energy_joules",
        "median_runtime_s", "utility_score", "mandatory"
    ]].copy()
    prioritization_decisions.insert(0, "rank", range(1, len(prioritization_decisions) + 1))
    prioritization_decisions["method"] = "Energy-Aware (Proposed)"
    prioritization_decisions["budget_fraction"] = default_budget

    baseline_rows = []
    for m in METHODS:
        seed_m = m.startswith("Random")
        sel = _select_tests(scoring, "Random Order" if seed_m else m, default_budget)
        s = _summarize(scoring, sel, CARBON_INTENSITY_G_PER_KWH)
        s["method"] = m
        baseline_rows.append(s)
    baseline_comparison = pd.DataFrame(baseline_rows)[[
        "method", "num_selected", "total_energy_j", "total_runtime_s", "total_carbon_g",
        "assurance_retained_pct", "mandatory_coverage_pct", "energy_saved_pct", "runtime_saved_pct",
    ]]

    return dict(
        scenario_parameters=scenario_parameters,
        test_catalog=test_catalog,
        test_runs=test_runs,
        energy_metrics=energy_metrics,
        assurance_features=assurance_features,
        scoring=scoring,
        environment_metadata=environment_metadata,
        prioritization_decisions=prioritization_decisions,
        baseline_comparison=baseline_comparison,
        merged_runs=merged,
    )


# ---------------------------------------------------------------------------
# Provider contract
# ---------------------------------------------------------------------------
class ExperimentDataProvider(ABC):
    """Every page reads data ONLY through an implementation of this contract.
    Swapping Dummy -> Backend must never require a page or chart to change."""

    @abstractmethod
    def get_dataset(self) -> dict:
        """Returns the canonical dict of DataFrames: scenario_parameters,
        test_catalog, test_runs, energy_metrics, assurance_features, scoring,
        environment_metadata, prioritization_decisions, baseline_comparison,
        merged_runs."""
        raise NotImplementedError

    @abstractmethod
    def get_experiment_summary(self, config: dict) -> dict:
        """Given the Experiment Info form config, returns estimated totals for
        the Experiment Summary panel: total_scenarios, mandatory_tests,
        optional_tests, estimated_total_runs, estimated_runtime_min,
        estimated_energy_kwh, estimated_carbon_kg, estimated_dataset_size_mb."""
        raise NotImplementedError

    @abstractmethod
    def get_live_log_line(self, progress_fraction: float, rng_seed: int) -> Optional[str]:
        """Returns a log line appropriate for the current run progress, or
        None if no new line should be emitted this tick."""
        raise NotImplementedError


class DummyDataProvider(ExperimentDataProvider):
    """Today's implementation: deterministic, seeded, in-memory synthetic
    data. No file I/O, no backend required — this is what frontend-only mode
    runs on (SRS §5 shared prototype)."""

    def get_dataset(self) -> dict:
        return _build_dummy_dataset()

    def get_experiment_summary(self, config: dict) -> dict:
        d = self.get_dataset()
        test_catalog = d["test_catalog"]
        test_runs = d["test_runs"]
        energy_metrics = d["energy_metrics"]

        total_scenarios = len(d["scenario_parameters"])
        mandatory_tests = int(test_catalog["mandatory"].sum())
        optional_tests = total_scenarios - mandatory_tests

        repeat_count = max(1, int(config.get("repeat_count", 1)))
        estimated_total_runs = total_scenarios * repeat_count

        avg_runtime_s = float(test_runs["runtime_s"].mean())
        avg_energy_wh = float(energy_metrics["energy_wh"].mean())

        workers = max(1, int(config.get("parallel_workers", 1))) if config.get("run_mode") == "Parallel" else 1
        estimated_runtime_min = (estimated_total_runs * avg_runtime_s / max(1, workers)) / 60.0

        estimated_energy_kwh = (estimated_total_runs * avg_energy_wh) / 1000.0
        carbon_intensity = float(config.get("carbon_intensity", CARBON_INTENSITY_G_PER_KWH))
        estimated_carbon_kg = (estimated_energy_kwh * carbon_intensity) / 1000.0

        # Rough per-run dataset footprint (JSON log + CSV rows), for a
        # ballpark "how big will this dataset be" figure.
        estimated_dataset_size_mb = (estimated_total_runs * 2.2) / 1024.0

        return dict(
            total_scenarios=total_scenarios,
            mandatory_tests=mandatory_tests,
            optional_tests=optional_tests,
            estimated_total_runs=estimated_total_runs,
            estimated_runtime_min=estimated_runtime_min,
            estimated_energy_kwh=estimated_energy_kwh,
            estimated_carbon_kg=estimated_carbon_kg,
            estimated_dataset_size_mb=estimated_dataset_size_mb,
        )

    def get_live_log_line(self, progress_fraction: float, rng_seed: int) -> Optional[str]:
        rng = np.random.default_rng(rng_seed)
        cycle = ["Scenario Started", "Simulation Running", "CPU Sample Recorded",
                 "Energy Estimated", "Scenario Completed"]
        # Occasionally inject a failure-style event so the log looks real
        # (SRS §6.2 raw-data rule: failures/timeouts are recorded, not hidden).
        if rng.random() < 0.06:
            return rng.choice(["Timeout", "Failed", "Crashed — retrying"])
        step = int(progress_fraction * 1000) % len(cycle)
        return cycle[step]


class BackendDataProvider(ExperimentDataProvider):
    """Tomorrow's implementation. Once the backend team's pipeline
    (executor.py -> energy_collector.py -> data_store.py) is producing real
    files under data/processed/ (SRS §6.4), implement each method below by
    reading those CSVs instead of raising. The method signatures and return
    shapes MUST match DummyDataProvider exactly — that's the whole point."""

    def __init__(self, data_dir: str = "data/processed"):
        self.data_dir = data_dir

    def get_dataset(self) -> dict:
        raise NotImplementedError(
            "BackendDataProvider.get_dataset() is not implemented yet. "
            "Wire this to read test_catalog.csv, test_runs.csv, "
            "software_energy_metrics.csv, assurance_features.csv, "
            "prioritization_decisions.csv, baseline_comparison.csv from "
            f"'{self.data_dir}' (SRS §6.4) and return the same dict shape "
            "as DummyDataProvider.get_dataset()."
        )

    def get_experiment_summary(self, config: dict) -> dict:
        raise NotImplementedError(
            "BackendDataProvider.get_experiment_summary() is not implemented "
            "yet. Compute the same keys as DummyDataProvider from the real "
            "dataset once it exists."
        )

    def get_live_log_line(self, progress_fraction: float, rng_seed: int) -> Optional[str]:
        raise NotImplementedError(
            "BackendDataProvider.get_live_log_line() is not implemented yet. "
            "Replace this with real log-tailing from outputs/logs/ once the "
            "executor writes them during a run."
        )


def get_active_provider() -> ExperimentDataProvider:
    """Single switch point for the whole app. Change this ONE line when the
    backend is ready — nothing else needs to change."""
    return DummyDataProvider()
    # return BackendDataProvider()  # <- flip to this once the backend exists
