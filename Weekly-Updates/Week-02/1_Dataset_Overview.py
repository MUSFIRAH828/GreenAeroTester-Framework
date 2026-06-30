"""
GreenAeroTester Dashboard - Dataset Overview Page
====================================================
Implements SRS Section 9.4 "Dataset Overview Page" requirements:
  flight phase distribution, weather condition distribution, fault type
  distribution, safety level distribution, mandatory vs optional tests,
  missing-value summary, invalid rows summary.

Place this file at: web/pages/1_Dataset_Overview.py
"""

import pandas as pd
import streamlit as st

from utils import load_dataset, missing_data_notice

st.set_page_config(page_title="Dataset Overview | GreenAeroTester", page_icon="📊", layout="wide")

st.title("📊 Dataset Overview")
st.caption("Distributions and data-quality summary across the scenario and test catalog.")

scenario_parameters = load_dataset("scenario_parameters")
test_catalog = load_dataset("test_catalog")

if scenario_parameters is None and test_catalog is None:
    missing_data_notice("scenario_parameters", "the dataset overview")
    st.stop()

# ---------------------------------------------------------------------------
# Helper: render a value-count bar chart for a column if it exists
# ---------------------------------------------------------------------------
def render_distribution(df: pd.DataFrame, column: str, title: str) -> None:
    st.markdown(f"**{title}**")
    if df is None or column not in df.columns:
        st.caption(f"Column `{column}` not found yet — will appear once scenarios include it.")
        return
    counts = df[column].astype(str).value_counts(dropna=False).rename_axis(column).reset_index(name="count")
    counts.columns = [column, "count"]
    st.bar_chart(counts.set_index(column))


# ---------------------------------------------------------------------------
# Scenario-level distributions
# ---------------------------------------------------------------------------
st.subheader("Scenario Distributions")

dist_cols = st.columns(2)
with dist_cols[0]:
    render_distribution(scenario_parameters, "flight_phase", "Flight Phase Distribution")
with dist_cols[1]:
    render_distribution(scenario_parameters, "weather_condition", "Weather Condition Distribution")

dist_cols2 = st.columns(2)
with dist_cols2[0]:
    render_distribution(scenario_parameters, "failure_type", "Fault / Failure Type Distribution")
with dist_cols2[1]:
    render_distribution(scenario_parameters, "safety_level", "Safety Level Distribution")

st.divider()

# ---------------------------------------------------------------------------
# Mandatory vs optional tests
# ---------------------------------------------------------------------------
st.subheader("Mandatory vs Optional Tests")

if test_catalog is not None and "mandatory_flag" in test_catalog.columns:
    flags = test_catalog["mandatory_flag"].astype(str).str.lower().isin(["true", "1", "yes"])
    mandatory_n = int(flags.sum())
    optional_n = int((~flags).sum())

    c1, c2 = st.columns(2)
    c1.metric("Mandatory Tests", mandatory_n)
    c2.metric("Optional Tests", optional_n)

    chart_df = pd.DataFrame({"category": ["Mandatory", "Optional"], "count": [mandatory_n, optional_n]})
    st.bar_chart(chart_df.set_index("category"))
else:
    st.caption("`test_catalog.csv` with a `mandatory_flag` column is not available yet.")

st.divider()

# ---------------------------------------------------------------------------
# Missing-value summary
# ---------------------------------------------------------------------------
st.subheader("Missing-Value Summary")

tabs = st.tabs(["Scenario Parameters", "Test Catalog"])

for tab, df, name in zip(tabs, [scenario_parameters, test_catalog], ["scenario_parameters.csv", "test_catalog.csv"]):
    with tab:
        if df is None:
            st.caption(f"`{name}` not available yet.")
            continue
        missing = df.isna().sum()
        missing = missing[missing > 0]
        if missing.empty:
            st.success(f"No missing values detected in `{name}`.")
        else:
            missing_df = missing.rename_axis("column").reset_index(name="missing_count")
            missing_df["missing_pct"] = (missing_df["missing_count"] / len(df) * 100).round(2)
            st.dataframe(missing_df, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Invalid rows summary (basic structural checks)
# ---------------------------------------------------------------------------
st.subheader("Invalid Rows Summary")

if scenario_parameters is None:
    st.caption("`scenario_parameters.csv` not available yet — cannot run validity checks.")
else:
    issues = []

    if "scenario_id" in scenario_parameters.columns:
        dup_count = int(scenario_parameters["scenario_id"].duplicated().sum())
        if dup_count > 0:
            issues.append(f"{dup_count} duplicate scenario_id value(s) found.")

    for numeric_col in ("starting_altitude", "starting_airspeed", "duration"):
        if numeric_col in scenario_parameters.columns:
            negative_count = int((pd.to_numeric(scenario_parameters[numeric_col], errors="coerce") < 0).sum())
            if negative_count > 0:
                issues.append(f"{negative_count} row(s) have a negative `{numeric_col}` value.")

    if issues:
        for issue in issues:
            st.warning(issue)
    else:
        st.success("No structural issues detected in the checks currently implemented.")

st.caption(
    "Note: this page performs lightweight, dashboard-side sanity checks. "
    "The authoritative data-quality report is produced by `validators.py` "
    "and stored under `results/reports/`."
)

# ---------------------------------------------------------------------------
# Raw table preview
# ---------------------------------------------------------------------------
with st.expander("🔍 Preview raw scenario_parameters.csv"):
    if scenario_parameters is not None:
        st.dataframe(scenario_parameters.head(100), use_container_width=True)
    else:
        st.caption("Not available yet.")
