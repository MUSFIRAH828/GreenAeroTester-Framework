# ============================================================================
# GreenAeroTester — shared UI helpers.
# This block is intentionally IDENTICAL (in spirit) to the one in Home.py /
# Dataset.py — see the note in Home.py for why each page reproduces it
# rather than importing a shared module. This copy is trimmed to only what
# the Energy page needs.
#
# Phase 9 note (this page): the Energy page no longer generates or reads any
# synthetic/dummy dataset (load_dataset(), generate_hardware_metrics(), the
# 500-scenario random model, etc). It reads the SAME uploaded, validated
# dataset the Home page owns — st.session_state["gat_dataset"] — so every
# KPI, chart, and table on this page is derived from the actual uploaded
# CSV, never from hardcoded arrays or randomly generated values.
#
# Whenever a new CSV is uploaded on Home (Upload/Change), this page picks it
# up automatically on its next render, because it always reads straight out
# of session state rather than caching anything locally.
#
# If no dataset is active (nothing uploaded yet, or the last upload failed
# validation), this page shows the same locked state as Home/Dataset
# instead of any placeholder numbers.
#
# Column contract: this page only relies on the columns Home.py's
# load_and_validate_csv() guarantees when present (run_id, scenario_id,
# runtime_s, software_energy_wh are always present once unlocked; status,
# test_id, flight_phase, mandatory, safety_level, assurance_score,
# timestamp, avg_power_w, carbon_gco2 are used when present). For
# hardware-related and CPU-related fields — which the shared validator does
# NOT canonicalize — this page does its own flexible, alias-based column
# detection (see ENERGY_COLUMN_ALIASES below) and gracefully hides/labels
# any visualization whose required column isn't present, instead of
# crashing or fabricating data.
# ============================================================================

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import streamlit.components.v1 as components
from utils.theme import apply_theme, get_theme_colors, get_chart_colors, get_chart_type, init_session_defaults

init_session_defaults()
COLORS = get_theme_colors()
CHART_COLORS = get_chart_colors()
STATUS_COLORS = {
    "Clean": COLORS["accent"],
    "Failed": COLORS["danger"],
    "Timeout": COLORS["amber"],
    "Crashed": COLORS["purple"],
}

PLOTLY_TEMPLATE = COLORS["plotly_template"]


def inject_css():
    apply_theme()


def sidebar_brand(active_hint: str = ""):
    with st.sidebar:
        st.markdown(
            """
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


def sidebar_lock_notice():
    """Identical lock UI to Home.py/Dataset.py: sidebar/nav stay visible but
    disabled, with a small explanatory note, whenever there's no active
    validated dataset."""
    with st.sidebar:
        st.markdown(
            """
            <style>
            [data-testid="stSidebarNav"] {
                pointer-events: none !important;
                opacity: 0.45;
                filter: grayscale(40%);
            }
            [data-testid="stSidebarNav"] a { cursor: not-allowed !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div style="margin:10px 0 4px 0; padding:10px 12px; border-radius:10px;
                 border:1px solid {COLORS.get('border', 'rgba(128,128,128,0.25)')};
                 background:{COLORS.get('bg_elevated', 'rgba(128,128,128,0.08)')};
                 color:{COLORS['text_faint']}; font-size:12.5px; line-height:1.45;">
                 No dataset uploaded yet. Please upload a CSV file on the Home page to unlock the application.
            </div>
            """,
            unsafe_allow_html=True,
        )
    components.html(
        """
        <script>
        const interceptNav = () => {
            const doc = window.parent.document;
            const nav = doc.querySelector('[data-testid="stSidebarNav"]');
            if (!nav) return;
            nav.querySelectorAll('a').forEach((link) => {
                if (link.dataset.gatLocked === "1") return;
                link.dataset.gatLocked = "1";
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    let toast = doc.getElementById('gat-lock-toast');
                    if (!toast) {
                        toast = doc.createElement('div');
                        toast.id = 'gat-lock-toast';
                        Object.assign(toast.style, {
                            position: 'fixed', bottom: '24px', left: '50%',
                            transform: 'translateX(-50%)', background: '#1f2430',
                            color: '#fff', padding: '10px 18px', borderRadius: '8px',
                            fontSize: '13px', fontFamily: 'Inter, sans-serif',
                            boxShadow: '0 4px 14px rgba(0,0,0,0.35)', zIndex: 99999,
                            transition: 'opacity 0.3s ease',
                        });
                        doc.body.appendChild(toast);
                    }
                    toast.textContent = 'Please upload a CSV file to unlock the application.';
                    toast.style.opacity = '1';
                    clearTimeout(window.__gatToastTimer);
                    window.__gatToastTimer = setTimeout(() => { toast.style.opacity = '0'; }, 3000);
                }, true);
            });
        };
        interceptNav();
        new MutationObserver(interceptNav).observe(window.parent.document.body, {childList: true, subtree: true});
        </script>
        """,
        height=0,
    )


def sidebar_status_footer(df, filename=None):
    total_runs = len(df)
    total_scn = df["scenario_id"].nunique() if "scenario_id" in df.columns else 0
    source_label = filename if filename else "uploaded CSV"
    with st.sidebar:
        st.markdown(
            f"""
            <div class="gat-sidebar-status">
                <div><span class="gat-dot"></span></div>
                <div style="margin-top:6px; color:{COLORS['text_faint']}">
                    {total_scn} scenarios &middot; {total_runs:,} runs<br/>
                    {source_label}
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


def source_badge_html(text, color):
    return (f'<span class="gat-badge" style="background:{color}22; color:{color}; '
            f'border:1px solid {color}55;"><span class="bdot" style="background:{color}"></span>{text}</span>')


def fmt_num(x, decimals=0):
    return f"{x:,.{decimals}f}"


