# ============================================================================
# GreenAeroTester — shared data model, styling tokens and UI helpers.
# This block is intentionally IDENTICAL across all 8 frontend files.
# Rationale: the brief restricts output to exactly 8 files with no shared
# utility module, so the single source of truth for the dummy dataset is
# reproduced verbatim (same seed, same logic) on every page. Because the
# random seed and generation steps never change, every page computes the
# exact same numbers. When a real backend/CSV pipeline is ready, only the
# body of `load_dataset()` needs to change (see Phase 8 note in each file);
# everything downstream (pages, charts, tables) reads from the returned
# dict of dataframes and does not need to change.
# ============================================================================

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from utils.theme import apply_theme, get_theme_colors, get_chart_colors, init_session_defaults

init_session_defaults()
COLORS = get_theme_colors()
# ---------------------------------------------------------------------------
# Design tokens — now sourced from utils/theme.py (global Dark/Light +
# per-chart color engine) instead of a hardcoded dict duplicated per file.
# ---------------------------------------------------------------------------
init_session_defaults()
COLORS = get_theme_colors()

STATUS_COLORS = {
    "Clean": COLORS["accent"],
    "Failed": COLORS["danger"],
    "Timeout": COLORS["amber"],
    "Crashed": COLORS["purple"],
}

PLOTLY_TEMPLATE = COLORS["plotly_template"]

# NOTE: the old hardcoded BASE_CSS string has been removed. styles/style.css
# now defines the same class names using CSS variables, and
# utils.theme.apply_theme() injects both the variables AND that stylesheet.


def inject_css():
    apply_theme()


def sidebar_brand(active_hint: str = ""):
    with st.sidebar:
        st.markdown(
            f"""
            <div class="gat-brand">
                <div class="gat-brand-mark">🌱</div>
                <div class="gat-brand-text">
                    <div class="gat-brand-title">GreenAeroTester</div>
                    <div class="gat-brand-sub">ENERGY-AWARE VALIDATION</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
       


def sidebar_status_footer(d):
    total_runs = len(d["test_runs"])
    total_scn = len(d["scenario_parameters"])
    with st.sidebar:
        st.markdown(
            f"""
            <div class="gat-sidebar-status">
                <div><span class="gat-dot"></span>System nominal</div>
                <div style="margin-top:6px; color:{COLORS['text_faint']}">
                    {total_scn} scenarios &middot; {total_runs:,} runs<br/>
                    dataset seed: 42 (deterministic)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def page_header(eyebrow, title, subtitle, pill_text=None):
    pill_html = f'<div class="gat-pill">{pill_text}</div>' if pill_text else ""
    st.markdown(
        f"""
        <div class="gat-header">
            <div>
                <div class="gat-eyebrow">{eyebrow}</div>
                <div class="gat-title">{title}</div>
                <div class="gat-subtitle">{subtitle}</div>
            </div>
            {pill_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(text, tag=None):
    tag_html = f'<span class="tag">{tag}</span>' if tag else ""
    st.markdown(f'<div class="gat-section-title">{text} {tag_html}</div>', unsafe_allow_html=True)


def metric_card(label, value, delta=None, accent=None):
    accent = accent or COLORS["accent"]
    delta_html = ""
    if delta is not None:
        cls = "up" if delta.strip().startswith("+") or delta.strip().startswith("↑") else (
            "down" if delta.strip().startswith("-") or delta.strip().startswith("↓") else "")
        delta_html = f'<div class="gat-card-delta {cls}">{delta}</div>'
    st.markdown(
        f"""
        <div class="gat-card" style="--accent-color:{accent}">
            <div class="gat-card-label">{label}</div>
            <div class="gat-card-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge_html(status):
    c = STATUS_COLORS.get(status, COLORS["text_dim"])
    return f'<span class="gat-badge" style="background:{c}22; color:{c}; border:1px solid {c}55;"><span class="bdot" style="background:{c}"></span>{status}</span>'


def fmt_num(x, decimals=0):
    return f"{x:,.{decimals}f}"


def apply_plotly_theme(fig, height=380):
    cc = get_chart_colors()  # background/grid/axis/title/legend/text — Settings-controlled
    bg = cc["background"] if cc["background"] != "transparent" else "rgba(0,0,0,0)"
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font=dict(family="Inter, sans-serif", color=cc["text"], size=12),
        margin=dict(l=10, r=10, t=40, b=10),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=cc["legend"])),
        xaxis=dict(gridcolor=cc["grid"], zerolinecolor=cc["grid"], color=cc["axis_label"]),
        yaxis=dict(gridcolor=cc["grid"], zerolinecolor=cc["grid"], color=cc["axis_label"]),
        title_font=dict(color=cc["title"]),
    )
    return fig



# ---------------------------------------------------------------------------
# Dataset model (SRS §5–§12): one deterministic dataset shared by all pages.
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


@st.cache_data(show_spinner=False)
def load_dataset():
    """Builds the ONE dummy dataset used by every page (SRS §5 files, §9 cleaning
    rules, §11 prioritization). Deterministic seed -> identical numbers everywhere.
    Swap this function body for real CSV/API reads when the backend is ready;
    the returned dict shape is the contract every page relies on."""
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

    # Canonical prioritization decision snapshot (Energy-Aware @ 60% budget) for
    # the Home/Export pages; the Prioritization page lets the user vary this.
    default_budget = 0.60
    canonical_selected = select_tests(scoring, "Energy-Aware (Proposed)", default_budget)
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
        sel = select_tests(scoring, "Random Order" if seed_m else m, default_budget)
        s = summarize(scoring, sel, CARBON_INTENSITY_G_PER_KWH)
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


def knapsack_01(optional, budget_remaining, n_bins=1500):
    """0/1 knapsack maximizing total assurance score within an energy budget,
    solved on a discretized weight grid (DP) — a near-optimal selection used
    for the 'Knapsack (0/1 DP)' prioritization method (SRS §11)."""
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


def select_tests(scoring, method, budget_fraction, rng_seed=7):
    """Selects tests under an energy budget using the requested prioritization
    method (SRS §11). Mandatory tests are always included first (SRS §11)."""
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
        chosen_optional = knapsack_01(optional, budget_remaining) if budget_remaining > 0 else optional.iloc[0:0]
        return pd.concat([mandatory, chosen_optional])
    else:
        raise ValueError(f"Unknown method: {method}")

    if budget_remaining <= 0:
        chosen_optional = optional.iloc[0:0]
    else:
        cum = optional["median_energy_joules"].cumsum()
        chosen_optional = optional[cum <= budget_remaining]
    return pd.concat([mandatory, chosen_optional])


def summarize(scoring, selected, carbon_intensity):
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


# ============================================================================
# ENTRY POINT — app.py
# Streamlit's automatic sidebar navigation is built from files under pages/,
# so the polished "Home" experience lives at pages/1_Home.py (it needs to
# appear as a normal nav item). This file is the app's bootstrap script: it
# configures the page once and immediately hands off to the Home dashboard,
# so opening the app always lands the user on a fully-rendered, correctly
# highlighted Home page rather than a blank entry screen.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester", page_icon="🌱",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_brand()
with st.sidebar:
    st.markdown(
        f'<div class="gat-sidebar-status"><span class="gat-dot"></span>Redirecting to Home…</div>',
        unsafe_allow_html=True,
    )

st.switch_page("pages/1_Home.py")


# NOTE: st.switch_page() above stops execution immediately, so anything
# after it never ran. It was dead code. pages/8_Settings.py already appears
# in the sidebar automatically (Streamlit lists every file under pages/),
# so no extra link is needed here.
