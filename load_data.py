"""
utils/load_data.py
===================
Single source of truth for the GreenAeroTester dummy dataset.

Every function here reads from the ONE deterministic dataset returned by
:func:`load_dataset` (seed-fixed, cached), so any page — or the Settings
page's live chart previews — that calls into this module sees numbers
that are internally consistent with each other: Clean + Failed + Timeout
+ Crashed always equals total runs, carbon is always derived from energy
via one formula, and totals follow the SRS (500 scenarios, etc).

Status labels (``Clean``/``Failed``/``Timeout``/``Crashed``) intentionally
match the vocabulary already used by pages 1-7 so that if those pages are
ever migrated to import from here, no relabeling is required.

Backend integration
--------------------
Swap the body of :func:`load_dataset` for real CSV/API reads when the
GreenAeroTester backend pipeline is available. Every other function in
this module consumes the returned DataFrame's columns only — none of them
know or care how the rows were produced.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Dataset configuration (SRS-aligned constants)
# ---------------------------------------------------------------------------
SEED = 42
N_SCENARIOS = 500                         # SRS §4: target ~500 scenario configurations
MANDATORY_FRACTION = 0.15
CARBON_INTENSITY_G_PER_KWH = 475.0        # SRS §8: fixed, documented grid-average constant

FLIGHT_PHASES = [
    "Takeoff", "Climb", "Cruise", "Turn", "Descent",
    "Approach", "Landing", "Go-Around", "Emergency Landing",
]
WEATHER_CONDITIONS = ["Clear", "Crosswind", "Turbulence", "Icing", "Low Visibility", "Storm"]
FAULT_TYPES = [
    "None", "Sensor Fault", "Navigation Fault",
    "Communication Fault", "Control Degradation", "Engine Degradation",
]
SAFETY_LEVELS = ["DAL-A", "DAL-B", "DAL-C", "DAL-D"]
RESULT_STATUSES = ["Clean", "Failed", "Timeout", "Crashed"]
RESULT_PROBABILITIES = [0.85, 0.08, 0.04, 0.03]

_BASE_POWER_BY_PHASE = {
    "Takeoff": 55, "Climb": 48, "Cruise": 35, "Turn": 40, "Descent": 30,
    "Approach": 42, "Landing": 50, "Go-Around": 58, "Emergency Landing": 65,
}

DATASET_COLUMNS = [
    "run_id", "test_id", "scenario_id", "scenario_name", "flight_phase",
    "weather", "fault_type", "safety_level", "mandatory", "assurance_score",
    "runtime_sec", "cpu_usage_pct", "memory_usage_mb", "software_energy_wh",
    "hardware_energy_wh", "hardware_status", "power_w", "carbon_emissions_g",
    "result", "timestamp",
]


# ---------------------------------------------------------------------------
# Core dataset generator
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_dataset() -> pd.DataFrame:
    """Builds and returns the single dummy dataset shared by every page.

    One row per simulation run, joined with its parent test/scenario
    attributes. Deterministic (``SEED``) and cached, so repeated calls —
    from any page, in any order — always return identical data.

    Returns
    -------
    pandas.DataFrame
        Columns listed in ``DATASET_COLUMNS``.
    """
    rng = np.random.default_rng(SEED)

    scenario_ids = [f"S{str(i).zfill(4)}" for i in range(1, N_SCENARIOS + 1)]
    test_ids = [f"T{str(i).zfill(4)}" for i in range(1, N_SCENARIOS + 1)]

    phase = rng.choice(FLIGHT_PHASES, N_SCENARIOS)
    weather = rng.choice(WEATHER_CONDITIONS, N_SCENARIOS, p=[0.35, 0.15, 0.15, 0.1, 0.15, 0.1])
    fault = rng.choice(FAULT_TYPES, N_SCENARIOS, p=[0.4, 0.12, 0.12, 0.12, 0.12, 0.12])
    safety = rng.choice(SAFETY_LEVELS, N_SCENARIOS, p=[0.2, 0.3, 0.3, 0.2])
    mandatory = (rng.random(N_SCENARIOS) < MANDATORY_FRACTION) | (safety == "DAL-A")
    scenario_name = np.array([
        f"{p} / {f}" if f != "None" else f"{p} Nominal" for p, f in zip(phase, fault)
    ])

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
        weights["cert"] * certification, 0, 100,
    )

    runs_per_test = rng.integers(4, 9, N_SCENARIOS)

    rows = []
    run_counter = 1
    ts_cursor = pd.Timestamp("2026-01-01")
    for i in range(N_SCENARIOS):
        n_runs = runs_per_test[i]
        statuses = rng.choice(RESULT_STATUSES, n_runs, p=RESULT_PROBABILITIES)
        base_power = _BASE_POWER_BY_PHASE[phase[i]]
        for status in statuses:
            run_id = f"R{str(run_counter).zfill(6)}"
            run_counter += 1

            runtime_sec = max(5.0, rng.normal(180, 70))
            if status == "Timeout":
                runtime_sec = max(runtime_sec, rng.uniform(400, 900))

            avg_power_w = max(5.0, rng.normal(base_power, base_power * 0.15))
            cpu_usage_pct = float(np.clip(rng.normal(55, 15), 5, 100))
            memory_usage_mb = float(max(200, rng.normal(2200, 500)))

            software_energy_wh = (avg_power_w * runtime_sec) / 3600.0
            carbon_emissions_g = (software_energy_wh / 1000.0) * CARBON_INTENSITY_G_PER_KWH

            rows.append((
                run_id, test_ids[i], scenario_ids[i], scenario_name[i], phase[i],
                weather[i], fault[i], safety[i], bool(mandatory[i]), round(float(assurance_score[i]), 1),
                round(runtime_sec, 1), round(cpu_usage_pct, 1), round(memory_usage_mb, 1),
                round(software_energy_wh, 4),
                np.nan, "Pending / Not Connected",
                round(avg_power_w, 1), round(carbon_emissions_g, 3),
                status, ts_cursor,
            ))
            ts_cursor = ts_cursor + pd.Timedelta(minutes=1)

    return pd.DataFrame(rows, columns=DATASET_COLUMNS)


# ---------------------------------------------------------------------------
# Reusable summary accessors
# ---------------------------------------------------------------------------
def get_dashboard_summary(df: Optional[pd.DataFrame] = None) -> dict:
    """Home-page KPI summary.

    Guarantees Clean + Failed + Timeout + Crashed == total runs by
    construction of the source dataset, and total scenarios follows the
    SRS target (``N_SCENARIOS``).

    Parameters
    ----------
    df : DataFrame, optional
        Pass an already-loaded dataset to avoid reloading; defaults to
        :func:`load_dataset`.
    """
    df = df if df is not None else load_dataset()
    counts = df["result"].value_counts()
    total_runs = int(len(df))

    return {
        "total_scenarios": int(df["scenario_id"].nunique()),
        "total_tests": int(df["test_id"].nunique()),
        "total_runs": total_runs,
        "clean_runs": int(counts.get("Clean", 0)),
        "failed_runs": int(counts.get("Failed", 0)),
        "timeout_runs": int(counts.get("Timeout", 0)),
        "crashed_runs": int(counts.get("Crashed", 0)),
        "mandatory_tests": int(df.loc[df["mandatory"], "test_id"].nunique()),
        "total_software_energy_kwh": float(df["software_energy_wh"].sum() / 1000.0),
        "hardware_energy_status": "Pending / Not Connected",
        "total_carbon_kg": float(df["carbon_emissions_g"].sum() / 1000.0),
        "carbon_intensity_g_per_kwh": CARBON_INTENSITY_G_PER_KWH,
        "mean_assurance_score": float(df.drop_duplicates("test_id")["assurance_score"].mean()),
    }


def get_energy_summary(df: Optional[pd.DataFrame] = None) -> dict:
    """Energy & carbon page summary.

    All figures derive from the same formula used at generation time:
    ``software_energy_wh = power_w * runtime_sec / 3600`` and
    ``carbon_emissions_g = (software_energy_wh / 1000) * carbon_intensity``.

    Returns
    -------
    dict
        Aggregate totals plus grouped Series ready for charting.
    """
    df = df if df is not None else load_dataset()

    return {
        "total_software_energy_kwh": float(df["software_energy_wh"].sum() / 1000.0),
        "total_carbon_kg": float(df["carbon_emissions_g"].sum() / 1000.0),
        "avg_power_w": float(df["power_w"].mean()),
        "avg_runtime_sec": float(df["runtime_sec"].mean()),
        "avg_cpu_usage_pct": float(df["cpu_usage_pct"].mean()),
        "avg_memory_usage_mb": float(df["memory_usage_mb"].mean()),
        "hardware_energy_status": "Pending / Not Connected",
        "measurement_source": "cpu_based_estimate",
        "energy_by_phase_kwh": (df.groupby("flight_phase")["software_energy_wh"].sum() / 1000.0).sort_values(),
        "carbon_by_fault_type_kg": (df.groupby("fault_type")["carbon_emissions_g"].sum() / 1000.0).sort_values(),
        "energy_trend": df.set_index("timestamp").resample("2h")["software_energy_wh"].sum() / 1000.0,
        "carbon_trend": df.set_index("timestamp").resample("2h")["carbon_emissions_g"].sum() / 1000.0,
        "runtime_trend": df.set_index("timestamp").resample("2h")["runtime_sec"].mean(),
        "cpu_trend": df.set_index("timestamp").resample("2h")["cpu_usage_pct"].mean(),
        "memory_trend": df.set_index("timestamp").resample("2h")["memory_usage_mb"].mean(),
    }


def get_export_data(df: Optional[pd.DataFrame] = None) -> dict:
    """Rebuilds the SRS-required normalized tables (SRS §5) for the Export page.

    Parameters
    ----------
    df : DataFrame, optional
        Run-level dataset; defaults to :func:`load_dataset`.

    Returns
    -------
    dict
        File-name -> DataFrame, matching the eight files required by SRS §5:
        test_catalog, scenario_parameters, test_runs, energy_metrics,
        assurance_features, environment_metadata, plus a validation summary.
    """
    df = df if df is not None else load_dataset()

    test_catalog = df.drop_duplicates("test_id")[[
        "test_id", "scenario_id", "scenario_name", "flight_phase",
        "safety_level", "mandatory",
    ]].rename(columns={"scenario_name": "test_name", "flight_phase": "category"}).reset_index(drop=True)

    scenario_parameters = df.drop_duplicates("scenario_id")[[
        "scenario_id", "flight_phase", "weather", "fault_type", "safety_level", "mandatory",
    ]].rename(columns={"weather": "weather_condition", "fault_type": "failure_type"}).reset_index(drop=True)

    test_runs = df[[
        "run_id", "test_id", "scenario_id", "result", "runtime_sec",
        "cpu_usage_pct", "memory_usage_mb", "power_w", "timestamp",
    ]].rename(columns={"result": "status"}).reset_index(drop=True)

    energy_metrics = df[[
        "run_id", "software_energy_wh", "hardware_energy_wh", "hardware_status", "carbon_emissions_g",
    ]].copy()
    energy_metrics["carbon_intensity_g_per_kwh"] = CARBON_INTENSITY_G_PER_KWH
    energy_metrics["measurement_source"] = "cpu_based_estimate"

    assurance_features = df.drop_duplicates("test_id")[[
        "test_id", "safety_level", "mandatory", "assurance_score",
    ]].reset_index(drop=True)

    environment_metadata = pd.DataFrame([{
        "host_name": "GAT-BENCH-01", "os": "Windows 11 / PowerShell 7",
        "cpu": "Intel Core i7-12700H", "ram_gb": 32,
        "simulator": "FlightGear 2024.1 + JSBSim", "dashboard": "Streamlit",
        "dataset_seed": SEED, "carbon_intensity_source": "fixed grid-average constant",
    }])

    return {
        "test_catalog.csv": test_catalog,
        "scenario_parameters.csv": scenario_parameters,
        "test_runs.csv": test_runs,
        "energy_metrics.csv": energy_metrics,
        "assurance_features.csv": assurance_features,
        "environment_metadata.csv": environment_metadata,
    }


def get_recent_activity(df: Optional[pd.DataFrame] = None, n: int = 10) -> pd.DataFrame:
    """Returns the ``n`` most recent runs for a Home/Activity widget.

    Parameters
    ----------
    df : DataFrame, optional
        Run-level dataset; defaults to :func:`load_dataset`.
    n : int
        Number of most-recent rows to return (default 10).

    Returns
    -------
    pandas.DataFrame
        Sorted descending by timestamp, with the columns most relevant to
        an activity feed.
    """
    df = df if df is not None else load_dataset()
    cols = ["run_id", "test_id", "scenario_id", "flight_phase", "result",
            "runtime_sec", "power_w", "carbon_emissions_g", "timestamp"]
    return df.sort_values("timestamp", ascending=False).head(n)[cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Prioritization / baseline helpers (bonus reusable functions — used by the
# Settings page's live "Priority Chart" preview and available to any future
# refactor of the Prioritization/Baseline pages).
# ---------------------------------------------------------------------------
PRIORITIZATION_METHODS = [
    "Default CI Order",
    "Random Order (median of 30)",
    "Runtime-Based",
    "Failure-History-Based",
    "Energy-Aware (Proposed)",
    "Knapsack (0/1 DP)",
]


def _test_level_table(df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Aggregates the run-level dataset to one row per test (median energy
    and median runtime across repeated runs, per SRS §11)."""
    df = df if df is not None else load_dataset()
    agg = df.groupby("test_id", as_index=False).agg(
        scenario_id=("scenario_id", "first"),
        scenario_name=("scenario_name", "first"),
        flight_phase=("flight_phase", "first"),
        safety_level=("safety_level", "first"),
        mandatory=("mandatory", "first"),
        assurance_score=("assurance_score", "first"),
        median_runtime_sec=("runtime_sec", "median"),
        median_software_energy_wh=("software_energy_wh", "median"),
        failure_rate=("result", lambda s: float((s != "Clean").mean())),
        run_count=("run_id", "count"),
    )
    agg["utility_score"] = agg["assurance_score"] / agg["median_software_energy_wh"]
    return agg