def apply_plotly_theme(fig, height=380):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(font=dict(color=CHART_COLORS["title"], size=15, family="Space Grotesk, sans-serif")),
        font=dict(family="Inter, sans-serif", color=CHART_COLORS["text"], size=12),
        margin=dict(l=10, r=10, t=44, b=10),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=CHART_COLORS["legend"])),
        xaxis=dict(gridcolor=CHART_COLORS["grid"], zerolinecolor=CHART_COLORS["grid"],
                   color=CHART_COLORS["axis_label"], tickfont=dict(color=CHART_COLORS["axis_label"]),
                   title_font=dict(color=CHART_COLORS["axis_label"])),
        yaxis=dict(gridcolor=CHART_COLORS["grid"], zerolinecolor=CHART_COLORS["grid"],
                   color=CHART_COLORS["axis_label"], tickfont=dict(color=CHART_COLORS["axis_label"]),
                   title_font=dict(color=CHART_COLORS["axis_label"])),
    )
    return fig


CARBON_INTENSITY_G_PER_KWH = 475.0  # documented fixed grid-average assumption (fallback only)
FLIGHT_PHASE_ORDER = ["Takeoff", "Climb", "Cruise", "Turn", "Descent", "Approach",
                       "Landing", "Go-Around", "Emergency Landing"]


# ---------------------------------------------------------------------------
# Flexible column lookup, same pattern as Dataset.py's weather/fault
# detection — for the columns the shared upload validator on Home.py does
# NOT canonicalize (CPU usage, and every hardware-related field). Every
# other column this page uses (run_id, scenario_id, runtime_s,
# software_energy_wh, status, test_id, flight_phase, avg_power_w,
# carbon_gco2, mandatory, timestamp) is already canonicalized by Home's
# load_and_validate_csv, so it's addressed directly by its canonical name.
# ---------------------------------------------------------------------------
def _norm(s):
    return str(s).strip().lower().replace(" ", "_")


def _find_column(columns, aliases):
    normalized = {_norm(c): c for c in columns}
    for a in aliases:
        if _norm(a) in normalized:
            return normalized[_norm(a)]
    return None


CPU_ALIASES = ["cpu_usage_pct", "cpu_usage", "avg_cpu_pct", "cpu_percent", "cpu_pct", "cpu"]
VOLTAGE_ALIASES = ["voltage_v", "voltage", "volts"]
CURRENT_ALIASES = ["current_a", "current", "amps", "amperage"]
HW_POWER_ALIASES = ["hardware_power_w", "hw_power_w", "power_trace_w", "hardware_avg_power_w"]
HW_ENERGY_ALIASES = ["hardware_energy_wh", "hw_energy_wh", "hardware_energy"]
HW_DEVICE_ALIASES = ["device_id", "hardware_device_id", "hw_device_id", "meter_id"]
HW_STATUS_ALIASES = ["hardware_status", "hw_status", "measurement_status", "hw_measurement_status"]
CALIBRATION_ALIASES = ["calibration_factor", "hw_calibration_factor", "calibration"]


def compute_group_stability(df, group_col, run_id_col="run_id"):
    """Run-to-run variation per test/scenario (Software Energy section):
    for every group_col value, look at all its runs and measure how much
    energy moves around from run to run using the coefficient of variation
    (CV = std/mean, as a %). Low CV => Stable, high CV => Unstable/flaky.
    Entirely derived from the uploaded software_energy_wh / runtime_s
    columns — no synthetic values."""
    agg = dict(
        n_runs=(run_id_col, "count"),
        avg_runtime_s=("runtime_s", "mean"),
        std_runtime_s=("runtime_s", "std"),
        avg_energy_wh=("software_energy_wh", "mean"),
        std_energy_wh=("software_energy_wh", "std"),
        total_energy_wh=("software_energy_wh", "sum"),
    )
    if "avg_power_w" in df.columns:
        agg["avg_power_w"] = ("avg_power_w", "mean")
    stats = df.groupby(group_col).agg(**agg).reset_index()
    stats["std_energy_wh"] = stats["std_energy_wh"].fillna(0.0)
    stats["std_runtime_s"] = stats["std_runtime_s"].fillna(0.0)
    stats["cv_energy_pct"] = np.where(stats["avg_energy_wh"] > 0,
                                       100 * stats["std_energy_wh"] / stats["avg_energy_wh"], 0.0)
    stats["cv_runtime_pct"] = np.where(stats["avg_runtime_s"] > 0,
                                        100 * stats["std_runtime_s"] / stats["avg_runtime_s"], 0.0)
    return stats


# ============================================================================
# PAGE: Energy Results — Software · Hardware · Comparison
# Source of truth: st.session_state["gat_dataset"] (the same validated CSV
# Home.py stores). No load_dataset(), no random values, no hardcoded arrays.
# energy_wh = software_energy_wh (as uploaded); carbon uses the CSV's own
# carbon_gco2 column when present, otherwise the documented fixed grid
# intensity as a fallback — exactly like Home.py does.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester — Energy",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_brand()

stage = st.session_state.get("gat_stage")
dataset = st.session_state.get("gat_dataset")

# ---- Locked state: no active validated dataset. Mirrors Home.py/Dataset.py
# exactly — nothing below renders (no charts/tables/KPIs with stale or
# placeholder numbers). --------------------------------------------------
if stage != "unlocked" or dataset is None:
    sidebar_lock_notice()
    page_header(
        "PHASE 1 · ENERGY",
        "Energy Results",
        "Software measurement, hardware measurement, and a side-by-side comparison — "
        "generated entirely from your uploaded dataset",
    )
    if st.session_state.get("gat_invalid_errors"):
        st.error(
            "The most recently uploaded file failed validation on the Home page, so no dataset is active. "
            "Go to Home to upload a corrected CSV."
        )
    else:
        st.info("No dataset uploaded yet. Please upload a CSV file on the Home page to begin.")
    st.stop()

# ---- Active dataset from here on -------------------------------------------
df = dataset.copy()
sidebar_status_footer(df, filename=st.session_state.get("gat_active_file"))

# ---- Column availability (software side is guaranteed by Home's validator;
# hardware/CPU side uses this page's own flexible alias detection) ----------
has_test_id = "test_id" in df.columns
has_status = "status" in df.columns
has_flight_phase = "flight_phase" in df.columns
has_mandatory = "mandatory" in df.columns
has_avg_power = "avg_power_w" in df.columns
has_carbon = "carbon_gco2" in df.columns
has_timestamp = "timestamp" in df.columns and df["timestamp"].notna().any()

