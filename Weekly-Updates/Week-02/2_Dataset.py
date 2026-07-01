"""
GreenAeroTester - Dataset Page
=================================
Gives users a full view of the structured test dataset: summary, statistics,
search/filter tools, data-quality checks (missing values, duplicates,
invalid rows), a live preview, CSV export, and distribution charts.

Dummy data stands in for the real linked CSV files described in the SRS
(test_catalog.csv, scenario_parameters.csv, test_runs.csv, ...).
"""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Dataset | GreenAeroTester", page_icon="🗂️", layout="wide")

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root { --bg-primary:#0B1120; --bg-surface:#131B2E; --bg-surface-2:#0F1729; --border-color:#1F2A44;
    --accent-teal:#2DD4BF; --accent-amber:#F59E0B; --accent-danger:#EF4444; --accent-success:#22C55E;
    --text-primary:#E5E7EB; --text-muted:#94A3B8; }
html, body, [class*="css"] { font-family:'Inter',sans-serif; }
.stApp { background-color: var(--bg-primary); }
section[data-testid="stSidebar"] { background-color: var(--bg-surface-2); border-right:1px solid var(--border-color); }
.gat-header { display:flex; align-items:center; justify-content:space-between; padding:20px 24px; margin-bottom:22px;
    border-radius:14px; background:linear-gradient(135deg,#0F1729 0%,#131B2E 100%); border:1px solid var(--border-color); }
.gat-header h1 { color:var(--text-primary); font-size:1.6rem; font-weight:800; margin:0; }
.gat-header p { color:var(--text-muted); font-size:0.85rem; margin:4px 0 0 0; }
.gat-badge { font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:600; padding:4px 10px; border-radius:20px; letter-spacing:0.03em; }
.badge-online { background:rgba(34,197,94,0.15); color:var(--accent-success); border:1px solid rgba(34,197,94,0.3); }
.badge-offline { background:rgba(239,68,68,0.15); color:var(--accent-danger); border:1px solid rgba(239,68,68,0.3); }
.badge-pending { background:rgba(245,158,11,0.15); color:var(--accent-amber); border:1px solid rgba(245,158,11,0.3); }
.gat-card { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:14px; padding:16px 18px; height:100%; }
.gat-card .label { color:var(--text-muted); font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; }
.gat-card .value { color:var(--text-primary); font-family:'JetBrains Mono',monospace; font-size:1.55rem; font-weight:700; margin:6px 0 2px 0; }
.gat-section-title { color:var(--text-primary); font-size:1.05rem; font-weight:700; margin:26px 0 12px 0; padding-left:10px; border-left:3px solid var(--accent-teal); }
.gat-footer { margin-top:40px; padding:16px 0; border-top:1px solid var(--border-color); color:var(--text-muted); font-size:0.75rem; text-align:center; }
div[data-testid="stMetric"] { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:12px; padding:14px 16px; }
div[data-testid="stMetricValue"] { color:var(--text-primary); font-family:'JetBrains Mono',monospace; }
div[data-testid="stMetricLabel"] { color:var(--text-muted); }
.stButton>button { background:var(--bg-surface); color:var(--text-primary); border:1px solid var(--border-color); border-radius:10px; font-weight:600; }
.stButton>button:hover { border-color:var(--accent-teal); color:var(--accent-teal); }
div[data-testid="stExpander"] { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:12px; }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"
COLOR_SEQ = ["#2DD4BF", "#F59E0B", "#60A5FA", "#F472B6", "#A78BFA", "#4ADE80", "#FCA5A5"]


def style_fig(fig, height=340):
    fig.update_layout(
        template=PLOTLY_TEMPLATE, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#E5E7EB", size=12),
        margin=dict(l=10, r=10, t=40, b=10), height=height,
    )
    return fig


def metric_card(label, value, sub=""):
    st.markdown(
        f"""<div class="gat-card"><div class="label">{label}</div>
        <div class="value">{value}</div><div style="color:var(--text-muted);font-size:0.76rem;">{sub}</div></div>""",
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# DUMMY DATASET (mirrors the merged/final dataset shape from the SRS)
# ----------------------------------------------------------------------------
@st.cache_data
def generate_full_dataset(n: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    flight_phases = ["Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing"]
    weather = ["Clear", "Windy", "Rain", "Fog", "Storm", "Snow"]
    fault_types = ["None", "Sensor Fault", "Engine Fault", "Control Surface Fault", "GPS Loss"]
    safety_levels = ["A", "B", "C", "D"]
    statuses = ["Clean", "Failed", "Timeout", "Crashed"]

    df = pd.DataFrame(
        {
            "run_id": [f"R{i:06d}" for i in range(1, n + 1)],
            "scenario_id": rng.choice([f"S{i:04d}" for i in range(1, 46)], size=n),
            "test_id": [f"T{i:04d}" for i in rng.integers(1, 260, n)],
            "flight_phase": rng.choice(flight_phases, size=n),
            "weather": rng.choice(weather, size=n, p=[0.4, 0.15, 0.15, 0.12, 0.1, 0.08]),
            "fault_type": rng.choice(fault_types, size=n, p=[0.55, 0.15, 0.12, 0.1, 0.08]),
            "safety_level": rng.choice(safety_levels, size=n, p=[0.2, 0.3, 0.3, 0.2]),
            "status": rng.choice(statuses, size=n, p=[0.78, 0.1, 0.07, 0.05]),
            "mandatory": rng.random(n) < 0.32,
            "runtime_s": np.clip(rng.normal(180, 45, n), 20, None).round(1),
            "software_energy_wh": np.clip(rng.normal(1.9, 0.6, n), 0.1, None).round(3),
        }
    )

    # Inject realistic data-quality issues for the demo
    missing_idx = rng.choice(n, size=int(n * 0.05), replace=False)
    df.loc[missing_idx, "weather"] = np.nan
    missing_idx2 = rng.choice(n, size=int(n * 0.03), replace=False)
    df.loc[missing_idx2, "safety_level"] = np.nan

    dup_rows = df.sample(int(n * 0.02), random_state=seed)
    df = pd.concat([df, dup_rows], ignore_index=True)

    invalid_idx = rng.choice(len(df), size=int(n * 0.02), replace=False)
    df.loc[invalid_idx, "runtime_s"] = -1  # invalid negative runtime

    return df


df = generate_full_dataset()

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div><h1>🗂️ Dataset</h1><p>Structured, linked test dataset covering scenarios, runs, faults, and energy metrics</p></div>
        <span class="gat-badge badge-pending">DUMMY DATA</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# DATASET SUMMARY
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Dataset Summary</div>', unsafe_allow_html=True)
s1, s2, s3, s4, s5 = st.columns(5)
with s1:
    metric_card("Total Rows", f"{len(df):,}", "merged_energy_metrics.csv")
with s2:
    metric_card("Unique Scenarios", f"{df['scenario_id'].nunique()}", "test_catalog.csv")
with s3:
    metric_card("Unique Tests", f"{df['test_id'].nunique()}", "linked test IDs")
with s4:
    metric_card("Mandatory Tests", f"{int(df['mandatory'].sum())}", "always selected")
with s5:
    metric_card("Dataset Version", "v0.1-dummy", "auto-generated preview")

# ----------------------------------------------------------------------------
# DATASET STATISTICS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Dataset Statistics</div>', unsafe_allow_html=True)
with st.expander("Numeric column statistics", expanded=True):
    st.dataframe(df[["runtime_s", "software_energy_wh"]].describe().T, use_container_width=True)

# ----------------------------------------------------------------------------
# SEARCH + FILTERS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Search & Filters</div>', unsafe_allow_html=True)
search_term = st.text_input("🔍 Search by Run ID, Scenario ID, or Test ID")

f1, f2, f3, f4, f5 = st.columns(5)
phase_filter = f1.multiselect("Flight Phase", sorted(df["flight_phase"].unique()))
weather_filter = f2.multiselect("Weather", sorted(df["weather"].dropna().unique()))
fault_filter = f3.multiselect("Fault Type", sorted(df["fault_type"].unique()))
safety_filter = f4.multiselect("Safety Level", sorted(df["safety_level"].dropna().unique()))
status_filter = f5.multiselect("Run Status", sorted(df["status"].unique()))

filtered = df.copy()
if search_term:
    mask = (
        filtered["run_id"].str.contains(search_term, case=False, na=False)
        | filtered["scenario_id"].str.contains(search_term, case=False, na=False)
        | filtered["test_id"].str.contains(search_term, case=False, na=False)
    )
    filtered = filtered[mask]
if phase_filter:
    filtered = filtered[filtered["flight_phase"].isin(phase_filter)]
if weather_filter:
    filtered = filtered[filtered["weather"].isin(weather_filter)]
if fault_filter:
    filtered = filtered[filtered["fault_type"].isin(fault_filter)]
if safety_filter:
    filtered = filtered[filtered["safety_level"].isin(safety_filter)]
if status_filter:
    filtered = filtered[filtered["status"].isin(status_filter)]

st.caption(f"Showing {len(filtered):,} of {len(df):,} rows after filters.")

# ----------------------------------------------------------------------------
# DATA QUALITY: MISSING VALUES / DUPLICATES / INVALID ROWS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Data Quality</div>', unsafe_allow_html=True)
dq1, dq2, dq3 = st.columns(3)

missing_counts = df.isna().sum()
missing_total = int(missing_counts.sum())
duplicate_total = int(df.duplicated().sum())
invalid_total = int((df["runtime_s"] < 0).sum())

with dq1:
    metric_card("Missing Values", f"{missing_total:,}", "cells across all columns")
with dq2:
    metric_card("Duplicate Rows", f"{duplicate_total:,}", "exact duplicate records")
with dq3:
    metric_card("Invalid Rows", f"{invalid_total:,}", "e.g. negative runtime")

with st.expander("Missing values by column"):
    st.dataframe(missing_counts[missing_counts > 0].rename("Missing Count"), use_container_width=True)
with st.expander("Duplicate rows preview"):
    st.dataframe(df[df.duplicated(keep=False)].head(20), use_container_width=True, hide_index=True)
with st.expander("Invalid rows preview (negative runtime)"):
    st.dataframe(df[df["runtime_s"] < 0], use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# DATASET PREVIEW + DOWNLOAD
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Dataset Preview</div>', unsafe_allow_html=True)
st.dataframe(filtered.head(200), use_container_width=True, hide_index=True)

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download Filtered Dataset as CSV",
    data=csv_bytes,
    file_name="greenaerotester_dataset_preview.csv",
    mime="text/csv",
)

# ----------------------------------------------------------------------------
# PROFESSIONAL CHARTS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Distribution Charts</div>', unsafe_allow_html=True)
g1, g2 = st.columns(2)
with g1:
    fig = px.bar(df["flight_phase"].value_counts(), title="Flight Phase Distribution", color_discrete_sequence=COLOR_SEQ)
    st.plotly_chart(style_fig(fig), use_container_width=True)
with g2:
    fig = px.bar(df["weather"].value_counts(), title="Weather Condition Distribution", color_discrete_sequence=COLOR_SEQ)
    st.plotly_chart(style_fig(fig), use_container_width=True)

g3, g4 = st.columns(2)
with g3:
    fig = px.bar(df["fault_type"].value_counts(), title="Fault Type Distribution", color_discrete_sequence=COLOR_SEQ)
    st.plotly_chart(style_fig(fig), use_container_width=True)
with g4:
    fig = px.bar(df["safety_level"].value_counts().sort_index(), title="Safety Level Distribution", color_discrete_sequence=COLOR_SEQ)
    st.plotly_chart(style_fig(fig), use_container_width=True)

g5, g6 = st.columns(2)
with g5:
    mand_counts = df["mandatory"].value_counts().rename({True: "Mandatory", False: "Optional"})
    fig = px.pie(names=mand_counts.index, values=mand_counts.values, hole=0.5,
                 title="Mandatory vs Optional Tests", color_discrete_sequence=["#F59E0B", "#1F2A44"])
    st.plotly_chart(style_fig(fig), use_container_width=True)
with g6:
    fig = px.histogram(df, x="software_energy_wh", nbins=30, title="Software Energy Distribution (Wh)",
                        color_discrete_sequence=["#2DD4BF"])
    st.plotly_chart(style_fig(fig), use_container_width=True)

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown(
    """<div class="gat-footer">GreenAeroTester Dashboard &middot; Dataset</div>""",
    unsafe_allow_html=True,
)
