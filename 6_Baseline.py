# ============================================================================
# GreenAeroTester — shared UI helpers.
# This block is intentionally IDENTICAL (in spirit) to the one in Home.py /
# Dataset.py / Prioritization.py — see the note there about why each page
# reproduces it rather than importing a shared module.
#
# Phase 9 note (this page): the Baseline Comparison page no longer uses
# load_dataset(), np.random-generated synthetic scoring features, or any
# hardcoded comparison table. It reads the SAME uploaded, validated dataset
# the Home page owns — st.session_state["gat_dataset"] — aggregates it into
# a per-test scoring table (identical approach to the Prioritization page),
# and runs every one of the six algorithms against that real data to build
# the comparison table and charts. If a signal an algorithm needs isn't in
# the CSV, that algorithm is left out of the comparison with a clear note
# instead of being backed by fabricated numbers — everything else keeps
# working. Because this page always reads straight out of session state
# (never caches a dataset of its own), it automatically reflects whatever
# CSV is currently active on Home on its very next render.
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


def sidebar_lock_notice():
    """Identical lock UI to Home.py / Dataset.py / Prioritization.py:
    sidebar/nav stay visible but disabled, with a small explanatory note,
    whenever there's no active validated dataset."""
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
# Comparison data model — built ENTIRELY from the uploaded CSV.
#
# CARBON_INTENSITY_G_PER_KWH mirrors the same documented, fixed grid-average
# constant used on Home.py, and is used the exact same way: only as a
# fallback to estimate carbon from energy when the CSV has no `carbon_gco2`
# column of its own. SAFETY_LEVEL_ASSURANCE_MAP mirrors the same fallback
# used on the Prioritization page to derive an assurance proxy from a real
# `safety_level` column when there's no `assurance_score` column. Neither
# constant is ever used to invent values for rows that lack the underlying
# real column too — in that case the affected metric is reported as
# unavailable rather than faked.
# ---------------------------------------------------------------------------
CARBON_INTENSITY_G_PER_KWH = 475.0
SAFETY_LEVEL_ASSURANCE_MAP = {"DAL-A": 100.0, "DAL-B": 80.0, "DAL-C": 55.0, "DAL-D": 30.0}

ALGORITHMS = [
    ("Default CI", "default_ci"),
    ("Random", "random"),
    ("Runtime Based", "runtime_based"),
    ("Failure History", "failure_history"),
    ("Energy Aware", "energy_aware"),
    ("Knapsack", "knapsack"),
]


def build_scoring(df):
    """Aggregates the uploaded, run-level CSV up to one row per test (a
    'unit') so every algorithm compares apples to apples. Uses `test_id` as
    the unit when the CSV provides one, otherwise falls back to
    `scenario_id` (always present — it's a required column)."""
    unit_col = "test_id" if "test_id" in df.columns else "scenario_id"

    has_status = "status" in df.columns
    has_mandatory = "mandatory" in df.columns
    has_safety = "safety_level" in df.columns
    has_assurance_raw = "assurance_score" in df.columns
    has_carbon_raw = "carbon_gco2" in df.columns

    agg_dict = {
        "runtime_s": "median",
        "software_energy_wh": "median",
    }
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
            grouped["median_energy_wh"] / 1000.0 * CARBON_INTENSITY_G_PER_KWH
        )
    else:
        carbon_source = f"estimated @ {int(CARBON_INTENSITY_G_PER_KWH)} gCO2/kWh"
        grouped["median_carbon_g"] = grouped["median_energy_wh"] / 1000.0 * CARBON_INTENSITY_G_PER_KWH

    grouped["utility_score"] = np.where(
        (grouped["median_energy_wh"] > 0) & grouped["assurance_score"].notna(),
        grouped["assurance_score"] / grouped["median_energy_wh"],
        np.nan,
    )

    meta = dict(
        unit_col=unit_col, has_status=has_status, has_mandatory=has_mandatory,
        has_safety=has_safety, has_assurance_raw=has_assurance_raw,
        assurance_source=assurance_source, assurance_available=bool(assurance_available),
        carbon_source=carbon_source,
    )
    return grouped, meta


def knapsack_01(optional, budget_remaining, n_bins=1500):
    """0/1 knapsack maximizing total assurance score within an energy
    budget, solved on a discretized weight grid (DP)."""
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
    """Selects units under an energy budget using the requested algorithm.
    Mandatory units are always included first and subtracted from the
    budget before optional units are considered."""
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
        num_selected=int(len(selected)),
        num_total=int(len(scoring)),
        total_energy_wh=float(sel_energy),
        total_runtime_s=float(sel_runtime),
        total_carbon_g=float(sel_carbon),
        energy_saved_pct=float(100 * (full_energy - sel_energy) / full_energy) if full_energy else 0.0,
        runtime_saved_pct=float(100 * (full_runtime - sel_runtime) / full_runtime) if full_runtime else 0.0,
        carbon_saved_pct=float(100 * (full_carbon - sel_carbon) / full_carbon) if full_carbon else 0.0,
    )

    if meta["assurance_available"]:
        full_assurance = scoring["assurance_score"].fillna(0).sum()
        sel_assurance = selected["assurance_score"].fillna(0).sum()
        result["assurance_retained_pct"] = (
            float(100 * sel_assurance / full_assurance) if full_assurance else 0.0
        )
    else:
        result["assurance_retained_pct"] = None

    if meta["has_mandatory"]:
        mand_total = int(scoring["mandatory"].sum())
        mand_selected = int(selected["mandatory"].sum())
        result["mandatory_coverage_pct"] = (100 * mand_selected / mand_total) if mand_total else 100.0
    else:
        result["mandatory_coverage_pct"] = None

    return result