cpu_col = _find_column(df.columns, CPU_ALIASES)
voltage_col = _find_column(df.columns, VOLTAGE_ALIASES)
current_col = _find_column(df.columns, CURRENT_ALIASES)
hw_power_col = _find_column(df.columns, HW_POWER_ALIASES)
hw_energy_col = _find_column(df.columns, HW_ENERGY_ALIASES)
hw_device_col = _find_column(df.columns, HW_DEVICE_ALIASES)
hw_status_col = _find_column(df.columns, HW_STATUS_ALIASES)
calibration_col = _find_column(df.columns, CALIBRATION_ALIASES)

has_hardware_data = any([voltage_col, current_col, hw_power_col, hw_energy_col, hw_device_col, hw_status_col])

group_col = "test_id" if has_test_id else "scenario_id"
group_label = "Test" if has_test_id else "Scenario"

# ---- Derived software fields (from the CSV only) ---------------------------
df["_energy_kwh"] = df["software_energy_wh"] / 1000.0
if has_carbon:
    df["_carbon_kg"] = df["carbon_gco2"] / 1000.0
    carbon_source_note = "from CSV carbon_gco2 column"
else:
    df["_carbon_kg"] = df["_energy_kwh"] * CARBON_INTENSITY_G_PER_KWH / 1000.0
    carbon_source_note = f"estimated @ {int(CARBON_INTENSITY_G_PER_KWH)} gCO₂/kWh (documented fallback)"

# ---- Derived hardware energy per run (only if the data allows it) ---------
hw_energy_wh_series = None
hw_energy_source_note = None
if hw_energy_col is not None:
    hw_energy_wh_series = pd.to_numeric(df[hw_energy_col], errors="coerce")
    hw_energy_source_note = f"from CSV `{hw_energy_col}` column"
elif hw_power_col is not None:
    hw_power_num = pd.to_numeric(df[hw_power_col], errors="coerce")
    hw_energy_wh_series = hw_power_num * df["runtime_s"] / 3600.0
    hw_energy_source_note = f"computed as `{hw_power_col}` × runtime_s ÷ 3600"
elif voltage_col is not None and current_col is not None:
    v_num = pd.to_numeric(df[voltage_col], errors="coerce")
    i_num = pd.to_numeric(df[current_col], errors="coerce")
    hw_power_derived = v_num * i_num
    hw_energy_wh_series = hw_power_derived * df["runtime_s"] / 3600.0
    hw_energy_source_note = f"computed as `{voltage_col}` × `{current_col}` × runtime_s ÷ 3600"

if hw_energy_wh_series is not None:
    df["_hw_energy_wh"] = hw_energy_wh_series
    has_hardware_energy = df["_hw_energy_wh"].notna().any()
else:
    has_hardware_energy = False

page_header(
    "PHASE 1 · ENERGY",
    "Energy Results",
    "Software measurement, hardware measurement, and a side-by-side comparison — "
    "generated entirely from your uploaded dataset",
    pill_text=f"{len(df):,} rows · {df['scenario_id'].nunique():,} scenarios",
)

# ---------------------------------------------------------------------------
# Filters — built only from columns actually present in the uploaded CSV
# ---------------------------------------------------------------------------
with st.expander("Filters", expanded=False):
    filter_defs = []
    if has_flight_phase:
        opts = [p for p in FLIGHT_PHASE_ORDER if p in df["flight_phase"].unique()]
        opts += sorted(set(df["flight_phase"].dropna().unique()) - set(opts))
        filter_defs.append(("flight_phase", "Flight phase", opts))
    if has_status:
        filter_defs.append(("status", "Status", sorted(df["status"].dropna().unique().tolist())))

    selections = {}
    fc_search1, fc_search2 = st.columns(2)
    with fc_search1:
        f_scenario = st.text_input("Scenario ID contains", "")
    with fc_search2:
        f_run = st.text_input("Run ID contains", "")

    for i in range(0, len(filter_defs), 3):
        row = filter_defs[i:i + 3]
        cols = st.columns(len(row))
        for (col_name, label, options), c in zip(row, cols):
            with c:
                selections[col_name] = st.multiselect(label, options, default=[], key=f"gat_energy_filter_{col_name}")

    f_mandatory = st.selectbox("Mandatory", ["All", "Mandatory only", "Optional only"]) if has_mandatory else "All"

    if has_timestamp:
        min_ts, max_ts = df["timestamp"].min(), df["timestamp"].max()
        f_dates = st.date_input("Date range", value=(min_ts.date(), max_ts.date()),
                                 min_value=min_ts.date(), max_value=max_ts.date())
    else:
        f_dates = None

view = df.copy()
for col_name, values in selections.items():
    if values:
        view = view[view[col_name].isin(values)]
if has_mandatory:
    if f_mandatory == "Mandatory only":
        view = view[view["mandatory"].astype(bool)]
    elif f_mandatory == "Optional only":
        view = view[~view["mandatory"].astype(bool)]
if f_scenario:
    view = view[view["scenario_id"].astype(str).str.contains(f_scenario, case=False, na=False)]
if f_run:
    view = view[view["run_id"].astype(str).str.contains(f_run, case=False, na=False)]
if has_timestamp and isinstance(f_dates, tuple) and len(f_dates) == 2:
    start, end = f_dates
    view = view[(view["timestamp"].dt.date >= start) & (view["timestamp"].dt.date <= end)]

st.caption(f"{len(view):,} of {len(df):,} runs match the current filters")

if view.empty:
    st.warning("No runs match the current filters. Adjust filters above to see results.")
    st.stop()

tab_sw, tab_hw, tab_cmp = st.tabs(["> Software Energy", " > Hardware Energy", " > Software vs Hardware"])

