# ============================================================================
# GreenAeroTester — shared UI helpers.
# This block is intentionally IDENTICAL (in spirit) to the one in Home.py /
# Dataset.py / Energy.py / Assurance.py / Prioritization.py / Baseline.py —
# see the note in Home.py for why each page reproduces it rather than
# importing a shared module. This copy is trimmed to only what the Export
# page needs.
#
# Phase 10 note (this page): the Export Center no longer uses load_dataset(),
# np.random-generated synthetic data, or any hardcoded dataset/report. It
# reads the SAME uploaded, validated dataset the Home page owns —
# st.session_state["gat_dataset"] — and generates every downloadable file
# (CSV, PDF, PNG, ZIP) directly from that CSV and the same scoring/
# prioritization/baseline-comparison logic used on the Prioritization and
# Baseline Comparison pages. If a signal an export needs isn't present in
# the uploaded CSV (e.g. hardware columns, an assurance_score/safety_level
# column), that specific export is disabled with a clear, professional
# message instead of being backed by fabricated numbers — every other
# export keeps working normally. Because this page always reads straight
# out of session state (never caches a dataset of its own), it automatically
# reflects whatever CSV is currently active on Home on its very next render.
#
# Phase 11 note (this page): all standalone Markdown (.md) reports have been
# removed. In their place, Section 3 now generates ONE comprehensive PDF
# report — combining the Home summary, validation summary, every dataset
# table, every available chart, energy analysis, assurance analysis, test
# prioritization, and baseline comparison — built fresh from whatever CSV is
# currently active in st.session_state["gat_dataset"]. Nothing here is
# hardcoded. The Full Package .zip bundles this same PDF instead of the old
# three .md/.pdf report pairs. Every other export on this page (per-table
# CSV/PDF downloads, per-chart PNG downloads) is unchanged.
# ============================================================================

import io
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import streamlit.components.v1 as components
from fpdf import FPDF
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
    """Identical lock UI to Home.py/Dataset.py/Energy.py/Assurance.py/
    Prioritization.py/Baseline.py: sidebar/nav stay visible but disabled,
    with a small explanatory note, whenever there's no active validated
    dataset."""
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


def fmt_num(x, decimals=0):
    return f"{x:,.{decimals}f}"


def apply_plotly_theme(fig, height=380):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(font=dict(color=CHART_COLORS["title"], size=15, family="Space Grotesk, sans-serif")),
        font=dict(family="Inter, sans-serif", color=CHART_COLORS["text"], size=12),
        margin=dict(l=10, r=10, t=40, b=10),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=CHART_COLORS["legend"])),
        xaxis=dict(gridcolor=CHART_COLORS["grid"], zerolinecolor=CHART_COLORS["grid"],
                   color=CHART_COLORS["axis_label"], tickfont=dict(color=CHART_COLORS["axis_label"])),
        yaxis=dict(gridcolor=CHART_COLORS["grid"], zerolinecolor=CHART_COLORS["grid"],
                   color=CHART_COLORS["axis_label"], tickfont=dict(color=CHART_COLORS["axis_label"])),
    )
    return fig


# ---------------------------------------------------------------------------
# Fixed, documented constants — used ONLY as fallbacks when the uploaded CSV
# doesn't already carry the real value (exact same pattern as every other
# page). Never used to fabricate numbers for rows that lack the underlying
# real column too.
# ---------------------------------------------------------------------------
CARBON_INTENSITY_G_PER_KWH = 475.0
SAFETY_LEVEL_ASSURANCE_MAP = {"DAL-A": 100.0, "DAL-B": 80.0, "DAL-C": 55.0, "DAL-D": 30.0}
COMPARISON_TOLERANCE_PCT = 10.0
FLIGHT_PHASE_ORDER = ["Takeoff", "Climb", "Cruise", "Turn", "Descent", "Approach",
                      "Landing", "Go-Around", "Emergency Landing"]
SAFETY_LEVELS_ORDER = ["DAL-A", "DAL-B", "DAL-C", "DAL-D"]

ALGORITHMS = [
    ("Default CI", "default_ci"),
    ("Random", "random"),
    ("Runtime Based", "runtime_based"),
    ("Failure History", "failure_history"),
    ("Energy Aware", "energy_aware"),
    ("Knapsack", "knapsack"),
]


# ---------------------------------------------------------------------------
# Flexible column lookup — identical pattern to Dataset.py (weather/fault)
# and Energy.py (CPU/hardware) for columns the shared upload validator on
# Home.py does NOT canonicalize.
# ---------------------------------------------------------------------------
def _norm(s):
    return str(s).strip().lower().replace(" ", "_")


def _find_column(columns, aliases):
    normalized = {_norm(c): c for c in columns}
    for a in aliases:
        if _norm(a) in normalized:
            return normalized[_norm(a)]
    return None


WEATHER_ALIASES = ["weather_condition", "weather"]
FAULT_ALIASES = ["failure_type", "fault_type", "fault"]
CPU_ALIASES = ["cpu_usage_pct", "cpu_usage", "avg_cpu_pct", "cpu_percent", "cpu_pct", "cpu"]
VOLTAGE_ALIASES = ["voltage_v", "voltage", "volts"]
CURRENT_ALIASES = ["current_a", "current", "amps", "amperage"]
HW_POWER_ALIASES = ["hardware_power_w", "hw_power_w", "power_trace_w", "hardware_avg_power_w"]
HW_ENERGY_ALIASES = ["hardware_energy_wh", "hw_energy_wh", "hardware_energy"]
HW_DEVICE_ALIASES = ["device_id", "hardware_device_id", "hw_device_id", "meter_id"]
HW_STATUS_ALIASES = ["hardware_status", "hw_status", "measurement_status", "hw_measurement_status"]


# ============================================================================
# Data model — everything below is built ENTIRELY from the uploaded CSV
# (st.session_state["gat_dataset"]). No load_dataset(), no random values.
# ============================================================================

def build_cleaned_dataset(df):
    """SRS §9 cleaning: drops exact duplicate rows and invalid rows (missing
    or negative runtime_s / software_energy_wh). Documents what was removed
    rather than silently discarding it — the counts are surfaced on the page
    and in the summary report. Never fabricates or fills in values."""
    before = len(df)
    cleaned = df.drop_duplicates().copy()
    invalid_mask = (
        cleaned["runtime_s"].isna() | cleaned["software_energy_wh"].isna() |
        (cleaned["runtime_s"] < 0) | (cleaned["software_energy_wh"] < 0)
    )
    removed_invalid = int(invalid_mask.sum())
    cleaned = cleaned[~invalid_mask].reset_index(drop=True)
    removed_duplicates = before - len(df.drop_duplicates())
    return cleaned, dict(removed_duplicates=int(removed_duplicates), removed_invalid=removed_invalid)


