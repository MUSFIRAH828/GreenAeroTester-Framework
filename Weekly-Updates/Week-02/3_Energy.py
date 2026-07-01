"""
GreenAeroTester - Energy Page
================================
Consolidates the SRS's Software Energy, Hardware Energy, and Software-vs-
Hardware Comparison pages into one Energy workspace using tabs, plus a
top-level summary covering runtime, CPU, memory, software/hardware energy,
power, and carbon.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Energy | GreenAeroTester", page_icon="⚡", layout="wide")

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
div[data-testid="stExpander"] { background:var(--bg-surface); border:1px solid var(--border-color); border-radius:12px; }
button[data-baseweb="tab"] { color: var(--text-muted); }
hr { border-color: var(--border-color); }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"


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
# DUMMY ENERGY DATASET (software + hardware streams, per SRS field lists)
# ----------------------------------------------------------------------------
@st.cache_data
def generate_energy_dataset(n: int = 260, seed: int = 21) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    tests = [f"T{i:04d}" for i in range(1, 61)]

    runtime = np.clip(rng.normal(180, 40, n), 30, None)
    cpu_avg = np.clip(rng.normal(52, 14, n), 5, 100)
    cpu_peak = np.clip(cpu_avg + rng.normal(20, 6, n), cpu_avg, 100)
    mem_avg = np.clip(rng.normal(1400, 260, n), 200, None)
    mem_peak = mem_avg + np.clip(rng.normal(300, 80, n), 0, None)
    sw_power_avg = np.clip(rng.normal(37, 8, n), 5, None)
    sw_power_peak = sw_power_avg + np.clip(rng.normal(12, 4, n), 0, None)
    sw_energy_wh = sw_power_avg * (runtime / 3600)
    sw_energy_j = sw_energy_wh * 3600

    hw_available = rng.random(n) < 0.55
    hw_voltage = np.where(hw_available, rng.normal(230, 3, n), np.nan)
    hw_current = np.where(hw_available, rng.normal(0.9, 0.15, n), np.nan)
    hw_power = np.where(hw_available, hw_voltage * hw_current * rng.normal(0.95, 0.02, n), np.nan)
    hw_energy_wh = np.where(hw_available, hw_power * (runtime / 3600), np.nan)
    hw_freq = np.where(hw_available, rng.normal(50, 0.2, n), np.nan)
    hw_pf = np.where(hw_available, np.clip(rng.normal(0.95, 0.02, n), 0.8, 1.0), np.nan)

    carbon_intensity = 442
    carbon_g = (sw_energy_wh / 1000) * carbon_intensity

    df = pd.DataFrame(
        {
            "run_id": [f"R{i:06d}" for i in range(1, n + 1)],
            "test_id": rng.choice(tests, size=n),
            "runtime_s": runtime.round(1),
            "cpu_avg_pct": cpu_avg.round(1),
            "cpu_peak_pct": cpu_peak.round(1),
            "memory_avg_mb": mem_avg.round(1),
            "memory_peak_mb": mem_peak.round(1),
            "sw_power_avg_w": sw_power_avg.round(2),
            "sw_power_peak_w": sw_power_peak.round(2),
            "software_energy_wh": sw_energy_wh.round(3),
            "software_energy_j": sw_energy_j.round(1),
            "hardware_voltage_v": np.round(hw_voltage, 2),
            "hardware_current_a": np.round(hw_current, 3),
            "hardware_power_w": np.round(hw_power, 2),
            "hardware_energy_wh": np.round(hw_energy_wh, 3),
            "hardware_frequency_hz": np.round(hw_freq, 2),
            "hardware_power_factor": np.round(hw_pf, 3),
            "carbon_g": carbon_g.round(2),
        }
    )
    return df


energy_df = generate_energy_dataset()

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown(
    """
    <div class="gat-header">
        <div><h1>⚡ Energy</h1><p>Runtime, resource usage, software & hardware energy, power, and carbon impact</p></div>
        <span class="gat-badge badge-pending">DUMMY DATA</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# TOP-LEVEL SUMMARY CARDS