# ============================================================================
# TAB 1 — SOFTWARE ENERGY
# ============================================================================
with tab_sw:
    section_title("Software Measurement Summary", tag="source: uploaded CSV")

    sw_energy_kwh = view["_energy_kwh"].sum()
    sw_carbon_kg = view["_carbon_kg"].sum()
    avg_runtime = view["runtime_s"].mean()

    r1 = st.columns(5)
    with r1[0]:
        metric_card("Total Software Energy", f"{sw_energy_kwh:.2f} kWh", accent=COLORS["accent2"])
    with r1[1]:
        metric_card("Total Carbon Estimate", f"{sw_carbon_kg:.2f} kg CO₂e", carbon_source_note, accent=COLORS["danger"])
    with r1[2]:
        if has_avg_power:
            metric_card("Avg Power / Run", f"{view['avg_power_w'].mean():.1f} W", accent=COLORS["accent"])
        else:
            metric_card("Avg Power / Run", "N/A", "no avg_power_w column in CSV", accent=COLORS["text_faint"])
    with r1[3]:
        metric_card("Avg Runtime / Run", f"{avg_runtime:.1f} s", accent=COLORS["purple"])
    with r1[4]:
        if cpu_col:
            metric_card("Avg CPU Usage", f"{pd.to_numeric(view[cpu_col], errors='coerce').mean():.1f}%",
                        accent=COLORS["accent2"])
        else:
            metric_card("Avg CPU Usage", "N/A", "no CPU usage column in CSV", accent=COLORS["text_faint"])

    r2 = st.columns(4)
    with r2[0]:
        metric_card("Runs in view", f"{len(view):,}", accent=COLORS["accent"])
    with r2[1]:
        metric_card(f"{group_label}s in view", f"{view[group_col].nunique():,}", accent=COLORS["purple"])
    with r2[2]:
        metric_card("Clean Runs", fmt_num(int((view["status"] == "Clean").sum())) if has_status else "N/A",
                    accent=COLORS["accent"] if has_status else COLORS["text_faint"])
    with r2[3]:
        metric_card("Data Source", "uploaded CSV", accent=COLORS["text_dim"])

    with st.expander("⚙ Energy & Carbon Formula Reference", expanded=False):
        st.markdown(f"""
- **Software Energy** — read directly from the uploaded CSV's `software_energy_wh` column for each run.
- **Carbon Estimate** — {"taken directly from the CSV's `carbon_gco2` column" if has_carbon else
        f"computed as `carbon_kg = energy_kwh × {int(CARBON_INTENSITY_G_PER_KWH)} / 1000`, using a fixed "
        f"grid-average intensity of **{int(CARBON_INTENSITY_G_PER_KWH)} gCO₂/kWh** (documented fallback, "
        f"used only because the CSV has no carbon column of its own)."}
- **Run-to-Run Variation** — coefficient of variation (`CV = std / mean × 100`) of `software_energy_wh`
  within each {group_label.lower()}, computed only from the uploaded rows.
- **Grouping** — {"per `test_id`" if has_test_id else "per `scenario_id` (no `test_id` column found in this CSV)"}.
""")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # CPU usage per run
    # ------------------------------------------------------------------
    section_title("CPU Usage per Run", tag=cpu_col if cpu_col else "unavailable")
    if cpu_col:
        cpu_series = pd.to_numeric(view[cpu_col], errors="coerce")
        cc1, cc2 = st.columns([1.3, 1])
        with cc1:
            plot_df = view.assign(_cpu=cpu_series)
            if has_timestamp:
                fig = go.Figure(go.Scatter(x=plot_df["timestamp"], y=plot_df["_cpu"], mode="markers",
                                            marker=dict(size=5, color=CHART_COLORS["bar"])))
                fig.update_layout(title="CPU Usage per Run Over Time", yaxis_title="CPU (%)")
            else:
                fig = go.Figure(go.Bar(x=plot_df["run_id"], y=plot_df["_cpu"], marker_color=CHART_COLORS["bar"]))
                fig.update_layout(title="CPU Usage per Run", yaxis_title="CPU (%)", xaxis_title="Run ID")
                fig.update_xaxes(showticklabels=False)
            st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})
        with cc2:
            fig = go.Figure(go.Histogram(x=cpu_series.dropna(), marker_color=CHART_COLORS["line"], nbinsx=25))
            fig.update_layout(title="CPU Usage Distribution", xaxis_title="CPU (%)", showlegend=False)
            st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})
    else:
        st.info("The uploaded CSV doesn't include a CPU usage column — CPU-per-run charts aren't available "
                "for this dataset.")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Runtime / Average Power / Energy per test (or per scenario)
    # ------------------------------------------------------------------
    section_title(f"Runtime, Power & Energy per {group_label}", tag="aggregated from uploaded rows")
    per_group = view.groupby(group_col).agg(
        n_runs=("run_id", "count"),
        avg_runtime_s=("runtime_s", "mean"),
        total_energy_wh=("software_energy_wh", "sum"),
        avg_energy_wh=("software_energy_wh", "mean"),
        total_carbon_kg=("_carbon_kg", "sum"),
    )
    if has_avg_power:
        per_group["avg_power_w"] = view.groupby(group_col)["avg_power_w"].mean()

    pg1, pg2 = st.columns(2)
    with pg1:
        top_rt = per_group["avg_runtime_s"].sort_values(ascending=False).head(15)
        fig = go.Figure(go.Bar(x=top_rt.values[::-1], y=[str(i) for i in top_rt.index[::-1]],
                                orientation="h", marker_color=CHART_COLORS["bar"]))
        fig.update_layout(title=f"Avg Runtime per {group_label} — Top 15 (s)")
        st.plotly_chart(apply_plotly_theme(fig, 380), use_container_width=True, config={"displaylogo": False})
    with pg2:
        if has_avg_power:
            top_pw = per_group["avg_power_w"].sort_values(ascending=False).head(15)
            fig = go.Figure(go.Bar(x=top_pw.values[::-1], y=[str(i) for i in top_pw.index[::-1]],
                                    orientation="h", marker_color=CHART_COLORS["line"]))
            fig.update_layout(title=f"Avg Power per {group_label} — Top 15 (W)")
            st.plotly_chart(apply_plotly_theme(fig, 380), use_container_width=True, config={"displaylogo": False})
        else:
            st.info("The uploaded CSV doesn't include an `avg_power_w` column — average power per "
                    f"{group_label.lower()} isn't available for this dataset.")

    top_en = per_group["total_energy_wh"].sort_values(ascending=False).head(15)
    fig = go.Figure(go.Bar(x=top_en.values[::-1], y=[str(i) for i in top_en.index[::-1]],
                            orientation="h", marker_color=CHART_COLORS["bar"]))
    fig.update_layout(title=f"Total Energy per {group_label} — Top 15 (Wh)")
    st.plotly_chart(apply_plotly_theme(fig, 380), use_container_width=True, config={"displaylogo": False})

    top_cb = per_group["total_carbon_kg"].sort_values(ascending=False).head(15)
    fig = go.Figure(go.Bar(x=top_cb.values[::-1], y=[str(i) for i in top_cb.index[::-1]],
                            orientation="h", marker_color=CHART_COLORS["purple"] if "purple" in CHART_COLORS else CHART_COLORS["line"]))
    fig.update_layout(title=f"Carbon Estimate per {group_label} — Top 15 (kg CO₂e)")
    st.plotly_chart(apply_plotly_theme(fig, 360), use_container_width=True, config={"displaylogo": False})

    group_table_cols = {
        group_col: group_label + " ID", "n_runs": "Runs", "avg_runtime_s": "Avg Runtime (s)",
        "total_energy_wh": "Total Energy (Wh)", "avg_energy_wh": "Avg Energy/Run (Wh)",
        "total_carbon_kg": "Total Carbon (kg CO₂e)",
    }
    if has_avg_power:
        group_table_cols["avg_power_w"] = "Avg Power (W)"
    group_show = per_group.reset_index()[list(group_table_cols.keys())].rename(columns=group_table_cols)
    for c in group_show.select_dtypes(include=[float]).columns:
        group_show[c] = group_show[c].round(2)
    group_show = group_show.sort_values("Total Energy (Wh)", ascending=False)
    st.dataframe(group_show, use_container_width=True, height=340, hide_index=True)
    st.download_button(f"⬇ Download per-{group_label.lower()} energy CSV", group_show.to_csv(index=False).encode(),
                        file_name=f"software_energy_per_{group_col}.csv", mime="text/csv", key="dl_sw_group")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Run-to-run variation / stability
    # ------------------------------------------------------------------
    section_title("Run-to-Run Variation & Stability", tag=f"grouped by {group_col}")
    stability = compute_group_stability(view, group_col)
    stab_threshold = st.slider("Stability threshold — CV of energy across runs (%)", 5, 60, 15, 1,
                                help="A test/scenario is labelled Unstable if the run-to-run energy "
                                     "coefficient of variation (std/mean, %) exceeds this threshold.")
    stability["stability"] = np.where(
        stability["n_runs"] <= 1, "Single Run",
        np.where(stability["cv_energy_pct"] > stab_threshold, "Unstable", "Stable"),
    )

    n_stable = int((stability["stability"] == "Stable").sum())
    n_unstable = int((stability["stability"] == "Unstable").sum())
    n_single = int((stability["stability"] == "Single Run").sum())

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        metric_card("Stable", f"{n_stable}", accent=COLORS["accent"])
    with sc2:
        metric_card("Unstable", f"{n_unstable}", accent=COLORS["danger"])
    with sc3:
        metric_card("Single-Run (not evaluable)", f"{n_single}", accent=COLORS["text_faint"])

    multi_run = stability[stability["n_runs"] > 1]
    if not multi_run.empty:
        top_var = multi_run.sort_values("cv_energy_pct", ascending=False).head(15)
        bar_colors = [CHART_COLORS["line"] if s == "Unstable" else CHART_COLORS["bar"] for s in top_var["stability"]]
        fig = go.Figure(go.Bar(x=top_var["cv_energy_pct"], y=[str(i) for i in top_var[group_col]],
                                orientation="h", marker_color=bar_colors))
        fig.add_vline(x=stab_threshold, line_dash="dot", line_color=COLORS["amber"])
        fig.update_layout(title=f"Most Variable {group_label}s — Energy CV (%)", yaxis=dict(autorange="reversed"))
        st.plotly_chart(apply_plotly_theme(fig, 400), use_container_width=True, config={"displaylogo": False})
    else:
        st.info(f"No {group_label.lower()} in the current filter has more than one run, so run-to-run "
                "variation can't be computed.")

    stab_cols = {
        group_col: group_label + " ID", "n_runs": "Runs", "avg_runtime_s": "Avg Runtime (s)",
        "avg_energy_wh": "Avg Energy/Run (Wh)", "cv_energy_pct": "Energy CV (%)",
        "cv_runtime_pct": "Runtime CV (%)", "stability": "Stability",
    }
    stab_show = stability[list(stab_cols.keys())].rename(columns=stab_cols).copy()
    for c in stab_show.select_dtypes(include=[float]).columns:
        stab_show[c] = stab_show[c].round(2)
    stab_show = stab_show.sort_values("Energy CV (%)", ascending=False)
    st.dataframe(stab_show, use_container_width=True, height=340, hide_index=True)
    st.download_button("⬇ Download stability table CSV", stab_show.to_csv(index=False).encode(),
                        file_name="software_energy_stability.csv", mime="text/csv", key="dl_sw_stability")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Per-run table
    # ------------------------------------------------------------------
    section_title("Per-Run Software Measurements", tag="from uploaded CSV")
    run_cols = {"run_id": "Run ID", "scenario_id": "Scenario"}
    if has_test_id:
        run_cols["test_id"] = "Test ID"
    if has_flight_phase:
        run_cols["flight_phase"] = "Flight Phase"
    if has_status:
        run_cols["status"] = "Status"
    if cpu_col:
        run_cols[cpu_col] = "CPU (%)"
    run_cols["runtime_s"] = "Runtime (s)"
    if has_avg_power:
        run_cols["avg_power_w"] = "Avg Power (W)"
    run_cols["software_energy_wh"] = "Energy (Wh)"
    run_cols["_carbon_kg"] = "Carbon (kg CO₂e)"

    run_show = view[list(run_cols.keys())].rename(columns=run_cols).copy()
    for c in run_show.select_dtypes(include=[float]).columns:
        run_show[c] = run_show[c].round(3)
    run_show = run_show.sort_values("Energy (Wh)", ascending=False)
    st.dataframe(run_show, use_container_width=True, height=340, hide_index=True)
    st.download_button("⬇ Download per-run software CSV", run_show.to_csv(index=False).encode(),
                        file_name="software_energy_per_run.csv", mime="text/csv", key="dl_sw_runs")

    st.markdown(
        f"""<div class="gat-footer-note">
        Every value on this tab is computed directly from the uploaded CSV (<code>{st.session_state.get('gat_active_file', '')}</code>).
        No random or hardcoded data is used.
        </div>""",
        unsafe_allow_html=True,
    )

