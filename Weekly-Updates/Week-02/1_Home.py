"""
GreenAeroTester - Home Dashboard
===================================
Premium industrial analytics overview of the whole GreenAeroTester pipeline.
Currently powered by realistic, seeded dummy data. Every widget is structured
so that swapping the dummy generators for real backend CSV loaders
(test_runs.csv, software_energy_metrics.csv, hardware_energy_metrics.csv,
merged_energy_metrics.csv) requires no layout changes.
"""

import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ----------------------------------------------------------------------------
# PAGE CONFIG + THEME (re-applied per page, Streamlit re-runs each script)
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Home | GreenAeroTester", page_icon="📊", layout="wide")

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root {
    --bg-primary:#0B1120; --bg-surface:#131B2E; --bg-surface-2:#0F1729; --border-color:#1F2A44;
    --accent-teal:#2DD4BF; --accent-amber:#F59E0B; --accent-danger:#EF4444; --accent-success:#22C55E;
    --text-primary:#E5E7EB; --text-muted:#94A3B8;
}
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
.gat-card .delta-up { color:var(--accent-success); font-size:0.76rem; }
.gat-card .delta-down { color:var(--accent-danger); font-size:0.76rem; }
.gat-card .delta-flat { color:var(--text-muted); font-size:0.76rem; }
.gat-status-row { display:flex; align-items:center; justify-content:space-between; padding:9px 4px; border-bottom:1px solid var(--border-color); }
.gat-status-row:last-child { border-bottom:none; }
.gat-status-label { color:var(--text-muted); font-size:0.82rem; }
.gat-section-title { color:var(--text-primary); font-size:1.05rem; font-weight:700; margin:26px 0 12px 0; padding-left:10px; border-left:3px solid var(--accent-teal); }
.gat-footer { margin-top:40px; padding:16px 0; border-top:1px solid var(--border-color); color:var(--text-muted); font-size:0.75rem; text-align:center; }
div[data-testid="stMetric"] { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:12px; padding:14px 16px; }
div[data-testid="stMetricValue"] { color:var(--text-primary); font-family:'JetBrains Mono',monospace; }
div[data-testid="stMetricLabel"] { color:var(--text-muted); }
.stButton>button { background:var(--bg-surface); color:var(--text-primary); border:1px solid var(--border-color); border-radius:10px; font-weight:600; width:100%; }
.stButton>button:hover { border-color:var(--accent-teal); color:var(--accent-teal); }
div[data-testid="stExpander"] { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:12px; }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"
COLOR_SEQ = ["#2DD4BF", "#F59E0B", "#60A5FA", "#F472B6", "#A78BFA", "#4ADE80"]
STATUS_COLORS = {"Clean": "#22C55E", "Failed": "#EF4444", "Timeout": "#F59E0B", "Crashed": "#94A3B8"}


def style_fig(fig, height=360):
    """Apply consistent dark-dashboard styling to every Plotly figure."""
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#E5E7EB", size=12),
        margin=dict(l=10, r=10, t=40, b=10),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def metric_card(label, value, delta=None, delta_type="flat"):
    delta_html = f'<div class="delta-{delta_type}">{delta}</div>' if delta else ""
    st.markdown(
        f"""<div class="gat-card"><div class="label">{label}</div>
        <div class="value">{value}</div>{delta_html}</div>""",
        unsafe_allow_html=True,
    )


def status_row(label, badge_html):
    st.markdown(
        f"""<div class="gat-status-row"><span class="gat-status-label">{label}</span>{badge_html}</div>""",
        unsafe_allow_html=True,
    )


def badge(text, kind):
    return f'<span class="gat-badge badge-{kind}">{text}</span>'