# ----------------------------------------------------------------------------
st.markdown('<div class="gat-section-title">Summary</div>', unsafe_allow_html=True)
hw_present = energy_df["hardware_energy_wh"].dropna()
m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
with m1:
    metric_card("Avg Runtime", f"{energy_df['runtime_s'].mean():.1f} s")
with m2:
    metric_card("Avg CPU Usage", f"{energy_df['cpu_avg_pct'].mean():.1f} %")
with m3:
    metric_card("Avg Memory", f"{energy_df['memory_avg_mb'].mean():.0f} MB")
with m4:
    metric_card("Total Software Energy", f"{energy_df['software_energy_wh'].sum():.1f} Wh")
with m5:
    metric_card("Total Hardware Energy", f"{hw_present.sum():.1f} Wh" if len(hw_present) else "Pending")
with m6:
    metric_card("Avg Power", f"{energy_df['sw_power_avg_w'].mean():.1f} W")
with m7:
    metric_card("Total Carbon", f"{energy_df['carbon_g'].sum()/1000:.2f} kg CO₂e")

# ----------------------------------------------------------------------------
# TABS: SOFTWARE ENERGY / HARDWARE ENERGY / SOFTWARE VS HARDWARE COMPARISON
# ----------------------------------------------------------------------------
tab_sw, tab_hw, tab_cmp = st.tabs(["🖥️ Software Energy", "🔌 Hardware Energy", "🔀 Software vs Hardware"])

