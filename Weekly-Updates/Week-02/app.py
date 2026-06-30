"""
GreenAeroTester Dashboard - Home Page
=======================================
Entry point for the Streamlit multipage dashboard. Run with:

    streamlit run web/app.py

Other pages live in web/pages/ and are picked up automatically by
Streamlit's multipage app mechanism (file order controlled by the
"N_Name.py" numeric prefixes).

Implements SRS Section 9.4 "Home Page" requirements:
  total scenarios, total runs, clean runs, total energy, total carbon,
  mandatory tests, failed/timeout runs.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from utils import (
    load_dataset,
    clean_run_summary,
    safe_value,
    get_load_errors,
)

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GreenAeroTester Dashboard",
    page_icon="🛩️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATASET_VERSION = "v0.1-prototype"  # update as the dataset matures

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🛩️ GreenAeroTester Dashboard")
st.caption(
    "Energy-aware validation analytics for FlightGear-based aviation "
    "cyber-physical system testing."
)

col_a, col_b = st.columns([3, 1])
with col_a:
    st.markdown(
        "GreenAeroTester measures the energy and carbon cost of aviation "
        "simulation test scenarios, and uses that data to prioritize tests "
        "by assurance value per unit of energy spent."
    )
with col_b:
    st.metric("Dataset Version", DATASET_VERSION)
    st.caption(f"Last refreshed: {dt.datetime.now():%Y-%m-%d %H:%M}")

st.divider()

# ---------------------------------------------------------------------------
# Load core datasets (each call returns None gracefully if missing)
# ---------------------------------------------------------------------------
test_catalog = load_dataset("test_catalog")
scenario_parameters = load_dataset("scenario_parameters")
test_runs = load_dataset("test_runs")
software_energy = load_dataset("software_energy_metrics")
hardware_energy = load_dataset("hardware_energy_metrics")

run_summary = clean_run_summary(test_runs)

# ---------------------------------------------------------------------------
# Top-level summary cards
# ---------------------------------------------------------------------------
st.subheader("Project Snapshot")

row1 = st.columns(4)
row1[0].metric("Total Scenarios", len(scenario_parameters) if scenario_parameters is not None else "—")
row1[1].metric("Total Runs", run_summary["total"] or "—")
row1[2].metric("Clean Runs", run_summary["clean"] or "—")
failed_timeout_crashed = run_summary["failed"] + run_summary["timeout"] + run_summary["crashed"]
row1[3].metric("Failed / Timeout / Crashed", failed_timeout_crashed or "—")

row2 = st.columns(4)

total_energy_j = None
if software_energy is not None and "energy_joules" in software_energy.columns:
    total_energy_j = software_energy["energy_joules"].sum()
row2[0].metric("Total Software Energy", f"{safe_value(total_energy_j, '{:,.0f}')} J")

total_hw_energy = None
if hardware_energy is not None and "energy_joules" in hardware_energy.columns:
    total_hw_energy = hardware_energy["energy_joules"].sum()
row2[1].metric("Total Hardware Energy", f"{safe_value(total_hw_energy, '{:,.0f}')} J")

total_carbon = None
if software_energy is not None and "estimated_carbon_gco2" in software_energy.columns:
    total_carbon = software_energy["estimated_carbon_gco2"].sum()
row2[2].metric("Estimated Carbon", f"{safe_value(total_carbon, '{:,.1f}')} gCO2")

mandatory_count = None
if test_catalog is not None and "mandatory_flag" in test_catalog.columns:
    mandatory_count = test_catalog["mandatory_flag"].astype(str).str.lower().isin(["true", "1", "yes"]).sum()
row2[3].metric("Mandatory Tests", mandatory_count if mandatory_count is not None else "—")

st.divider()

# ---------------------------------------------------------------------------
# Run status breakdown
# ---------------------------------------------------------------------------
st.subheader("Run Status Breakdown")

if test_runs is None:
    st.info(
        "**test_runs.csv** has not been generated yet. Once the backend "
        "pipeline produces it (in `data/raw/`, `data/processed/`, or "
        "`data/final/`), run status counts will appear here."
    )
else:
    status_cols = st.columns(5)
    status_cols[0].metric("Total", run_summary["total"])
    status_cols[1].metric("Clean", run_summary["clean"])
    status_cols[2].metric("Failed", run_summary["failed"])
    status_cols[3].metric("Timeout", run_summary["timeout"])
    status_cols[4].metric("Crashed", run_summary["crashed"])

    status_df = pd.DataFrame(
        {
            "status": ["Clean", "Failed", "Timeout", "Crashed", "Other/Unmarked"],
            "count": [
                run_summary["clean"],
                run_summary["failed"],
                run_summary["timeout"],
                run_summary["crashed"],
                run_summary["other"],
            ],
        }
    )
    status_df = status_df[status_df["count"] > 0]
    if not status_df.empty:
        st.bar_chart(status_df.set_index("status"))

st.divider()

# ---------------------------------------------------------------------------
# Navigation help
# ---------------------------------------------------------------------------
st.subheader("Explore the Dashboard")
nav_cols = st.columns(3)
nav_cols[0].markdown(
    "**📊 Dataset Overview**\n\nFlight phase, weather, fault type, safety "
    "level, and missing-value summaries."
)
nav_cols[1].markdown(
    "**⚡ Energy Results**\n\nRuntime, power, energy, carbon, and "
    "run-to-run variation per test."
)
nav_cols[2].markdown(
    "**🏆 Prioritization & Baselines**\n\nCompare proposed energy-aware "
    "ranking against baseline methods."
)
st.caption("Use the sidebar to navigate between pages.")

# ---------------------------------------------------------------------------
# Diagnostics (load errors), shown last and collapsed so it doesn't clutter
# ---------------------------------------------------------------------------
errors = get_load_errors()
if errors:
    with st.expander("⚠️ Data loading issues", expanded=False):
        for err in errors:
            st.warning(err)