# ============================================================================
# TAB 2 — HARDWARE ENERGY
# ============================================================================
with tab_hw:
    section_title("Hardware Measurement Status", tag="from uploaded CSV")

    if not has_hardware_data:
        st.info("Hardware data not available in the uploaded dataset.")
    else:
        detected = []
        if voltage_col: detected.append(f"Voltage → `{voltage_col}`")
        if current_col: detected.append(f"Current → `{current_col}`")
        if hw_power_col: detected.append(f"Power → `{hw_power_col}`")
        if hw_energy_col: detected.append(f"Energy → `{hw_energy_col}`")
        if hw_device_col: detected.append(f"Device ID → `{hw_device_col}`")
        if hw_status_col: detected.append(f"Status → `{hw_status_col}`")
        st.markdown(source_badge_html("Hardware columns detected: " + " · ".join(detected), COLORS["accent2"]),
                    unsafe_allow_html=True)

        hwc = st.columns(4)
        with hwc[0]:
            if voltage_col:
                metric_card("Avg Voltage", f"{pd.to_numeric(view[voltage_col], errors='coerce').mean():.2f} V",
                            accent=COLORS["accent2"])
            else:
                metric_card("Avg Voltage", "N/A", "no voltage column", accent=COLORS["text_faint"])
        with hwc[1]:
            if current_col:
                metric_card("Avg Current", f"{pd.to_numeric(view[current_col], errors='coerce').mean():.2f} A",
                            accent=COLORS["purple"])
            else:
                metric_card("Avg Current", "N/A", "no current column", accent=COLORS["text_faint"])
        with hwc[2]:
            if hw_power_col:
                metric_card("Avg Hardware Power", f"{pd.to_numeric(view[hw_power_col], errors='coerce').mean():.1f} W",
                            accent=COLORS["amber"])
            elif voltage_col and current_col:
                derived_power = (pd.to_numeric(view[voltage_col], errors="coerce")
                                  * pd.to_numeric(view[current_col], errors="coerce"))
                metric_card("Avg Hardware Power", f"{derived_power.mean():.1f} W", "V × A", accent=COLORS["amber"])
            else:
                metric_card("Avg Hardware Power", "N/A", "no power/voltage+current columns", accent=COLORS["text_faint"])
        with hwc[3]:
            if has_hardware_energy:
                metric_card("Total Hardware Energy", f"{view['_hw_energy_wh'].sum()/1000:.2f} kWh",
                            hw_energy_source_note, accent=COLORS["amber"])
            else:
                metric_card("Total Hardware Energy", "N/A", "insufficient columns to derive", accent=COLORS["text_faint"])

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # ---- Voltage / Current readings ------------------------------------
        vc1, vc2 = st.columns(2)
        with vc1:
            section_title("Voltage Readings", tag=voltage_col if voltage_col else "unavailable")
            if voltage_col:
                v_num = pd.to_numeric(view[voltage_col], errors="coerce")
                if has_timestamp:
                    fig = go.Figure(go.Scatter(x=view["timestamp"], y=v_num, mode="lines",
                                                line=dict(color=CHART_COLORS["bar"], width=2)))
                    fig.update_layout(title="Voltage Over Time", yaxis_title="Volts (V)")
                else:
                    fig = go.Figure(go.Histogram(x=v_num.dropna(), marker_color=CHART_COLORS["bar"], nbinsx=25))
                    fig.update_layout(title="Voltage Distribution", xaxis_title="Volts (V)", showlegend=False)
                st.plotly_chart(apply_plotly_theme(fig, 300), use_container_width=True, config={"displaylogo": False})
            else:
                st.info("No voltage column found in the uploaded CSV.")
        with vc2:
            section_title("Current Readings", tag=current_col if current_col else "unavailable")
            if current_col:
                i_num = pd.to_numeric(view[current_col], errors="coerce")
                if has_timestamp:
                    fig = go.Figure(go.Scatter(x=view["timestamp"], y=i_num, mode="lines",
                                                line=dict(color=CHART_COLORS["title"], width=2)))
                    fig.update_layout(title="Current Over Time", yaxis_title="Amps (A)")
                else:
                    fig = go.Figure(go.Histogram(x=i_num.dropna(), marker_color=CHART_COLORS["title"], nbinsx=25))
                    fig.update_layout(title="Current Distribution", xaxis_title="Amps (A)", showlegend=False)
                st.plotly_chart(apply_plotly_theme(fig, 300), use_container_width=True, config={"displaylogo": False})
            else:
                st.info("No current column found in the uploaded CSV.")

        # ---- Power trace -----------------------------------------------------
        section_title("Power Trace", tag="hardware active power")
        if hw_power_col or (voltage_col and current_col):
            if hw_power_col:
                p_num = pd.to_numeric(view[hw_power_col], errors="coerce")
            else:
                p_num = (pd.to_numeric(view[voltage_col], errors="coerce")
                         * pd.to_numeric(view[current_col], errors="coerce"))
            if has_timestamp:
                trace_df = view.assign(_p=p_num).set_index("timestamp")["_p"].sort_index()
                fig = go.Figure(go.Scatter(x=trace_df.index, y=trace_df.values, mode="lines",
                                            line=dict(color=CHART_COLORS["line"], width=2), fill="tozeroy",
                                            fillcolor=f"{CHART_COLORS['line']}22"))
                fig.update_layout(title="Hardware Power Trace Over Time", yaxis_title="Watts")
            else:
                fig = go.Figure(go.Scatter(y=p_num.values, mode="lines", line=dict(color=CHART_COLORS["line"], width=2)))
                fig.update_layout(title="Hardware Power Trace (by row order)", yaxis_title="Watts")
            st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})
        else:
            st.info("The uploaded CSV doesn't include a hardware power column (or voltage + current to "
                    "derive one) — the power trace isn't available for this dataset.")

        # ---- Hardware energy per run ------------------------------------------
        section_title("Hardware Energy per Run", tag=hw_energy_source_note if has_hardware_energy else "unavailable")
        if has_hardware_energy:
            ec1, ec2 = st.columns(2)
            with ec1:
                fig = go.Figure(go.Histogram(x=view["_hw_energy_wh"].dropna(), marker_color=CHART_COLORS["line"], nbinsx=30))
                fig.update_layout(title="Hardware Energy per Run — Distribution (Wh)", xaxis_title="Wh per run", showlegend=False)
                st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})
            with ec2:
                if has_flight_phase:
                    by_phase_hw = view.groupby("flight_phase")["_hw_energy_wh"].sum() / 1000
                    order = [p for p in FLIGHT_PHASE_ORDER if p in by_phase_hw.index]
                    order += sorted(set(by_phase_hw.index) - set(order))
                    by_phase_hw = by_phase_hw.reindex(order)
                    fig = go.Figure(go.Bar(x=by_phase_hw.index, y=by_phase_hw.values, marker_color=CHART_COLORS["bar"]))
                    fig.update_layout(title="Hardware Energy — Total by Flight Phase (kWh)", showlegend=False)
                else:
                    top_hw = view.groupby(group_col)["_hw_energy_wh"].sum().sort_values(ascending=False).head(15) / 1000
                    fig = go.Figure(go.Bar(x=top_hw.values[::-1], y=[str(i) for i in top_hw.index[::-1]],
                                            orientation="h", marker_color=CHART_COLORS["bar"]))
                    fig.update_layout(title=f"Hardware Energy — Top 15 {group_label}s (kWh)")
                st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})
        else:
            st.info("Not enough hardware columns were found to compute energy per run for this dataset "
                    "(need a hardware energy column, a hardware power column, or both voltage and current).")

        # ---- Hardware measurement status ---------------------------------------
        section_title("Hardware Measurement Status", tag=hw_status_col if hw_status_col else "unavailable")
        if hw_status_col:
            status_counts = view[hw_status_col].value_counts()
            fig = go.Figure(go.Pie(labels=status_counts.index, values=status_counts.values, hole=0.55))
            fig.update_traces(marker=dict(colors=CHART_COLORS["pie"]))
            fig.update_layout(title="Hardware Measurement Status Breakdown", showlegend=True)
            st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})
        else:
            st.info("No hardware measurement status column found in the uploaded CSV.")

        # ---- Hardware readings linked to run_id -------------------------------
        section_title("Hardware Readings — Linked to Run ID", tag="from uploaded CSV")
        hw_table_cols = {"run_id": "Run ID", "scenario_id": "Scenario"}
        if hw_device_col: hw_table_cols[hw_device_col] = "Device ID"
        if voltage_col: hw_table_cols[voltage_col] = "Voltage (V)"
        if current_col: hw_table_cols[current_col] = "Current (A)"
        if hw_power_col: hw_table_cols[hw_power_col] = "Power (W)"
        if has_hardware_energy: hw_table_cols["_hw_energy_wh"] = "Energy (Wh)"
        if hw_status_col: hw_table_cols[hw_status_col] = "Status"

        hw_table = view[list(hw_table_cols.keys())].rename(columns=hw_table_cols).copy()
        for c in hw_table.select_dtypes(include=[float]).columns:
            hw_table[c] = hw_table[c].round(3)
        st.dataframe(hw_table, use_container_width=True, height=360, hide_index=True)
        st.download_button("⬇ Download hardware readings CSV", hw_table.to_csv(index=False).encode(),
                            file_name="hardware_energy_readings.csv", mime="text/csv", key="dl_hw")

        st.markdown(
            f"""<div class="gat-footer-note">
            Every hardware value on this tab is read or derived directly from the uploaded CSV
            (<code>{st.session_state.get('gat_active_file', '')}</code>) — no simulated or hardcoded values.
            </div>""",
            unsafe_allow_html=True,
        )