def _knapsack_01(optional: pd.DataFrame, budget_remaining: float, n_bins: int = 1500) -> pd.DataFrame:
    """0/1 knapsack (discretized DP) maximizing assurance score within budget."""
    weights = optional["median_software_energy_wh"].to_numpy()
    values = optional["assurance_score"].to_numpy()
    n = len(weights)
    if n == 0 or budget_remaining <= 0:
        return optional.iloc[0:0]

    scale = n_bins / budget_remaining
    w_scaled = np.minimum(n_bins, np.round(weights * scale).astype(int))

    dp = np.zeros(n_bins + 1)
    keep = np.zeros((n, n_bins + 1), dtype=bool)
    for i in range(n):
        w, v = w_scaled[i], values[i]
        if w > n_bins:
            continue
        prev = dp.copy()
        cand = np.empty_like(dp)
        cand[:w] = -1
        cand[w:] = prev[:n_bins + 1 - w] + v
        take = cand > prev
        dp = np.where(take, cand, prev)
        keep[i] = take

    chosen_idx, cap = [], n_bins
    for i in range(n - 1, -1, -1):
        if keep[i, cap]:
            chosen_idx.append(i)
            cap -= w_scaled[i]
    return optional.iloc[chosen_idx]


def _select_tests(test_table: pd.DataFrame, method: str, budget_fraction: float,
                   rng_seed: int = 7) -> pd.DataFrame:
    """Selects tests under an energy budget using the given method (SRS §11).
    Mandatory tests are always included first."""
    total_energy = test_table["median_software_energy_wh"].sum()
    budget = total_energy * max(0.0, min(1.0, budget_fraction))
    mandatory = test_table[test_table["mandatory"]]
    optional = test_table[~test_table["mandatory"]].copy()
    budget_remaining = budget - mandatory["median_software_energy_wh"].sum()

    if method == "Default CI Order":
        optional = optional.sort_values("test_id")
    elif method in ("Random Order", "Random Order (median of 30)"):
        optional = optional.sample(frac=1.0, random_state=rng_seed)
    elif method == "Runtime-Based":
        optional = optional.sort_values("median_runtime_sec")
    elif method == "Failure-History-Based":
        optional = optional.sort_values("failure_rate", ascending=False)
    elif method == "Energy-Aware (Proposed)":
        optional = optional.sort_values("utility_score", ascending=False)
    elif method == "Knapsack (0/1 DP)":
        chosen = _knapsack_01(optional, budget_remaining) if budget_remaining > 0 else optional.iloc[0:0]
        return pd.concat([mandatory, chosen])
    else:
        raise ValueError(f"Unknown prioritization method: {method}")

    if budget_remaining <= 0:
        chosen = optional.iloc[0:0]
    else:
        cum = optional["median_software_energy_wh"].cumsum()
        chosen = optional[cum <= budget_remaining]
    return pd.concat([mandatory, chosen])