# ============================================================================
# PAGE: Baseline Comparison
#
# Locked state mirrors Home.py / Dataset.py / Prioritization.py exactly: if
# there is no active, validated dataset in st.session_state["gat_dataset"],
# this page shows the same lock notice / prompt-to-upload message and
# stops — it never falls back to load_dataset(), random values, or any
# hardcoded comparison table.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester — Baseline", page_icon="📊",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_brand()

stage = st.session_state.get("gat_stage")
dataset = st.session_state.get("gat_dataset")

if stage != "unlocked" or dataset is None:
    sidebar_lock_notice()
    page_header(
        "PHASE 2 · BASELINE COMPARISON",
        "Baseline Comparison",
        "How each prioritization method stacks up against the others",
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
sidebar_status_footer(df, filename=st.session_state.get("gat_active_file"))

scoring, meta = build_scoring(df)
unit_label = "tests" if meta["unit_col"] == "test_id" else "scenarios"
has_runtime_data = df["runtime_s"].notna().any()

page_header(
    "PHASE 2 · BASELINE COMPARISON",
    "Baseline Comparison",
    "How each prioritization method stacks up against CI, random, runtime and failure-history baselines",
    pill_text=f"{len(ALGORITHMS)} methods · {len(scoring):,} {unit_label} · source: uploaded CSV",
)

if meta["assurance_source"]:
    st.caption(f"Assurance scoring derived from: {meta['assurance_source']}. Carbon: {meta['carbon_source']}.")
else:
    st.caption(
        "No `assurance_score` or `safety_level` column found in the uploaded CSV — Assurance Retained, "
        "Energy Aware, and Knapsack are unavailable until one is provided. Carbon: "
        f"{meta['carbon_source']}."
    )

# ---- Availability of each algorithm, based on what the CSV actually has ---
availability = {
    "default_ci": (True, None),
    "random": (True, None),
    "runtime_based": (True, None),
    "failure_history": (
        meta["has_status"],
        "requires a `status` column in the uploaded dataset",
    ),
    "energy_aware": (
        meta["assurance_available"],
        "requires an `assurance_score` or `safety_level` column in the uploaded dataset",
    ),
    "knapsack": (
        meta["assurance_available"],
        "requires an `assurance_score` or `safety_level` column in the uploaded dataset",
    ),
}
unavailable = [(label, msg) for label, key in ALGORITHMS for ok, msg in [availability[key]] if not ok]

section_title("Reference Budget")
budget_pct = st.slider(
    "Energy budget used for this comparison (% of full-suite median energy)",
    10, 100, 60, step=5, key="baseline_budget",
)

# ---- Run every available algorithm at the reference budget -----------------
rows = []
for label, key in ALGORITHMS:
    ok, _ = availability[key]
    if not ok:
        continue
    sel = select_units(scoring, key, budget_pct / 100.0)
    s = summarize_selection(scoring, sel, meta)
    s["method"] = label
    rows.append(s)

if not rows:
    st.warning("No algorithms could be compared for this dataset — check the messages above for what's missing.")
    st.stop()

comparison = pd.DataFrame(rows)

if unavailable:
    skipped_txt = "; ".join(f"**{label}** ({msg})" for label, msg in unavailable)
    st.info(f"Skipped from this comparison: {skipped_txt}.")

# ---- Winner ---------------------------------------------------------------
if comparison["assurance_retained_pct"].notna().any():
    winner = comparison.sort_values("assurance_retained_pct", ascending=False).iloc[0]
    winner_note = f"{winner['method']} retains the most assurance at this budget"
else:
    winner = comparison.sort_values("energy_saved_pct", ascending=False).iloc[0]
    winner_note = f"{winner['method']} saves the most energy at this budget"

section_title("Headline Comparison")
c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Methods Compared", fmt_num(len(comparison)), f"of {len(ALGORITHMS)} total", accent=COLORS["accent"])
with c2:
    metric_card("Top Method", winner["method"], winner_note, accent=COLORS["accent2"])
with c3:
    metric_card("Energy Saved (Top)", f"{winner['energy_saved_pct']:.1f}%", "vs. running the full suite",
                accent=COLORS["accent"])
with c4:
    if pd.notna(winner["assurance_retained_pct"]):
        metric_card("Assurance Retained (Top)", f"{winner['assurance_retained_pct']:.1f}%", accent=COLORS["amber"])
    else:
        metric_card("Assurance Retained (Top)", "N/A", "no assurance data in dataset", accent=COLORS["text_faint"])

# ---- Comparison charts -----------------------------------------------------
section_title("Assurance Retained vs Energy Saved")
g1, g2 = st.columns(2)
with g1:
    if comparison["assurance_retained_pct"].notna().any():
        fig = go.Figure(go.Bar(
            x=comparison["method"], y=comparison["assurance_retained_pct"],
            marker=dict(color=[CHART_COLORS["line"] if m == winner["method"] else CHART_COLORS["bar"]
                                for m in comparison["method"]]),
        ))
        fig.update_layout(title="Assurance Retained (%)", xaxis_tickangle=-25)
        st.plotly_chart(apply_plotly_theme(fig, 360), use_container_width=True, config={"displaylogo": False})
    else:
        st.info(
            "No `assurance_score` or `safety_level` column in the uploaded CSV — assurance comparison "
            "isn't available for this dataset."
        )
with g2:
    fig = go.Figure(go.Bar(
        x=comparison["method"], y=comparison["energy_saved_pct"],
        marker=dict(color=CHART_COLORS["line"]),
    ))
    fig.update_layout(title="Energy Saved vs Full Suite (%)", xaxis_tickangle=-25)
    st.plotly_chart(apply_plotly_theme(fig, 360), use_container_width=True, config={"displaylogo": False})

g3, g4 = st.columns(2)
with g3:
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Energy (kWh)", x=comparison["method"],
                          y=comparison["total_energy_wh"] / 1000.0, marker_color=CHART_COLORS["bar"]))
    fig.add_trace(go.Bar(name="Carbon (kg CO₂e)", x=comparison["method"],
                          y=comparison["total_carbon_g"] / 1000.0, marker_color=CHART_COLORS["line"]))
    fig.update_layout(title="Total Energy vs Carbon by Method", barmode="group", xaxis_tickangle=-25)
    st.plotly_chart(apply_plotly_theme(fig, 360), use_container_width=True, config={"displaylogo": False})