# ============================================================================
# TAB 3 — SOFTWARE vs HARDWARE COMPARISON
# ============================================================================
with tab_cmp:
    section_title("Software vs Hardware — Comparison", tag="from uploaded CSV")

    if not has_hardware_energy:
        st.info("Software vs Hardware comparison cannot be generated because hardware_energy_wh is missing.")
    else:
        cmp_view = view.dropna(subset=["software_energy_wh", "_hw_energy_wh"]).copy()
        if cmp_view.empty:
            st.info("Software vs Hardware comparison cannot be generated because hardware_energy_wh is missing.")
        else:
            sw_energy_kwh = cmp_view["software_energy_wh"].sum() / 1000
            hw_energy_kwh = cmp_view["_hw_energy_wh"].sum() / 1000
            abs_diff_wh = (cmp_view["_hw_energy_wh"] - cmp_view["software_energy_wh"]).abs().sum()
            energy_diff_pct = 100 * (hw_energy_kwh - sw_energy_kwh) / sw_energy_kwh if sw_energy_kwh else 0.0

            cmp_view["_diff_wh"] = cmp_view["_hw_energy_wh"] - cmp_view["software_energy_wh"]
            cmp_view["_diff_pct"] = np.where(
                cmp_view["software_energy_wh"] > 0,
                100 * cmp_view["_diff_wh"] / cmp_view["software_energy_wh"], np.nan,
            )
            cmp_view["_error_pct"] = cmp_view["_diff_pct"].abs()

            if calibration_col:
                calibration_factor = float(pd.to_numeric(cmp_view[calibration_col], errors="coerce").dropna().mean())
                calibration_note = f"from CSV `{calibration_col}` column (mean)"
            else:
                mean_sw = cmp_view["software_energy_wh"].mean()
                calibration_factor = float(cmp_view["_hw_energy_wh"].mean() / mean_sw) if mean_sw else 1.0
                calibration_note = "computed as mean(hardware) ÷ mean(software) — no calibration column in CSV"

            r1 = st.columns(5)
            with r1[0]:
                metric_card("Software Energy", f"{sw_energy_kwh:.2f} kWh", accent=COLORS["accent2"])
            with r1[1]:
                metric_card("Hardware Energy", f"{hw_energy_kwh:.2f} kWh", hw_energy_source_note, accent=COLORS["amber"])
            with r1[2]:
                metric_card("Absolute Difference", f"{abs_diff_wh:.1f} Wh", accent=COLORS["purple"])
            with r1[3]:
                metric_card("Difference (%)", f"{energy_diff_pct:+.1f}%", accent=COLORS["purple"])
            with r1[4]:
                metric_card("Calibration Factor", f"{calibration_factor:.4f}", calibration_note, accent=COLORS["accent"])

            st.caption(
                "Formula: `diff_wh = hardware_energy_wh − software_energy_wh` · "
                "`diff_pct = 100 × diff_wh / software_energy_wh` · `error_pct = |diff_pct|`."
            )
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            cg1, cg2 = st.columns(2)
            with cg1:
                if has_flight_phase:
                    by_phase = cmp_view.groupby("flight_phase")[["software_energy_wh", "_hw_energy_wh"]].sum() / 1000
                    order = [p for p in FLIGHT_PHASE_ORDER if p in by_phase.index]
                    order += sorted(set(by_phase.index) - set(order))
                    by_phase = by_phase.reindex(order)
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name="Software (kWh)", x=by_phase.index, y=by_phase["software_energy_wh"],
                                          marker_color=CHART_COLORS["bar"]))
                    fig.add_trace(go.Bar(name="Hardware (kWh)", x=by_phase.index, y=by_phase["_hw_energy_wh"],
                                          marker_color=CHART_COLORS["line"]))
                    fig.update_layout(title="Software vs Hardware — Total Energy by Flight Phase", barmode="group")
                else:
                    by_group = cmp_view.groupby(group_col)[["software_energy_wh", "_hw_energy_wh"]].sum().head(15) / 1000
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name="Software (kWh)", x=[str(i) for i in by_group.index],
                                          y=by_group["software_energy_wh"], marker_color=CHART_COLORS["bar"]))
                    fig.add_trace(go.Bar(name="Hardware (kWh)", x=[str(i) for i in by_group.index],
                                          y=by_group["_hw_energy_wh"], marker_color=CHART_COLORS["line"]))
                    fig.update_layout(title=f"Software vs Hardware — Total Energy by {group_label}", barmode="group")
                st.plotly_chart(apply_plotly_theme(fig, 340), use_container_width=True, config={"displaylogo": False})
            with cg2:
                lo = min(cmp_view["software_energy_wh"].min(), cmp_view["_hw_energy_wh"].min())
                hi = max(cmp_view["software_energy_wh"].max(), cmp_view["_hw_energy_wh"].max())
                fig = go.Figure()
                fig.add_trace(go.Scattergl(x=cmp_view["software_energy_wh"], y=cmp_view["_hw_energy_wh"], mode="markers",
                                            marker=dict(size=5, color=cmp_view["_error_pct"], colorscale="Tealgrn",
                                                        showscale=True, colorbar=dict(title="Error %")),
                                            name="Runs"))
                fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                                          line=dict(color=COLORS["text_faint"], width=1.5, dash="dash"),
                                          name="Perfect agreement"))
                fig.update_layout(title="Software vs Hardware Energy (Wh)", xaxis_title="Software Energy (Wh)",
                                   yaxis_title="Hardware Energy (Wh)")
                st.plotly_chart(apply_plotly_theme(fig, 340), use_container_width=True, config={"displaylogo": False})

            if has_timestamp:
                section_title("Difference Trend", tag="hardware vs software, over time")
                diff_t = cmp_view.set_index("timestamp")["_diff_pct"].sort_index()
                fig = go.Figure(go.Scatter(x=diff_t.index, y=diff_t.values, mode="lines+markers",
                                            line=dict(color=CHART_COLORS["line"], width=2), marker=dict(size=4)))
                fig.add_hline(y=0, line_dash="dot", line_color=COLORS["grid"])
                fig.update_layout(title="Difference Trend — Hardware vs Software (%)", yaxis_title="Difference (%)",
                                   showlegend=False)
                st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # ------------------------------------------------------------------
            # Runs with large mismatch
            # ------------------------------------------------------------------
            section_title("Runs with Large Mismatch", tag="runs where error exceeds threshold")
            mismatch_threshold = st.slider("Flag runs with estimation error above (%)", 5, 100, 15, 1)
            flagged = cmp_view[cmp_view["_error_pct"] > mismatch_threshold].copy()
            st.caption(f"{len(flagged):,} of {len(cmp_view):,} runs in the current filter exceed {mismatch_threshold}% error")

            if flagged.empty:
                st.success("No runs exceed the selected mismatch threshold.")
            else:
                flag_cols = {"run_id": "Run ID", "scenario_id": "Scenario"}
                if has_test_id:
                    flag_cols["test_id"] = "Test ID"
                if has_flight_phase:
                    flag_cols["flight_phase"] = "Flight Phase"
                flag_cols.update({
                    "software_energy_wh": "Software Energy (Wh)", "_hw_energy_wh": "Hardware Energy (Wh)",
                    "_diff_wh": "Difference (Wh)", "_diff_pct": "Difference (%)", "_error_pct": "Error (%)",
                })
                flag_show = flagged[list(flag_cols.keys())].rename(columns=flag_cols).copy()
                for c in flag_show.select_dtypes(include=[float]).columns:
                    flag_show[c] = flag_show[c].round(2)
                flag_show = flag_show.sort_values("Error (%)", ascending=False)
                st.dataframe(flag_show, use_container_width=True, height=320, hide_index=True)
                st.download_button("⬇ Download flagged mismatches CSV", flag_show.to_csv(index=False).encode(),
                                    file_name="flagged_energy_mismatches.csv", mime="text/csv", key="dl_flagged")

            st.markdown(
                f"""<div class="gat-footer-note">
                All comparison values are computed directly from the uploaded CSV
                (<code>{st.session_state.get('gat_active_file', '')}</code>): software energy comes from
                <code>software_energy_wh</code>, hardware energy is {hw_energy_source_note}. No simulated
                or hardcoded values are used.
                </div>""",
                unsafe_allow_html=True,
            )