def build_scoring(df):
    """Aggregates the uploaded, run-level CSV up to one row per test (a
    'unit'), identical in approach to Prioritization.py / Baseline.py so all
    three pages always agree on the same numbers. Uses `test_id` as the unit
    when the CSV provides one, otherwise falls back to `scenario_id`."""
    unit_col = "test_id" if "test_id" in df.columns else "scenario_id"

    has_status = "status" in df.columns
    has_mandatory = "mandatory" in df.columns
    has_safety = "safety_level" in df.columns
    has_assurance_raw = "assurance_score" in df.columns
    has_carbon_raw = "carbon_gco2" in df.columns

    agg_dict = {"runtime_s": "median", "software_energy_wh": "median"}
    if unit_col != "scenario_id":
        agg_dict["scenario_id"] = "first"
    if has_assurance_raw:
        agg_dict["assurance_score"] = "median"
    if has_carbon_raw:
        agg_dict["carbon_gco2"] = "median"
    if has_safety:
        agg_dict["safety_level"] = lambda s: (s.dropna().mode().iat[0] if not s.dropna().mode().empty else np.nan)

    grouped = (
        df.groupby(unit_col)
        .agg(agg_dict)
        .reset_index()
        .rename(columns={unit_col: "unit_id", "runtime_s": "median_runtime_s",
                          "software_energy_wh": "median_energy_wh"})
    )

    if has_status:
        fail_rate = df.assign(_fail=(df["status"] != "Clean")).groupby(unit_col)["_fail"].mean()
        grouped["failure_rate"] = grouped["unit_id"].map(fail_rate).fillna(0.0)
    else:
        grouped["failure_rate"] = np.nan

    if has_mandatory:
        mand = df.groupby(unit_col)["mandatory"].apply(lambda s: bool(s.astype(bool).any()))
        grouped["mandatory"] = grouped["unit_id"].map(mand).fillna(False)
    else:
        grouped["mandatory"] = False

    if has_assurance_raw:
        assurance_source = "assurance_score column"
        grouped["assurance_score"] = pd.to_numeric(grouped["assurance_score"], errors="coerce")
        assurance_available = grouped["assurance_score"].notna().any()
    elif has_safety:
        assurance_source = "safety_level column (mapped)"
        grouped["assurance_score"] = grouped["safety_level"].map(SAFETY_LEVEL_ASSURANCE_MAP)
        assurance_available = grouped["assurance_score"].notna().any()
    else:
        assurance_source = None
        grouped["assurance_score"] = np.nan
        assurance_available = False

    if has_carbon_raw:
        carbon_source = "carbon_gco2 column"
        grouped["median_carbon_g"] = pd.to_numeric(grouped["carbon_gco2"], errors="coerce")
        grouped["median_carbon_g"] = grouped["median_carbon_g"].fillna(
            grouped["median_energy_wh"] / 1000.0 * CARBON_INTENSITY_G_PER_KWH)
    else:
        carbon_source = f"estimated @ {int(CARBON_INTENSITY_G_PER_KWH)} gCO2/kWh"
        grouped["median_carbon_g"] = grouped["median_energy_wh"] / 1000.0 * CARBON_INTENSITY_G_PER_KWH

    grouped["utility_score"] = np.where(
        (grouped["median_energy_wh"] > 0) & grouped["assurance_score"].notna(),
        grouped["assurance_score"] / grouped["median_energy_wh"], np.nan,
    )

    meta = dict(
        unit_col=unit_col, has_status=has_status, has_mandatory=has_mandatory,
        has_safety=has_safety, has_assurance_raw=has_assurance_raw,
        assurance_source=assurance_source, assurance_available=bool(assurance_available),
        carbon_source=carbon_source,
    )
    return grouped, meta


def knapsack_01(optional, budget_remaining, n_bins=1500):
    if optional.empty or budget_remaining <= 0:
        return optional.iloc[0:0]
    weights = optional["median_energy_wh"].to_numpy()
    values = optional["assurance_score"].fillna(0.0).to_numpy()
    n = len(weights)
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


def select_units(scoring, algo_key, energy_budget_frac, seed=7):
    total_energy = scoring["median_energy_wh"].sum()
    budget = total_energy * max(0.0, min(1.0, energy_budget_frac))
    mandatory_df = scoring[scoring["mandatory"] == True]  # noqa: E712
    optional_df = scoring[scoring["mandatory"] != True].copy()  # noqa: E712
    budget_remaining = budget - mandatory_df["median_energy_wh"].sum()

    if algo_key == "default_ci":
        optional_df = optional_df.sort_values("unit_id")
    elif algo_key == "random":
        optional_df = optional_df.sample(frac=1.0, random_state=seed)
    elif algo_key == "runtime_based":
        optional_df = optional_df.sort_values("median_runtime_s")
    elif algo_key == "failure_history":
        optional_df = optional_df.sort_values("failure_rate", ascending=False)
    elif algo_key == "energy_aware":
        optional_df = optional_df.sort_values("utility_score", ascending=False, na_position="last")
    elif algo_key == "knapsack":
        chosen = knapsack_01(optional_df, budget_remaining)
        return pd.concat([mandatory_df, chosen])
    else:
        raise ValueError(f"Unknown algorithm: {algo_key}")

    if budget_remaining <= 0:
        chosen = optional_df.iloc[0:0]
    else:
        cum_energy = optional_df["median_energy_wh"].cumsum()
        chosen = optional_df[cum_energy <= budget_remaining]
    return pd.concat([mandatory_df, chosen])


def summarize_selection(scoring, selected, meta):
    full_energy = scoring["median_energy_wh"].sum()
    full_runtime = scoring["median_runtime_s"].sum()
    full_carbon = scoring["median_carbon_g"].sum()
    sel_energy = selected["median_energy_wh"].sum()
    sel_runtime = selected["median_runtime_s"].sum()
    sel_carbon = selected["median_carbon_g"].sum()

    result = dict(
        num_selected=int(len(selected)), num_total=int(len(scoring)),
        total_energy_wh=float(sel_energy), total_runtime_s=float(sel_runtime),
        total_carbon_g=float(sel_carbon),
        energy_saved_pct=float(100 * (full_energy - sel_energy) / full_energy) if full_energy else 0.0,
        runtime_saved_pct=float(100 * (full_runtime - sel_runtime) / full_runtime) if full_runtime else 0.0,
        carbon_saved_pct=float(100 * (full_carbon - sel_carbon) / full_carbon) if full_carbon else 0.0,
    )
    if meta["assurance_available"]:
        full_assurance = scoring["assurance_score"].fillna(0).sum()
        sel_assurance = selected["assurance_score"].fillna(0).sum()
        result["assurance_retained_pct"] = float(100 * sel_assurance / full_assurance) if full_assurance else 0.0
    else:
        result["assurance_retained_pct"] = None
    if meta["has_mandatory"]:
        mand_total = int(scoring["mandatory"].sum())
        mand_selected = int(selected["mandatory"].sum())
        result["mandatory_total"] = mand_total
        result["mandatory_selected"] = mand_selected
        result["mandatory_coverage_pct"] = (100 * mand_selected / mand_total) if mand_total else 100.0
    else:
        result["mandatory_total"] = None
        result["mandatory_selected"] = None
        result["mandatory_coverage_pct"] = None
    return result