with g4:
    if has_runtime_data:
        fig = go.Figure(go.Bar(
            x=comparison["method"], y=comparison["runtime_saved_pct"], marker=dict(color=CHART_COLORS["bar"]),
        ))
        fig.update_layout(title="Runtime Saved vs Full Suite (%)", xaxis_tickangle=-25)
        st.plotly_chart(apply_plotly_theme(fig, 360), use_container_width=True, config={"displaylogo": False})
    else:
        st.info("No usable runtime data in the uploaded CSV — runtime comparison isn't available.")

# ---- Table -------------------------------------------------------------------
section_title("Full Comparison Table")
table = comparison.copy()
table["total_energy_kwh"] = (table["total_energy_wh"] / 1000.0).round(3)
table["total_runtime_min"] = (table["total_runtime_s"] / 60).round(1)
table["total_carbon_kg"] = (table["total_carbon_g"] / 1000.0).round(3)

display_cols = ["method", "num_selected", "total_energy_kwh"]
col_names = ["Method", "Tests Selected", "Energy (kWh)"]
if has_runtime_data:
    display_cols.append("total_runtime_min"); col_names.append("Runtime (min)")
display_cols.append("total_carbon_kg"); col_names.append("Carbon (kg CO₂e)")
if comparison["assurance_retained_pct"].notna().any():
    display_cols.append("assurance_retained_pct"); col_names.append("Assurance Retained (%)")
if meta["has_mandatory"]:
    display_cols.append("mandatory_coverage_pct"); col_names.append("Mandatory Coverage (%)")
display_cols.append("energy_saved_pct"); col_names.append("Energy Saved (%)")
if has_runtime_data:
    display_cols.append("runtime_saved_pct"); col_names.append("Runtime Saved (%)")
display_cols.append("carbon_saved_pct"); col_names.append("Carbon Saved (%)")

table_display = table[display_cols].copy()
table_display.columns = col_names
st.dataframe(table_display.round(1), hide_index=True, use_container_width=True, height=270)

st.download_button(
    "⬇ Download baseline_comparison.csv", table_display.to_csv(index=False).encode(),
    file_name="baseline_comparison.csv", mime="text/csv",
)

st.markdown(
    f"""<div class="gat-footer-note">
    GreenAeroTester baseline comparison · driven entirely by the uploaded CSV
    (<code>{st.session_state.get('gat_active_file', '')}</code>, {len(df):,} rows, {len(scoring):,} {unit_label}) ·
    mandatory {unit_label} are subtracted from the budget first and always included in every method ·
    upload a different CSV on the Home page at any time to refresh every comparison, KPI, and chart here.
    </div>""",
    unsafe_allow_html=True,
)