# ----------------------------------------------------------------------------
# DUMMY DATA GENERATION (seeded -> stable across reruns, cached for speed)
# ----------------------------------------------------------------------------
@st.cache_data
def generate_run_dataset(n_runs: int = 320, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    flight_phases = ["Takeoff", "Climb", "Cruise", "Descent", "Approach", "Landing"]
    statuses = ["Clean", "Failed", "Timeout", "Crashed"]
    status_p = [0.78, 0.10, 0.07, 0.05]

    n_scenarios = 42
    scenario_ids = [f"S{i:04d}" for i in range(1, n_scenarios + 1)]

    run_status = rng.choice(statuses, size=n_runs, p=status_p)
    runtime = np.clip(rng.normal(180, 45, n_runs), 40, None)
    cpu_avg = np.clip(rng.normal(55, 15, n_runs), 5, 100)
    mem_avg = np.clip(rng.normal(1450, 300, n_runs), 200, None)
    sw_power = np.clip(rng.normal(38, 9, n_runs), 5, None)
    sw_energy_wh = sw_power * (runtime / 3600)
    hw_available_mask = rng.random(n_runs) < 0.55  # simulate ESP32 not always connected
    hw_energy_wh = np.where(
        hw_available_mask, sw_energy_wh * rng.normal(1.12, 0.08, n_runs), np.nan
    )
    carbon_intensity = 442  # gCO2/kWh, illustrative grid factor
    carbon_g = (sw_energy_wh / 1000) * carbon_intensity

    dates = [datetime.now() - timedelta(hours=int(h)) for h in rng.integers(0, 24 * 14, n_runs)]

    df = pd.DataFrame(
        {
            "run_id": [f"R{i:06d}" for i in range(1, n_runs + 1)],
            "scenario_id": rng.choice(scenario_ids, size=n_runs),
            "test_id": [f"T{i:04d}" for i in rng.integers(1, 250, n_runs)],
            "flight_phase": rng.choice(flight_phases, size=n_runs),
            "status": run_status,
            "runtime_s": runtime.round(1),
            "cpu_avg_pct": cpu_avg.round(1),
            "memory_avg_mb": mem_avg.round(1),
            "software_energy_wh": sw_energy_wh.round(3),
            "hardware_energy_wh": np.round(hw_energy_wh, 3),
            "carbon_g": carbon_g.round(2),
            "mandatory": rng.random(n_runs) < 0.32,
            "timestamp": dates,
        }
    )
    return df.sort_values("timestamp", ascending=False).reset_index(drop=True)


df = generate_run_dataset()

# ----------------------------------------------------------------------------
# DEFENSIVE SESSION STATE (in case this page is opened directly, without
# first visiting app.py, e.g. via a bookmarked URL)
# ----------------------------------------------------------------------------
_home_defaults = {
    "backend_connected": False,
    "flightgear_status": "offline",
    "hardware_meter_status": "pending",
    "dataset_loaded": True,
    "simulation_running": False,
    "simulation_progress": 0,
    "current_algorithm": "Energy Aware",
    "energy_budget": 500.0,
    "last_refresh": datetime.now(),
    "app_version": "v0.1.0-frontend-preview",
}
for _key, _value in _home_defaults.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div>
            <h1>📊 Mission Control · Home</h1>
            <p>Live overview of simulation runs, energy consumption, and carbon impact across the test suite</p>
        </div>
        <span class="gat-badge badge-pending">DUMMY DATA · BACKEND OFFLINE</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# SUMMARY CARDS (10 required cards)
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Summary</div>', unsafe_allow_html=True)

total_scenarios = df["scenario_id"].nunique()
total_runs = len(df)
clean_runs = int((df["status"] == "Clean").sum())
failed_runs = int((df["status"] == "Failed").sum())
timeout_runs = int((df["status"] == "Timeout").sum())
crashed_runs = int((df["status"] == "Crashed").sum())
total_sw_energy = df["software_energy_wh"].sum()
hw_values = df["hardware_energy_wh"].dropna()
total_hw_energy = hw_values.sum() if len(hw_values) > 0 else None
total_carbon = df["carbon_g"].sum()
mandatory_tests = int(df["mandatory"].sum())

row1 = st.columns(5)
with row1[0]:
    metric_card("Total Scenarios", f"{total_scenarios}", "Active in catalog", "flat")
with row1[1]:
    metric_card("Total Runs", f"{total_runs:,}", "Last 14 days", "flat")
with row1[2]:
    metric_card("Clean Runs", f"{clean_runs:,}", f"{clean_runs/total_runs:.0%} pass rate", "up")
with row1[3]:
    metric_card("Failed Runs", f"{failed_runs:,}", f"{failed_runs/total_runs:.0%} of total", "down")
with row1[4]:
    metric_card("Timeout Runs", f"{timeout_runs:,}", f"{timeout_runs/total_runs:.0%} of total", "down")

row2 = st.columns(5)
with row2[0]:
    metric_card("Crashed Runs", f"{crashed_runs:,}", f"{crashed_runs/total_runs:.0%} of total", "down")
with row2[1]:
    metric_card("Total Software Energy", f"{total_sw_energy:,.1f} Wh", "CodeCarbon / psutil estimate", "flat")
with row2[2]:
    if total_hw_energy is not None:
        metric_card("Total Hardware Energy", f"{total_hw_energy:,.1f} Wh", "ESP32 power meter", "flat")
    else:
        metric_card("Total Hardware Energy", "Pending", "Not Connected Yet", "flat")
with row2[3]:
    metric_card("Est. Carbon Emissions", f"{total_carbon/1000:,.2f} kg CO₂e", "Grid factor 442 gCO₂/kWh", "flat")
with row2[4]:
    metric_card("Mandatory Tests", f"{mandatory_tests:,}", "Always selected", "flat")

# ----------------------------------------------------------------------------
# SYSTEM STATUS PANEL
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">System Status</div>', unsafe_allow_html=True)
status_col, action_col = st.columns([1.3, 1])

with status_col:
    st.markdown('<div class="gat-card">', unsafe_allow_html=True)
    status_row("Backend Status", badge("OFFLINE" if not st.session_state.backend_connected else "ONLINE",
                                        "offline" if not st.session_state.backend_connected else "online"))
    status_row("FlightGear Status", badge(st.session_state.flightgear_status.upper(),
                                           "offline" if st.session_state.flightgear_status == "offline" else "online"))
    status_row("Hardware Meter Status", badge(st.session_state.hardware_meter_status.upper(), "pending"))
    status_row("Dataset Status", badge("LOADED (DUMMY)" if st.session_state.dataset_loaded else "MISSING", "online"))
    status_row("Simulation Status", badge("RUNNING" if st.session_state.simulation_running else "IDLE",
                                           "pending" if st.session_state.simulation_running else "offline"))
    status_row("Current Algorithm", badge(st.session_state.current_algorithm.upper(), "online"))
    status_row("Last Refresh Time", badge(st.session_state.last_refresh.strftime("%H:%M:%S"), "pending"))
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# ACTION BUTTONS + SIMULATION PROGRESS
# ----------------------------------------------------------------------------
with action_col:
    st.markdown('<div class="gat-card">', unsafe_allow_html=True)
    st.markdown('<span class="gat-status-label">QUICK ACTIONS</span>', unsafe_allow_html=True)
    st.write("")
    b1, b2 = st.columns(2)
    b3, b4 = st.columns(2)
    run_clicked = b1.button("▶️ Run Simulation", use_container_width=True)
    refresh_clicked = b2.button("🔄 Refresh Dashboard", use_container_width=True)
    report_clicked = b3.button("📄 Generate Report", use_container_width=True)
    export_clicked = b4.button("⬇️ Export CSV", use_container_width=True)
    reset_clicked = st.button("♻️ Reset Dashboard", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if refresh_clicked:
        st.session_state.last_refresh = datetime.now()
        st.cache_data.clear()
        st.toast("Dashboard refreshed with the latest dummy data snapshot.")
        st.rerun()

    if report_clicked:
        st.toast("Report generation queued. Backend reporting.py will produce the real PDF/HTML.")

    if export_clicked:
        st.toast("Use the Export Center page for full download options.")

    if reset_clicked:
        for key in ["simulation_running", "simulation_progress"]:
            st.session_state[key] = _defaults_reset = 0 if key == "simulation_progress" else False
        st.cache_data.clear()
        st.toast("Dashboard state has been reset.")
        st.rerun()

    if run_clicked:
        st.session_state.simulation_running = True

# Simulation progress simulation (visual only - no backend yet)
if st.session_state.simulation_running:
    st.markdown('<div class="gat-section-title">Simulation Progress</div>', unsafe_allow_html=True)
    stages = [
        "Initializing", "Loading Scenario", "Launching FlightGear", "Collecting Runtime",
        "Collecting CPU", "Collecting Memory", "Calculating Software Energy",
        "Calculating Hardware Energy", "Calculating Carbon", "Generating Report", "Completed",
    ]
    progress_bar = st.progress(0, text=stages[0])
    status_placeholder = st.empty()
    for i, stage in enumerate(stages):
        pct = int(((i + 1) / len(stages)) * 100)
        progress_bar.progress(pct, text=f"{stage} ({pct}%)")
        status_placeholder.caption(f"Step {i+1}/{len(stages)}: {stage} — visual simulation, backend not connected yet.")
        time.sleep(0.18)
    st.success("Simulation sequence completed (visual demo only). Connect the backend to run real scenarios.")
    st.session_state.simulation_running = False

# ----------------------------------------------------------------------------
# CHARTS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Analytics</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    status_counts = df["status"].value_counts().reindex(["Clean", "Failed", "Timeout", "Crashed"]).fillna(0)
    fig = go.Figure(
        go.Bar(
            x=status_counts.index, y=status_counts.values,
            marker_color=[STATUS_COLORS[s] for s in status_counts.index],
        )
    )
    fig.update_layout(title="Runs by Status")
    st.plotly_chart(style_fig(fig, 320), use_container_width=True)

with c2:
    phase_counts = df["flight_phase"].value_counts()
    fig = px.pie(
        names=phase_counts.index, values=phase_counts.values, hole=0.5,
        color_discrete_sequence=COLOR_SEQ, title="Flight Phase Distribution",
    )
    st.plotly_chart(style_fig(fig, 320), use_container_width=True)

trend_df = df.sort_values("timestamp").copy()
trend_df["run_index"] = range(1, len(trend_df) + 1)

c3, c4 = st.columns(2)
with c3:
    fig = px.line(trend_df, x="timestamp", y="runtime_s", title="Runtime Trend (s)",
                   color_discrete_sequence=["#2DD4BF"])
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)
with c4:
    fig = px.line(trend_df, x="timestamp", y="cpu_avg_pct", title="CPU Usage Trend (%)",
                   color_discrete_sequence=["#F59E0B"])
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)