def build_software_energy_metrics(df, has_carbon):
    """Software Energy Metrics export — read/derived directly from the
    uploaded CSV, one row per run."""
    cols = ["run_id", "scenario_id"]
    if "test_id" in df.columns:
        cols.append("test_id")
    out = df[cols].copy()
    out["runtime_s"] = df["runtime_s"]
    out["software_energy_wh"] = df["software_energy_wh"]
    if has_carbon:
        out["carbon_gco2"] = df["carbon_gco2"]
        out["carbon_source"] = "csv_carbon_gco2_column"
    else:
        out["carbon_gco2"] = df["software_energy_wh"] / 1000.0 * CARBON_INTENSITY_G_PER_KWH
        out["carbon_source"] = f"estimated_{int(CARBON_INTENSITY_G_PER_KWH)}_gco2_per_kwh"
    out["measurement_source"] = "cpu_based_estimate (uploaded CSV)"
    return out


def build_hardware_energy_metrics(df, voltage_col, current_col, hw_power_col, hw_energy_col,
                                   hw_device_col, hw_status_col):
    """Hardware Energy Metrics export — only built from columns actually
    present in the uploaded CSV (voltage/current/power/energy/device/status
    aliases). Returns (dataframe_or_None, energy_source_note_or_None)."""
    if not any([voltage_col, current_col, hw_power_col, hw_energy_col]):
        return None, None

    out = pd.DataFrame({"run_id": df["run_id"], "scenario_id": df["scenario_id"]})
    power_source = None
    if voltage_col:
        out["voltage_v"] = pd.to_numeric(df[voltage_col], errors="coerce")
    if current_col:
        out["current_a"] = pd.to_numeric(df[current_col], errors="coerce")
    if hw_power_col:
        out["device_power_w"] = pd.to_numeric(df[hw_power_col], errors="coerce")
        power_source = f"`{hw_power_col}` column"
    elif voltage_col and current_col:
        out["device_power_w"] = out["voltage_v"] * out["current_a"]
        power_source = f"`{voltage_col}` x `{current_col}`"

    energy_source = None
    if hw_energy_col:
        out["device_energy_wh"] = pd.to_numeric(df[hw_energy_col], errors="coerce")
        energy_source = f"`{hw_energy_col}` column"
    elif "device_power_w" in out.columns and out["device_power_w"].notna().any():
        out["device_energy_wh"] = out["device_power_w"] * df["runtime_s"] / 3600.0
        energy_source = f"device_power_w ({power_source}) x runtime_s / 3600"

    if hw_device_col:
        out["device_id"] = df[hw_device_col]
    if hw_status_col:
        out["hardware_status"] = df[hw_status_col]
    out["measurement_source"] = "uploaded_csv_hardware_columns"

    has_energy = "device_energy_wh" in out.columns and out["device_energy_wh"].notna().any()
    return out, (energy_source if has_energy else None)


def build_merged_comparison_metrics(df, hw_df):
    """Merged Comparison Metrics export — software vs hardware energy per
    run. Only produced when the hardware export above yields usable
    per-run energy values."""
    if hw_df is None or "device_energy_wh" not in hw_df.columns or not hw_df["device_energy_wh"].notna().any():
        return None

    merged = pd.DataFrame({
        "run_id": df["run_id"], "scenario_id": df["scenario_id"],
        "software_energy_wh": df["software_energy_wh"],
    })
    if "test_id" in df.columns:
        merged["test_id"] = df["test_id"]
    if "status" in df.columns:
        merged["status"] = df["status"]
    merged["hardware_energy_wh"] = hw_df["device_energy_wh"].values
    merged = merged.dropna(subset=["software_energy_wh", "hardware_energy_wh"])
    if merged.empty:
        return None

    merged["delta_wh"] = merged["hardware_energy_wh"] - merged["software_energy_wh"]
    merged["delta_pct"] = np.where(merged["software_energy_wh"] > 0,
                                    100 * merged["delta_wh"] / merged["software_energy_wh"], np.nan)
    merged["within_tolerance"] = merged["delta_pct"].abs() <= COMPARISON_TOLERANCE_PCT
    return merged.reset_index(drop=True)


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------
def _pdf_safe(text: str) -> str:
    replacements = {
        "—": "-", "–": "-", "…": "...", "’": "'", "‘": "'",
        "“": '"', "”": '"', "·": "-", "•": "-", "→": "->",
        "≤": "<=", "≥": ">=", "×": "x", "°": " deg",
    }
    for uni, ascii_ in replacements.items():
        text = text.replace(uni, ascii_)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def df_to_pdf_bytes(df: pd.DataFrame, title: str) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, _pdf_safe(title), ln=True)

    if df.empty:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, "No rows available for this export.", ln=True)
        return bytes(pdf.output())

    col_width = 277 / max(1, len(df.columns))
    row_height = 6
    pdf.set_font("Helvetica", "B", 8)
    for col in df.columns:
        pdf.cell(col_width, row_height, _pdf_safe(str(col))[:22], border=1)
    pdf.ln(row_height)
    pdf.set_font("Helvetica", "", 8)
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(col_width, row_height, _pdf_safe(str(val))[:22], border=1)
        pdf.ln(row_height)
    return bytes(pdf.output())


def report_to_pdf_bytes(report_text: str) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Courier", "", 8)
    for line in report_text.splitlines():
        text = _pdf_safe(line) if line.strip() else " "
        pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def _fig_png(fig, width=850, height=430, scale=2):
    return fig.to_image(format="png", width=width, height=height, scale=scale)
def _fit_text(pdf, text, max_width):
    """Truncates text (with an ellipsis) so it never exceeds max_width in
    the current font — prevents table cell text from overflowing into the
    next column, which was causing the overlapping text/columns issue."""
    text = str(text)
    if pdf.get_string_width(text) <= max_width:
        return text
    ellipsis = "..."
    while text and pdf.get_string_width(text + ellipsis) > max_width:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis

# ============================================================================
# PAGE: Export Center
#
# Locked state mirrors every other page exactly: if there is no active,
# validated dataset in st.session_state["gat_dataset"], this page shows the
# same lock notice / prompt-to-upload message and stops — it never falls
# back to load_dataset(), random values, or any hardcoded export.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester — Export", page_icon="📦",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_brand()