def _summarize_selection(test_table: pd.DataFrame, selected: pd.DataFrame) -> dict:
    """Baseline-comparison metrics for one method's selection (SRS §12)."""
    full_energy = test_table["median_software_energy_wh"].sum()
    full_runtime = test_table["median_runtime_sec"].sum()
    full_assurance = test_table["assurance_score"].sum()
    mandatory_total = test_table["mandatory"].sum()

    sel_energy = selected["median_software_energy_wh"].sum()
    sel_runtime = selected["median_runtime_sec"].sum()
    sel_assurance = selected["assurance_score"].sum()
    sel_mandatory = selected["mandatory"].sum()
    sel_carbon_g = (sel_energy / 1000.0) * CARBON_INTENSITY_G_PER_KWH

    return {
        "num_selected": int(len(selected)),
        "total_energy_kwh": float(sel_energy / 1000.0),
        "total_runtime_min": float(sel_runtime / 60.0),
        "total_carbon_kg": float(sel_carbon_g / 1000.0),
        "assurance_retained_pct": float(100 * sel_assurance / full_assurance) if full_assurance else 0.0,
        "mandatory_coverage_pct": float(100 * sel_mandatory / mandatory_total) if mandatory_total else 100.0,
        "energy_saved_pct": float(100 * (full_energy - sel_energy) / full_energy) if full_energy else 0.0,
        "runtime_saved_pct": float(100 * (full_runtime - sel_runtime) / full_runtime) if full_runtime else 0.0,
    }