c5, c6 = st.columns(2)
with c5:
    fig = px.line(trend_df, x="timestamp", y="memory_avg_mb", title="Memory Usage Trend (MB)",
                   color_discrete_sequence=["#60A5FA"])
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)
with c6:
    fig = px.line(trend_df, x="timestamp", y="software_energy_wh", title="Software Energy Trend (Wh)",
                   color_discrete_sequence=["#4ADE80"])
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)

c7, c8 = st.columns(2)
with c7:
    hw_trend = trend_df.dropna(subset=["hardware_energy_wh"])
    if len(hw_trend) > 0:
        fig = px.line(hw_trend, x="timestamp", y="hardware_energy_wh", title="Hardware Energy Trend (Wh)",
                       color_discrete_sequence=["#A78BFA"])
        st.plotly_chart(style_fig(fig, 300), use_container_width=True)
    else:
        st.info("Hardware Energy Trend: Pending — ESP32 power meter not connected yet.")
with c8:
    fig = px.line(trend_df, x="timestamp", y="carbon_g", title="Carbon Trend (g CO₂e)",
                   color_discrete_sequence=["#F472B6"])
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)

c9, c10 = st.columns(2)
with c9:
    fig = px.histogram(df, x="software_energy_wh", nbins=30, title="Energy Distribution (Wh)",
                        color_discrete_sequence=["#2DD4BF"])
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)
with c10:
    mand_counts = df["mandatory"].value_counts().rename({True: "Mandatory", False: "Optional"})
    fig = px.pie(names=mand_counts.index, values=mand_counts.values, hole=0.5,
                 color_discrete_sequence=["#F59E0B", "#1F2A44"], title="Mandatory vs Optional Tests")
    st.plotly_chart(style_fig(fig, 300), use_container_width=True)