stage = st.session_state.get("gat_stage")
dataset = st.session_state.get("gat_dataset")

if stage != "unlocked" or dataset is None:
    sidebar_lock_notice()
    page_header(
        "PHASE 3 · EXPORT",
        "Export Center",
        "Download every dataset stage, metric table, figure and report for final handover",
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
df = dataset
validation_summary = st.session_state.get("gat_validation_summary") or {}
sidebar_status_footer(df, filename=st.session_state.get("gat_active_file"))

# ---- Column availability ----------------------------------------------------
has_test_id = "test_id" in df.columns
has_status = "status" in df.columns
has_mandatory = "mandatory" in df.columns
has_safety = "safety_level" in df.columns
has_assurance_raw = "assurance_score" in df.columns
has_carbon = "carbon_gco2" in df.columns
has_flight_phase = "flight_phase" in df.columns
has_avg_power = "avg_power_w" in df.columns
weather_col = _find_column(df.columns, WEATHER_ALIASES)
fault_col = _find_column(df.columns, FAULT_ALIASES)
cpu_col = _find_column(df.columns, CPU_ALIASES)
voltage_col = _find_column(df.columns, VOLTAGE_ALIASES)
current_col = _find_column(df.columns, CURRENT_ALIASES)
hw_power_col = _find_column(df.columns, HW_POWER_ALIASES)
hw_energy_col = _find_column(df.columns, HW_ENERGY_ALIASES)
hw_device_col = _find_column(df.columns, HW_DEVICE_ALIASES)
hw_status_col = _find_column(df.columns, HW_STATUS_ALIASES)

page_header(
    "PHASE 3 · EXPORT",
    "Export Center",
    "Download every dataset stage, metric table, figure and report for final handover",
    pill_text=f"source: {st.session_state.get('gat_active_file', 'uploaded CSV')}",
)

# ---- Build the shared data model once ---------------------------------------
scoring, meta = build_scoring(df)
unit_label = "tests" if meta["unit_col"] == "test_id" else "scenarios"
cleaned_df, clean_info = build_cleaned_dataset(df)
software_energy_metrics = build_software_energy_metrics(df, has_carbon)
hardware_energy_metrics, hw_energy_source = build_hardware_energy_metrics(
    df, voltage_col, current_col, hw_power_col, hw_energy_col, hw_device_col, hw_status_col)
merged_comparison_metrics = build_merged_comparison_metrics(df, hardware_energy_metrics)
has_hardware_export = hardware_energy_metrics is not None and hw_energy_source is not None
has_comparison_export = merged_comparison_metrics is not None

DEFAULT_BUDGET_PCT = 60
default_budget = DEFAULT_BUDGET_PCT / 100.0
default_algo_key = "energy_aware" if meta["assurance_available"] else "default_ci"
default_algo_label = dict(ALGORITHMS)[default_algo_key] if False else \
    {key: label for label, key in ALGORITHMS}[default_algo_key]

prioritization_selected = select_units(scoring, default_algo_key, default_budget)
prioritization_summary = summarize_selection(scoring, prioritization_selected, meta)

prioritization_decisions = prioritization_selected.copy()
if default_algo_key == "energy_aware":
    prioritization_decisions = prioritization_decisions.sort_values(
        "utility_score", ascending=False, na_position="last")
elif default_algo_key == "knapsack":
    prioritization_decisions = prioritization_decisions.sort_values(
        "assurance_score", ascending=False, na_position="last")
else:
    prioritization_decisions = prioritization_decisions.sort_values(["mandatory", "unit_id"], ascending=[False, True])
prioritization_decisions = prioritization_decisions.reset_index(drop=True)
prioritization_decisions.insert(0, "rank", range(1, len(prioritization_decisions) + 1))
prioritization_decisions["method"] = default_algo_label
prioritization_decisions["budget_fraction"] = default_budget
prioritization_decisions = prioritization_decisions.rename(columns={"unit_id": meta["unit_col"]})

baseline_availability = {
    "default_ci": (True, None),
    "random": (True, None),
    "runtime_based": (True, None),
    "failure_history": (meta["has_status"], "requires a `status` column"),
    "energy_aware": (meta["assurance_available"], "requires an `assurance_score` or `safety_level` column"),
    "knapsack": (meta["assurance_available"], "requires an `assurance_score` or `safety_level` column"),
}
baseline_rows = []
for label, key in ALGORITHMS:
    ok, _ = baseline_availability[key]
    if not ok:
        continue
    sel = select_units(scoring, key, default_budget)
    s = summarize_selection(scoring, sel, meta)
    s["method"] = label
    baseline_rows.append(s)
baseline_comparison = pd.DataFrame(baseline_rows) if baseline_rows else pd.DataFrame()
if not baseline_comparison.empty:
    order_cols = ["method", "num_selected", "num_total", "total_energy_wh", "total_runtime_s",
                  "total_carbon_g", "assurance_retained_pct", "mandatory_coverage_pct",
                  "energy_saved_pct", "runtime_saved_pct", "carbon_saved_pct"]
    baseline_comparison = baseline_comparison[order_cols]

has_runtime_data = df["runtime_s"].notna().any()

# ============================================================================
# SECTION 1 — Datasets & Metric Tables (CSV + PDF, individually)
# ============================================================================
section_title("Datasets & Metrics", tag="CSV / PDF")

FILES = {
    "raw_dataset.csv": (df, "Uploaded Raw Dataset — exactly as uploaded", True, None),
    "cleaned_dataset.csv": (cleaned_df, "Cleaned Dataset — duplicates & invalid rows removed (SRS §9)", True, None),
    "final_dataset.csv": (scoring.rename(columns={"unit_id": meta["unit_col"]}),
                          "Final Dataset — scored, feature-engineered table", True, None),
    "software_energy_metrics.csv": (software_energy_metrics, "Software Energy Metrics — from uploaded CSV", True, None),
    "hardware_energy_metrics.csv": (
        hardware_energy_metrics if has_hardware_export else pd.DataFrame(),
        "Hardware Energy Metrics — from uploaded hardware columns", has_hardware_export,
        "requires voltage/current/power/energy hardware columns in the uploaded CSV",
    ),
    "merged_comparison_metrics.csv": (
        merged_comparison_metrics if has_comparison_export else pd.DataFrame(),
        "Merged Comparison — software vs hardware energy", has_comparison_export,
        "requires hardware energy data in the uploaded CSV",
    ),
    "prioritization_decisions.csv": (
        prioritization_decisions, f"Prioritization Decisions — {default_algo_label} @ {DEFAULT_BUDGET_PCT}%",
        True, None,
    ),
    "baseline_comparison.csv": (
        baseline_comparison, "Baseline Comparison — all available methods @ 60%",
        not baseline_comparison.empty, "no prioritization method could be evaluated for this dataset",
    ),
}

cols = st.columns(4)
for i, (fname, (tbl, label, available, reason)) in enumerate(FILES.items()):
    with cols[i % 4]:
        accent = COLORS["accent2"] if available else COLORS["text_faint"]
        value_txt = f"{len(tbl):,} rows" if available else "unavailable"
        st.markdown(
            f"""<div class="gat-card" style="--accent-color:{accent}; margin-bottom:6px;">
                <div class="gat-card-label">{label}</div>
                <div class="gat-card-value" style="font-size:1.1rem;">{value_txt}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if available:
            dc1, dc2 = st.columns(2)
            with dc1:
                st.download_button("⬇ CSV", tbl.to_csv(index=False).encode(), file_name=fname,
                                    mime="text/csv", key=f"dl_csv_{fname}", use_container_width=True)
            with dc2:
                pdf_name = fname.replace(".csv", ".pdf")
                st.download_button("📄 PDF", df_to_pdf_bytes(tbl, fname), file_name=pdf_name,
                                    mime="application/pdf", key=f"dl_pdf_{fname}", use_container_width=True)
        else:
            st.caption(f"⚠ Not available — {reason}.")
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# ============================================================================
# SECTION 2 — Figures (charts as downloadable PNG)
# ============================================================================
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
section_title("Figures", tag="charts as PNG")
st.caption("Every chart this dataset can support, generated fresh from the uploaded CSV, as a standalone image "
           "for slides and reports. Charts that need a column your CSV doesn't have are simply omitted.")


def _chart_status_donut():
    counts = df["status"].value_counts()
    fig = go.Figure(go.Pie(labels=counts.index, values=counts.values, hole=0.55,
                            marker=dict(colors=CHART_COLORS["pie"]), textinfo="label+percent"))
    fig.update_layout(title="Run Status Breakdown")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_energy_by_phase():
    phase_energy = df.groupby("flight_phase")["software_energy_wh"].sum().sort_values() / 1000.0
    fig = go.Figure(go.Bar(x=phase_energy.values, y=phase_energy.index, orientation="h",
                            marker=dict(color=CHART_COLORS["bar"])))
    fig.update_layout(title="Software Energy by Flight Phase (kWh)")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_top_scenarios_energy():
    top = df.groupby("scenario_id")["software_energy_wh"].sum().sort_values(ascending=False).head(15) / 1000.0
    fig = go.Figure(go.Bar(x=top.values[::-1], y=top.index[::-1], orientation="h",
                            marker=dict(color=CHART_COLORS["bar"])))
    fig.update_layout(title="Top 15 Scenarios by Software Energy (kWh)")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_weather_mix():
    counts = df[weather_col].value_counts()
    fig = go.Figure(go.Pie(labels=counts.index, values=counts.values, hole=0.5,
                            marker=dict(colors=CHART_COLORS["pie"])))
    fig.update_layout(title="Weather Condition Mix")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_fault_type():
    counts = df[fault_col].value_counts()
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker=dict(color=CHART_COLORS["bar"])))
    fig.update_layout(title="Fault Type Distribution")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_safety_level():
    counts = df["safety_level"].value_counts().reindex(
        [lvl for lvl in SAFETY_LEVELS_ORDER if lvl in df["safety_level"].unique()])
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker=dict(color=CHART_COLORS["line"])))
    fig.update_layout(title="Safety Level (DAL) Distribution")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_runtime_distribution():
    fig = go.Figure(go.Histogram(x=df["runtime_s"].dropna(), marker=dict(color=CHART_COLORS["bar"]), nbinsx=40))
    fig.update_layout(title="Runtime Distribution (seconds)")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_avg_power_by_status():
    by_status = df.groupby("status")["avg_power_w"].mean()
    fig = go.Figure(go.Bar(x=by_status.index, y=by_status.values, marker=dict(color=CHART_COLORS["line"])))
    fig.update_layout(title="Average Power by Run Status (W)")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_assurance_hist():
    fig = go.Figure(go.Histogram(x=scoring["assurance_score"].dropna(),
                                  marker=dict(color=CHART_COLORS["bar"]), nbinsx=30))
    fig.update_layout(title="Assurance Score Distribution")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_assurance_vs_energy():
    s = scoring.dropna(subset=["assurance_score", "median_energy_wh"])
    fig = go.Figure(go.Scatter(x=s["median_energy_wh"], y=s["assurance_score"], mode="markers",
                                marker=dict(color=CHART_COLORS["bar"], size=6, opacity=0.6)))
    fig.update_layout(title="Assurance Score vs Median Energy (Wh)",
                       xaxis_title="Median Energy (Wh)", yaxis_title="Assurance Score")
    return _fig_png(apply_plotly_theme(fig, 380))


def _chart_top_utility():
    top = scoring.dropna(subset=["utility_score"]).sort_values("utility_score", ascending=False).head(15)
    fig = go.Figure(go.Bar(x=top["utility_score"], y=top["unit_id"], orientation="h",
                            marker=dict(color=CHART_COLORS["bar"])))
    fig.update_layout(title="Top 15 Tests by Utility Score (Energy-Aware)")
    return _fig_png(apply_plotly_theme(fig, 420))


def _chart_baseline_comparison():
    b = baseline_comparison
    fig = go.Figure()
    if b["assurance_retained_pct"].notna().any():
        fig.add_trace(go.Bar(name="Assurance Retained %", x=b["method"], y=b["assurance_retained_pct"],
                              marker_color=CHART_COLORS["bar"]))
    fig.add_trace(go.Bar(name="Energy Saved %", x=b["method"], y=b["energy_saved_pct"],
                          marker_color=CHART_COLORS["line"]))
    fig.update_layout(barmode="group", title="Baseline Comparison — Assurance vs Energy Saved", xaxis_tickangle=-20)
    return _fig_png(apply_plotly_theme(fig, 420))


def _chart_sw_vs_hw_energy():
    m = merged_comparison_metrics
    fig = go.Figure(go.Scatter(
        x=m["software_energy_wh"], y=m["hardware_energy_wh"], mode="markers",
        marker=dict(color=CHART_COLORS["bar"], size=5, opacity=0.5)))
    lo = min(m["software_energy_wh"].min(), m["hardware_energy_wh"].min())
    hi = max(m["software_energy_wh"].max(), m["hardware_energy_wh"].max())
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines",
                              line=dict(color=CHART_COLORS["line"], dash="dash"), name="Perfect agreement"))
    fig.update_layout(title="Software vs Hardware Energy per Run (Wh)",
                       xaxis_title="Software estimate (Wh)", yaxis_title="Hardware measured (Wh)")
    return _fig_png(apply_plotly_theme(fig, 420))


FIGURE_BUILDERS = {}
if has_status:
    FIGURE_BUILDERS["run_status_breakdown.png"] = _chart_status_donut
if has_flight_phase:
    FIGURE_BUILDERS["energy_by_flight_phase.png"] = _chart_energy_by_phase
else:
    FIGURE_BUILDERS["top_scenarios_by_energy.png"] = _chart_top_scenarios_energy
if weather_col:
    FIGURE_BUILDERS["weather_condition_mix.png"] = _chart_weather_mix
if fault_col:
    FIGURE_BUILDERS["fault_type_distribution.png"] = _chart_fault_type
if has_safety:
    FIGURE_BUILDERS["safety_level_distribution.png"] = _chart_safety_level
if has_runtime_data:
    FIGURE_BUILDERS["runtime_distribution.png"] = _chart_runtime_distribution
if has_avg_power and has_status:
    FIGURE_BUILDERS["avg_power_by_status.png"] = _chart_avg_power_by_status
if meta["assurance_available"]:
    FIGURE_BUILDERS["assurance_score_distribution.png"] = _chart_assurance_hist
    FIGURE_BUILDERS["assurance_vs_energy.png"] = _chart_assurance_vs_energy
    FIGURE_BUILDERS["top_utility_tests.png"] = _chart_top_utility
if not baseline_comparison.empty:
    FIGURE_BUILDERS["baseline_comparison_chart.png"] = _chart_baseline_comparison
if has_comparison_export:
    FIGURE_BUILDERS["software_vs_hardware_energy.png"] = _chart_sw_vs_hw_energy


def render_all_figures(cache_key):
    """Renders every available chart to PNG once, showing a progress bar
    since kaleido calls are the slow part. Caching across reruns is
    already handled by the gat_figures/gat_figures_key session-state gate
    at each call site below, so this function itself doesn't need
    @st.cache_data — it's only ever invoked when a real (re)render is
    needed. cache_key still ties this render to the active file + row
    count, matching the previous behavior."""
    total = len(FIGURE_BUILDERS)
    figs = {}
    progress_bar = st.progress(0, text=f"Rendering figures... (0/{total})")
    for i, (name, builder) in enumerate(FIGURE_BUILDERS.items(), start=1):
        figs[name] = builder()
        progress_bar.progress(i / total, text=f"Rendering figures... ({i}/{total})")
    progress_bar.empty()
    return figs


figures_cache_key = (st.session_state.get("gat_active_file"), len(df))

if not FIGURE_BUILDERS:
    st.info("No chartable columns were found in the uploaded CSV, so no figures are available for this dataset.")
else:
    if "gat_figures" not in st.session_state or st.session_state.get("gat_figures_key") != figures_cache_key:
        st.session_state["gat_figures"] = None
        st.session_state["gat_figures_key"] = figures_cache_key

    if st.session_state["gat_figures"] is None:
        if st.button("🖼 Render Figures", use_container_width=True):
            st.session_state["gat_figures"] = render_all_figures(figures_cache_key)
            st.rerun()
    else:
        figs = st.session_state["gat_figures"]
        fcols = st.columns(4)
        for i, (fname, png_bytes) in enumerate(figs.items()):
            with fcols[i % 4]:
                st.download_button("🖼 " + fname, png_bytes, file_name=fname, mime="image/png",
                                    key=f"dl_fig_{fname}", use_container_width=True)

# ============================================================================
# Report text builders — used ONLY internally now, to assemble the single
# comprehensive PDF in Section 3 below. No .md file is ever written.
# ============================================================================

total_scenarios = df["scenario_id"].nunique()
total_runs = len(df)
total_energy_kwh = df["software_energy_wh"].sum() / 1000.0
carbon_kg_series = (df["carbon_gco2"] / 1000.0) if has_carbon else \
    (df["software_energy_wh"] / 1000.0 * CARBON_INTENSITY_G_PER_KWH / 1000.0)
total_carbon_kg = float(carbon_kg_series.sum())
mandatory_tests = int(df.loc[df["mandatory"].astype(bool), "scenario_id"].nunique()) if has_mandatory else None
status_counts = df["status"].value_counts() if has_status else pd.Series(dtype=int)
hw_agree_pct = (100 * merged_comparison_metrics["within_tolerance"].mean()) if has_comparison_export else None


def build_summary_report_text():
    """Home page summary + validation summary + energy analysis +
    carbon/assurance analysis — built entirely from the currently uploaded
    dataset."""
    lines = [
        "# GreenAeroTester — Summary Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Source file: {st.session_state.get('gat_active_file', 'uploaded CSV')}",
        "",
        "## Dataset Summary",
        f"- Total scenarios: {total_scenarios}",
        f"- Total runs: {total_runs}",
        f"- Unit of analysis: {meta['unit_col']} ({unit_label})",
        f"- Mandatory tests: {mandatory_tests if mandatory_tests is not None else 'N/A (no `mandatory` column)'}",
        "",
        "## Validation Summary",
        f"- Missing values: {validation_summary.get('missing_values', 'N/A')}",
        f"- Duplicate rows: {validation_summary.get('duplicate_rows', 'N/A')}",
        f"- Invalid rows: {validation_summary.get('invalid_rows', 'N/A')}",
        f"- Cleaned dataset removed: {clean_info['removed_duplicates']} duplicate row(s), "
        f"{clean_info['removed_invalid']} invalid row(s)",
        "",
        "## Energy Summary",
        f"- Total software energy: {total_energy_kwh:.3f} kWh",
        f"- Average runtime per run: {df['runtime_s'].mean():.1f} s" if has_runtime_data else "- Runtime data unavailable",
    ]
    if has_status:
        lines += [
            f"- Clean runs: {int(status_counts.get('Clean', 0))}",
            f"- Failed runs: {int(status_counts.get('Failed', 0))}",
            f"- Timeout runs: {int(status_counts.get('Timeout', 0))}",
            f"- Crashed runs: {int(status_counts.get('Crashed', 0))}",
        ]
    else:
        lines.append("- Run status data unavailable (no `status` column in the uploaded CSV)")

    lines += [
        "",
        "## Carbon Summary",
        f"- Total estimated carbon: {total_carbon_kg:.3f} kg CO2e",
        f"- Source: {'CSV `carbon_gco2` column' if has_carbon else f'estimated @ {int(CARBON_INTENSITY_G_PER_KWH)} gCO2/kWh (documented fallback)'}",
    ]
    if has_comparison_export:
        lines.append(f"- Software/hardware agreement within {COMPARISON_TOLERANCE_PCT:.0f}%: {hw_agree_pct:.1f}% of compared runs")

    lines += ["", "## Assurance Summary"]
    if meta["assurance_available"]:
        valid_scores = scoring["assurance_score"].dropna()
        lines += [
            f"- Source: {meta['assurance_source']}",
            f"- Mean assurance score: {valid_scores.mean():.1f}",
            f"- Score range: {valid_scores.min():.1f} - {valid_scores.max():.1f}",
        ]
    else:
        lines.append("- Not available: no `assurance_score` or `safety_level` column in the uploaded CSV")

    lines += ["", "## Known Limitations"]
    if not has_hardware_export:
        lines.append("- No hardware measurement columns were found in the uploaded CSV — hardware energy "
                      "and software/hardware comparison exports are unavailable.")
    if not meta["assurance_available"]:
        lines.append("- No assurance data was found — assurance-dependent exports (Energy Aware / Knapsack "
                      "prioritization, assurance charts) are unavailable.")
    return "\n".join(lines)


summary_report_text = build_summary_report_text()


def build_prioritization_report_text():
    lines = [
        "# GreenAeroTester — Prioritization Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Source file: {st.session_state.get('gat_active_file', 'uploaded CSV')}",
        "",
        f"Selected Algorithm: {default_algo_label}",
        f"Energy Budget: {DEFAULT_BUDGET_PCT}% of full-suite median energy",
        f"Unit of analysis: {meta['unit_col']} ({unit_label})",
        "",
        "## Selection Summary",
        f"- Tests selected: {prioritization_summary['num_selected']} of {prioritization_summary['num_total']}",
        f"- Energy used: {prioritization_summary['total_energy_wh']/1000:.3f} kWh "
        f"({prioritization_summary['energy_saved_pct']:.1f}% saved vs. full suite)",
    ]
    if has_runtime_data:
        lines.append(f"- Runtime used: {prioritization_summary['total_runtime_s']/60:.1f} min "
                     f"({prioritization_summary['runtime_saved_pct']:.1f}% saved vs. full suite)")
    if prioritization_summary["assurance_retained_pct"] is not None:
        lines.append(f"- Assurance retained: {prioritization_summary['assurance_retained_pct']:.1f}%")
    else:
        lines.append("- Assurance retained: N/A (no assurance data in dataset)")
    if meta["has_mandatory"]:
        lines.append(f"- Mandatory tests included: {prioritization_summary['mandatory_selected']} / "
                     f"{prioritization_summary['mandatory_total']} "
                     f"({prioritization_summary['mandatory_coverage_pct']:.0f}% coverage)")
    else:
        lines.append("- Mandatory tests included: N/A (no `mandatory` column in dataset)")

    lines += ["", "## Ranked Test List (top 30)"]
    show_cols = [meta["unit_col"], "mandatory", "median_runtime_s", "median_energy_wh"]
    if meta["assurance_available"]:
        show_cols += ["assurance_score", "utility_score"]
    top30 = prioritization_decisions.head(30)[["rank"] + show_cols]
    lines.append(top30.round(2).to_string(index=False))
    return "\n".join(lines)


prioritization_report_text = build_prioritization_report_text()


def build_baseline_report_text():
    lines = [
        "# GreenAeroTester — Baseline Comparison Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Source file: {st.session_state.get('gat_active_file', 'uploaded CSV')}",
        f"Reference budget: {DEFAULT_BUDGET_PCT}% of full-suite median energy",
        "",
    ]
    if baseline_comparison.empty:
        lines.append("No prioritization method could be evaluated for this dataset.")
        return "\n".join(lines)

    display = baseline_comparison.copy()
    display["total_energy_kwh"] = (display["total_energy_wh"] / 1000).round(3)
    display["total_runtime_min"] = (display["total_runtime_s"] / 60).round(1)
    display["total_carbon_kg"] = (display["total_carbon_g"] / 1000).round(3)
    cols = ["method", "num_selected", "total_energy_kwh", "total_runtime_min", "total_carbon_kg",
            "assurance_retained_pct", "mandatory_coverage_pct", "energy_saved_pct",
            "runtime_saved_pct", "carbon_saved_pct"]
    lines.append("## Algorithm Comparison Table")
    lines.append(display[cols].round(1).to_string(index=False))

    if display["assurance_retained_pct"].notna().any():
        winner = display.sort_values("assurance_retained_pct", ascending=False).iloc[0]
    else:
        winner = display.sort_values("energy_saved_pct", ascending=False).iloc[0]
    lines += [
        "", "## Headline",
        f"- Top method: {winner['method']}",
        f"- Energy saved: {winner['energy_saved_pct']:.1f}%",
        f"- Runtime saved: {winner['runtime_saved_pct']:.1f}%" if has_runtime_data else "- Runtime saved: N/A",
        f"- Carbon saved: {winner['carbon_saved_pct']:.1f}%",
    ]
    if pd.notna(winner["assurance_retained_pct"]):
        lines.append(f"- Assurance retained: {winner['assurance_retained_pct']:.1f}%")
    if pd.notna(winner["mandatory_coverage_pct"]):
        lines.append(f"- Mandatory coverage: {winner['mandatory_coverage_pct']:.1f}%")

    skipped = [label for label, key in ALGORITHMS if not baseline_availability[key][0]]
    if skipped:
        lines += ["", "## Skipped Methods", *[
            f"- {label}: {baseline_availability[key][1]}" for label, key in ALGORITHMS if not baseline_availability[key][0]
        ]]
    return "\n".join(lines)


baseline_report_text = build_baseline_report_text()

# ============================================================================
# SECTION 3 — Comprehensive Report (single PDF, no Markdown)
#
# Replaces the previous three separate .md/.pdf report pairs with ONE
# comprehensive PDF: Home summary, validation summary, every dataset table,
# every available chart, energy analysis, assurance analysis, test
# prioritization, and baseline comparison — all built fresh from whatever
# CSV is currently active. Nothing here is hardcoded.
# ============================================================================
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
section_title("Reports", tag="PDF")


def build_comprehensive_report_pdf(figs, font_family="Helvetica"):
    """Assembles the single comprehensive PDF report from the current
    dataset's summary text, every FILES table, every rendered chart, and
    the prioritization/baseline report text — in that order.

    font_family controls the heading/table font (user-selectable). The
    monospaced text_section()s (Home/validation/prioritization/baseline
    summaries, which contain fixed-width dataframe.to_string() output)
    always stay on Courier so their columns remain aligned regardless of
    the chosen font.

    Every table/header cell now uses _fit_text() to truncate to the
    ACTUAL measured width of the cell rather than a fixed character
    count — this is what previously caused overlapping text/columns when
    a table had many narrow columns.
    """
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)

    def text_section(report_text):
        pdf.add_page()
        pdf.set_font("Courier", "", 8)
        for line in report_text.splitlines():
            text = _pdf_safe(line) if line.strip() else " "
            pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")

    # Home summary / validation summary / energy analysis / assurance analysis
    text_section(summary_report_text)

    # Datasets & Metric Tables
    pdf.add_page()
    pdf.set_font(font_family, "B", 14)
    pdf.cell(0, 10, "Datasets & Metric Tables", ln=True)
    for fname, (tbl, label, available, reason) in FILES.items():
        pdf.set_font(font_family, "B", 10)
        pdf.ln(3)
        pdf.multi_cell(0, 6, _pdf_safe(f"{label}  ({fname})"))
        if not available:
            pdf.set_font(font_family, "", 9)
            pdf.cell(0, 6, _pdf_safe(f"Unavailable - {reason}."), ln=True)
            continue
        show = tbl.head(25)
        if show.empty:
            pdf.set_font(font_family, "", 9)
            pdf.cell(0, 6, "No rows available for this export.", ln=True)
            continue
        n_cols = max(1, len(show.columns))
        col_width = 277 / n_cols
        cell_pad = 1.5  # mm padding so text never touches the cell border
        row_height = 5
        pdf.set_font(font_family, "B", 7)
        for col in show.columns:
            fitted = _fit_text(pdf, _pdf_safe(str(col)), col_width - cell_pad)
            pdf.cell(col_width, row_height, fitted, border=1)
        pdf.ln(row_height)
        pdf.set_font(font_family, "", 7)
        for _, row in show.iterrows():
            for val in row:
                fitted = _fit_text(pdf, _pdf_safe(str(val)), col_width - cell_pad)
                pdf.cell(col_width, row_height, fitted, border=1)
            pdf.ln(row_height)
        if len(tbl) > len(show):
            pdf.set_font(font_family, "I", 7)
            pdf.cell(0, 5, f"... {len(tbl) - len(show)} more row(s) not shown (see full CSV export).", ln=True)

    # Figures
    if figs:
        for fig_name, png_bytes in figs.items():
            pdf.add_page()
            pdf.set_font(font_family, "B", 12)
            title = fig_name.replace(".png", "").replace("_", " ").title()
            fitted_title = _fit_text(pdf, _pdf_safe(title), 270)
            pdf.cell(0, 10, fitted_title, ln=True)
            pdf.image(io.BytesIO(png_bytes), x=15, y=28, w=260)
    else:
        pdf.add_page()
        pdf.set_font(font_family, "", 10)
        pdf.cell(0, 8, "No chartable columns were found in the uploaded CSV.", ln=True)

    # Test Prioritization
    text_section(prioritization_report_text)

    # Baseline Comparison
    if not baseline_comparison.empty:
        text_section(baseline_report_text)

    return bytes(pdf.output())


st.caption("One PDF covering the Home summary, validation, every dataset table, every available chart, "
           "energy analysis, assurance analysis, prioritization, and baseline comparison — generated fresh "
           "from the currently uploaded CSV.")

if st.button("📄 Generate Comprehensive Report (PDF)", type="primary", use_container_width=True):
    if FIGURE_BUILDERS:
        if st.session_state.get("gat_figures") is None or st.session_state.get("gat_figures_key") != figures_cache_key:
            st.session_state["gat_figures"] = render_all_figures(figures_cache_key)
            st.session_state["gat_figures_key"] = figures_cache_key
        report_figs = st.session_state["gat_figures"]
    else:
        report_figs = {}
    with st.spinner("Assembling the PDF report..."):
        st.session_state["gat_comprehensive_report"] = build_comprehensive_report_pdf(report_figs)
        st.session_state["gat_comprehensive_report_key"] = figures_cache_key

if (st.session_state.get("gat_comprehensive_report") is not None
        and st.session_state.get("gat_comprehensive_report_key") == figures_cache_key):
    st.download_button(
        "⬇ Download comprehensive_report.pdf", st.session_state["gat_comprehensive_report"],
        file_name="comprehensive_report.pdf", mime="application/pdf",
        type="primary", use_container_width=True, key="dl_comprehensive_report",
    )

# ============================================================================
# SECTION 4 — Full Package (.zip)
# ============================================================================
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
section_title("Full Package", tag="one click")
st.caption("Bundles every available dataset (CSV), every available figure (PNG) and the comprehensive PDF "
           "report into a single .zip. Exports that are unavailable for this dataset are simply left out, "
           "with the reason noted in a manifest file. Figures are rendered on demand, so the first click "
           "may take a few seconds.")

if st.button("📦 Build Full Package (.zip)", type="primary", use_container_width=True):
    if FIGURE_BUILDERS:
        if st.session_state.get("gat_figures") is None or st.session_state.get("gat_figures_key") != figures_cache_key:
            st.session_state["gat_figures"] = render_all_figures(figures_cache_key)
            st.session_state["gat_figures_key"] = figures_cache_key
        figs_for_zip = st.session_state["gat_figures"]
    else:
        figs_for_zip = {}

    with st.spinner("Packaging files..."):

        manifest_lines = ["GreenAeroTester export manifest", f"Generated: {datetime.now(timezone.utc).isoformat()}",
                           f"Source file: {st.session_state.get('gat_active_file', 'uploaded CSV')}", ""]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, (tbl, label, available, reason) in FILES.items():
                if available:
                    zf.writestr(f"datasets/{fname}", tbl.to_csv(index=False))
                    manifest_lines.append(f"[included] datasets/{fname} — {label}")
                else:
                    manifest_lines.append(f"[skipped]  {fname} — {label}: {reason}")
            for fig_name, png_bytes in figs_for_zip.items():
                zf.writestr(f"figures/{fig_name}", png_bytes)
                manifest_lines.append(f"[included] figures/{fig_name}")
            zf.writestr(
                "reports/comprehensive_report.pdf",
                build_comprehensive_report_pdf(
                    figs_for_zip, font_family=st.session_state.get("gat_report_font", "Helvetica")
                ),
            )
            manifest_lines.append("[included] reports/comprehensive_report.pdf")
            zf.writestr("MANIFEST.txt", "\n".join(manifest_lines))

    st.download_button(
        "⬇ Download greenaerotester_export.zip", zip_buffer.getvalue(),
        file_name="greenaerotester_export.zip", mime="application/zip",
        type="primary", use_container_width=True, key="dl_full_zip",
    )

st.markdown(
    f"""<div class="gat-footer-note">
    GreenAeroTester export center · driven entirely by the uploaded CSV
    (<code>{st.session_state.get('gat_active_file', '')}</code>, {len(df):,} rows, {len(scoring):,} {unit_label}) ·
    upload a different CSV on the Home page at any time to refresh every export, figure, and report here.
    </div>""",
    unsafe_allow_html=True,
)