# --- Software Energy tab -----------------------------------------------------
with tab_sw:
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(energy_df, x="run_id", y="cpu_avg_pct", title="CPU Usage per Run",
                          color_discrete_sequence=["#2DD4BF"])
        fig.update_xaxes(showticklabels=False)
        st.plotly_chart(style_fig(fig), use_container_width=True)
    with c2:
        runtime_by_test = energy_df.groupby("test_id")["runtime_s"].mean().sort_values(ascending=False).head(15)
        fig = px.bar(runtime_by_test, title="Runtime per Test (Top 15, avg s)", color_discrete_sequence=["#F59E0B"])
        st.plotly_chart(style_fig(fig), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        power_by_test = energy_df.groupby("test_id")["sw_power_avg_w"].mean().sort_values(ascending=False).head(15)
        fig = px.bar(power_by_test, title="Average Power per Test (Top 15, W)", color_discrete_sequence=["#60A5FA"])
        st.plotly_chart(style_fig(fig), use_container_width=True)
    with c4:
        energy_by_test = energy_df.groupby("test_id")["software_energy_wh"].mean().sort_values(ascending=False).head(15)
        fig = px.bar(energy_by_test, title="Energy per Test (Top 15, Wh)", color_discrete_sequence=["#4ADE80"])
        st.plotly_chart(style_fig(fig), use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        fig = px.histogram(energy_df, x="carbon_g", nbins=30, title="Carbon Estimate Distribution (g)",
                            color_discrete_sequence=["#F472B6"])
        st.plotly_chart(style_fig(fig), use_container_width=True)
    with c6:
        variation = energy_df.groupby("test_id")["software_energy_wh"].std().dropna().sort_values(ascending=False)
        fig = px.bar(variation.head(15), title="Run-to-Run Variation (std dev, Wh)", color_discrete_sequence=["#A78BFA"])
        st.plotly_chart(style_fig(fig), use_container_width=True)

    st.markdown("**Stable vs Unstable Tests** (by coefficient of variation of software energy)")
    grp = energy_df.groupby("test_id")["software_energy_wh"].agg(["mean", "std"]).dropna()
    grp["cv"] = grp["std"] / grp["mean"]
    grp["stability"] = np.where(grp["cv"] < 0.15, "Stable", "Unstable")
    st.dataframe(grp.sort_values("cv", ascending=False).head(20), use_container_width=True)

# --- Hardware Energy tab -----------------------------------------------------
with tab_hw:
    hw_df = energy_df.dropna(subset=["hardware_energy_wh"])
    hw_status = "Connected (partial coverage)" if len(hw_df) > 0 else "Not Connected Yet"
    st.markdown(
        f"""<span class="gat-badge {'badge-pending' if len(hw_df)>0 else 'badge-offline'}">HARDWARE METER: {hw_status.upper()}</span>""",
        unsafe_allow_html=True,
    )
    st.caption(f"Hardware readings available for {len(hw_df)} of {len(energy_df)} runs ({len(hw_df)/len(energy_df):.0%} coverage).")

    if len(hw_df) > 0:
        h1, h2 = st.columns(2)
        with h1:
            fig = px.line(hw_df.reset_index(), y="hardware_voltage_v", title="Voltage Readings (V)",
                           color_discrete_sequence=["#2DD4BF"])
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with h2:
            fig = px.line(hw_df.reset_index(), y="hardware_current_a", title="Current Readings (A)",
                           color_discrete_sequence=["#F59E0B"])
            st.plotly_chart(style_fig(fig), use_container_width=True)

        h3, h4 = st.columns(2)
        with h3:
            fig = px.line(hw_df.reset_index(), y="hardware_power_w", title="Power Trace (W)",
                           color_discrete_sequence=["#60A5FA"])
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with h4:
            fig = px.bar(hw_df.head(25), x="run_id", y="hardware_energy_wh", title="Hardware Energy per Run (Wh)",
                         color_discrete_sequence=["#4ADE80"])
            fig.update_xaxes(showticklabels=False)
            st.plotly_chart(style_fig(fig), use_container_width=True)

        st.markdown("**Hardware Readings Linked to Run IDs**")
        st.dataframe(
            hw_df[["run_id", "hardware_voltage_v", "hardware_current_a", "hardware_power_w",
                   "hardware_energy_wh", "hardware_frequency_hz", "hardware_power_factor"]].head(30),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No hardware readings available yet. Once the ESP32 power meter (Intern 3) is connected, "
                "this tab will populate automatically from hardware_energy_metrics.csv.")

# --- Software vs Hardware Comparison tab ------------------------------------
with tab_cmp:
    cmp_df = energy_df.dropna(subset=["hardware_energy_wh"]).copy()
    if len(cmp_df) > 0:
        cmp_df["difference_wh"] = cmp_df["hardware_energy_wh"] - cmp_df["software_energy_wh"]
        cmp_df["difference_pct"] = (cmp_df["difference_wh"] / cmp_df["software_energy_wh"]) * 100
        calibration_factor = (cmp_df["hardware_energy_wh"] / cmp_df["software_energy_wh"]).mean()

        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            metric_card("Avg Difference", f"{cmp_df['difference_pct'].mean():.1f} %")
        with cc2:
            metric_card("Calibration Factor", f"{calibration_factor:.3f}")
        with cc3:
            mismatch = int((cmp_df["difference_pct"].abs() > 25).sum())
            metric_card("Runs with Large Mismatch", f"{mismatch}", ">25% difference")

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=cmp_df["software_energy_wh"].values, mode="lines", name="Software Energy (Wh)",
                                  line=dict(color="#2DD4BF")))
        fig.add_trace(go.Scatter(y=cmp_df["hardware_energy_wh"].values, mode="lines", name="Hardware Energy (Wh)",
                                  line=dict(color="#F59E0B")))
        fig.update_layout(title="Software Energy vs Hardware Energy")
        st.plotly_chart(style_fig(fig, 380), use_container_width=True)

        fig2 = px.histogram(cmp_df, x="difference_pct", nbins=30, title="Difference Percentage Distribution",
                             color_discrete_sequence=["#F472B6"])
        st.plotly_chart(style_fig(fig2), use_container_width=True)

        st.markdown("**Runs with Large Mismatch (>25%)**")
        st.dataframe(
            cmp_df[cmp_df["difference_pct"].abs() > 25][
                ["run_id", "software_energy_wh", "hardware_energy_wh", "difference_wh", "difference_pct"]
            ],
            use_container_width=True, hide_index=True,
        )
        st.caption(
            "Notes on measurement limitations: software estimates are derived from CPU/memory-based "
            "models and do not capture full system wall-power draw (e.g. display, peripherals, PSU "
            "losses), which explains the systematic offset from hardware readings."
        )
    else:
        st.info("Comparison unavailable — no runs currently have both software and hardware energy readings.")

# ----------------------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------------------
st.markdown("""<div class="gat-footer">GreenAeroTester Dashboard &middot; Energy</div>""", unsafe_allow_html=True)