# ----------------------------------------------------------------------------
# TABLES
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Activity & Alerts</div>', unsafe_allow_html=True)

t1, t2 = st.columns([1.4, 1])
with t1:
    st.markdown("**Recent Activity**")
    recent = df[["run_id", "scenario_id", "status", "flight_phase", "runtime_s", "timestamp"]].head(10)
    st.dataframe(recent, use_container_width=True, hide_index=True)

with t2:
    st.markdown("**Current Alerts**")
    alerts = pd.DataFrame(
        {
            "Severity": ["High", "Medium", "Medium", "Low"],
            "Message": [
                f"{crashed_runs} runs crashed in the last 14 days",
                "Hardware power meter offline for ~45% of runs",
                "3 scenarios missing safety-level metadata",
                "Dataset last synced from dummy generator",
            ],
        }
    )
    st.dataframe(alerts, use_container_width=True, hide_index=True)

st.markdown("**Upcoming Scheduled Simulations**")
upcoming = pd.DataFrame(
    {
        "Scenario ID": [f"S{i:04d}" for i in [7, 12, 19, 25]],
        "Flight Phase": ["Cruise", "Approach", "Takeoff", "Landing"],
        "Scheduled For": [(datetime.now() + timedelta(hours=h)).strftime("%Y-%m-%d %H:%M") for h in [2, 6, 24, 30]],
        "Priority": ["Mandatory", "Optional", "Mandatory", "Optional"],
    }
)
st.dataframe(upcoming, use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# QUICK STATISTICS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Quick Statistics</div>', unsafe_allow_html=True)
q1, q2, q3, q4, q5, q6 = st.columns(6)
q1.metric("Avg Runtime", f"{df['runtime_s'].mean():.1f} s")
q2.metric("Avg Energy", f"{df['software_energy_wh'].mean():.2f} Wh")
q3.metric("Avg Carbon", f"{df['carbon_g'].mean():.2f} g")
q4.metric("Max Runtime", f"{df['runtime_s'].max():.1f} s")
q5.metric("Max Energy", f"{df['software_energy_wh'].max():.2f} Wh")
q6.metric("Max Carbon", f"{df['carbon_g'].max():.2f} g")

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown(
    f"""<div class="gat-footer">GreenAeroTester Dashboard &middot; Home &middot; Data refreshed {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}</div>""",
    unsafe_allow_html=True,
)