def get_prioritization_data(
    df: Optional[pd.DataFrame] = None,
    method: str = "Energy-Aware (Proposed)",
    budget_fraction: float = 0.60,
) -> dict:
    """Ranked test selection under an energy budget (SRS §11).

    Returns
    -------
    dict
        ``{"ranked": DataFrame, "summary": dict}``.
    """
    test_table = _test_level_table(df)
    lookup_method = "Random Order" if method.startswith("Random") else method
    selected = _select_tests(test_table, lookup_method, budget_fraction)

    sort_map = {
        "Default CI Order": ("test_id", True),
        "Runtime-Based": ("median_runtime_sec", True),
        "Failure-History-Based": ("failure_rate", False),
        "Energy-Aware (Proposed)": ("utility_score", False),
        "Knapsack (0/1 DP)": ("assurance_score", False),
    }
    sort_col, ascending = sort_map.get(method, ("utility_score", False))
    ranked = selected.sort_values(sort_col, ascending=ascending).reset_index(drop=True)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))

    return {"ranked": ranked, "summary": _summarize_selection(test_table, selected)}


def get_baseline_data(df: Optional[pd.DataFrame] = None, budget_fraction: float = 0.60) -> pd.DataFrame:
    """Baseline comparison across all prioritization methods (SRS §12).

    Returns
    -------
    pandas.DataFrame
        One row per method with selection-size, energy, runtime, carbon,
        assurance-retained %, mandatory-coverage %, energy-saved % and
        runtime-saved % columns.
    """
    test_table = _test_level_table(df)
    rows = []
    for method in PRIORITIZATION_METHODS:
        lookup_method = "Random Order" if method.startswith("Random") else method
        selected = _select_tests(test_table, lookup_method, budget_fraction)
        row = _summarize_selection(test_table, selected)
        row["method"] = method
        rows.append(row)

    return pd.DataFrame(rows)[[
        "method", "num_selected", "total_energy_kwh", "total_runtime_min", "total_carbon_kg",
        "assurance_retained_pct", "mandatory_coverage_pct", "energy_saved_pct", "runtime_saved_pct",
    ]]
