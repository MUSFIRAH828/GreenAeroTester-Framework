# ============================================================================
# GreenAeroTester — shared UI helpers.
# This block is intentionally IDENTICAL (in spirit) to the one in Home.py /
# Dataset.py — see the note there about why each page reproduces it rather
# than importing a shared module.
#
# Phase 9 note (this page): the Prioritization page no longer uses
# load_dataset(), np.random-generated synthetic scoring features, or any
# hardcoded ranking/statistics. It reads the SAME uploaded, validated
# dataset the Home page owns — st.session_state["gat_dataset"] — and builds
# every ranking, KPI, and export directly from whatever columns are present
# in that CSV. If a required signal (e.g. a status column, an
# assurance_score/safety_level column) isn't present, the affected
# algorithm is disabled with a clear message instead of being backed by
# fabricated numbers; everything else on the page keeps working normally.
# Because this page always reads straight out of session state (never
# caches a dataset of its own), it automatically reflects whatever CSV is
# currently active on Home — including after a Change/re-upload — on its
# very next render.
# ============================================================================

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import streamlit.components.v1 as components
from utils.theme import apply_theme, get_theme_colors, get_chart_colors, get_chart_type, init_session_defaults
from utils.charts import chart_budget_curve

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
    """Identical lock UI to Home.py / Dataset.py: sidebar/nav stay visible
    but disabled, with a small explanatory note, whenever there's no active
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
# Prioritization data model — built ENTIRELY from the uploaded CSV.
#
# SAFETY_LEVEL_ASSURANCE_MAP is a documented, fixed mapping (same spirit as
# the CARBON_INTENSITY_G_PER_KWH constant on Home.py) used ONLY as a
# fallback to derive an assurance proxy from a real `safety_level` column
# when the CSV has no `assurance_score` column of its own. It is never used
# to invent scores for rows that don't have safety_level data either — in
# that case assurance is simply reported as unavailable and the algorithms
# that depend on it (Energy Aware, Knapsack) are disabled with an explicit
# message rather than producing fake rankings.
# ---------------------------------------------------------------------------
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
    'unit') so prioritization operates on tests, not individual runs.
    Uses `test_id` as the unit when the CSV provides one, otherwise falls
    back to `scenario_id` (always present — it's a required column)."""
    unit_col = "test_id" if "test_id" in df.columns else "scenario_id"

    has_status = "status" in df.columns
    has_mandatory = "mandatory" in df.columns
    has_safety = "safety_level" in df.columns
    has_assurance_raw = "assurance_score" in df.columns
    has_flight_phase = "flight_phase" in df.columns

    agg_dict = {
        "runtime_s": "median",
        "software_energy_wh": "median",
    }
    if unit_col != "scenario_id":
        agg_dict["scenario_id"] = "first"
    if has_flight_phase:
        agg_dict["flight_phase"] = lambda s: (s.dropna().mode().iat[0] if not s.dropna().mode().empty else np.nan)
    if has_safety:
        agg_dict["safety_level"] = lambda s: (s.dropna().mode().iat[0] if not s.dropna().mode().empty else np.nan)
    if has_assurance_raw:
        agg_dict["assurance_score"] = "median"

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

    grouped["utility_score"] = np.where(
        (grouped["median_energy_wh"] > 0) & grouped["assurance_score"].notna(),
        grouped["assurance_score"] / grouped["median_energy_wh"],
        np.nan,
    )

    meta = dict(
        unit_col=unit_col, has_status=has_status, has_mandatory=has_mandatory,
        has_safety=has_safety, has_assurance_raw=has_assurance_raw,
        has_flight_phase=has_flight_phase, assurance_source=assurance_source,
        assurance_available=bool(assurance_available),
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


def select_units(scoring, algo_key, energy_budget_frac, runtime_budget_frac=None, seed=7):
    """Selects units under an energy budget (and optionally a runtime
    budget) using the requested algorithm. Mandatory units are always
    included first and subtracted from the budget before optional units
    are considered."""
    total_energy = scoring["median_energy_wh"].sum()
    total_runtime = scoring["median_runtime_s"].sum()
    budget = total_energy * max(0.0, min(1.0, energy_budget_frac))
    runtime_budget = (total_runtime * max(0.0, min(1.0, runtime_budget_frac))
                       if runtime_budget_frac is not None else None)

    mandatory_df = scoring[scoring["mandatory"] == True]  # noqa: E712
    optional_df = scoring[scoring["mandatory"] != True].copy()  # noqa: E712

    budget_remaining = budget - mandatory_df["median_energy_wh"].sum()
    runtime_remaining = (runtime_budget - mandatory_df["median_runtime_s"].sum()
                          if runtime_budget is not None else None)

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
        if runtime_remaining is not None and not chosen.empty:
            chosen = chosen.sort_values("utility_score", ascending=False, na_position="last")
            cum_rt = chosen["median_runtime_s"].cumsum()
            chosen = chosen[cum_rt <= runtime_remaining]
        return pd.concat([mandatory_df, chosen])
    else:
        raise ValueError(f"Unknown algorithm: {algo_key}")

    if budget_remaining <= 0:
        chosen = optional_df.iloc[0:0]
    else:
        cum_energy = optional_df["median_energy_wh"].cumsum()
        keep_mask = cum_energy <= budget_remaining
        if runtime_remaining is not None:
            cum_runtime = optional_df["median_runtime_s"].cumsum()
            keep_mask &= cum_runtime <= runtime_remaining
        chosen = optional_df[keep_mask]
    return pd.concat([mandatory_df, chosen])


def summarize_selection(scoring, selected, meta):
    full_energy = scoring["median_energy_wh"].sum()
    full_runtime = scoring["median_runtime_s"].sum()
    sel_energy = selected["median_energy_wh"].sum()
    sel_runtime = selected["median_runtime_s"].sum()

    result = dict(
        num_selected=int(len(selected)),
        num_total=int(len(scoring)),
        total_energy_wh=float(sel_energy),
        total_runtime_s=float(sel_runtime),
        energy_saved_pct=float(100 * (full_energy - sel_energy) / full_energy) if full_energy else 0.0,
        runtime_saved_pct=float(100 * (full_runtime - sel_runtime) / full_runtime) if full_runtime else 0.0,
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
        result["mandatory_total"] = mand_total
        result["mandatory_selected"] = mand_selected
        result["mandatory_coverage_pct"] = (100 * mand_selected / mand_total) if mand_total else 100.0
    else:
        result["mandatory_total"] = None
        result["mandatory_selected"] = None
        result["mandatory_coverage_pct"] = None

    return result


# ============================================================================
# PAGE: Prioritization Engine
#
# Locked state mirrors Home.py / Dataset.py exactly: if there is no active,
# validated dataset in st.session_state["gat_dataset"], this page shows the
# same lock notice / prompt-to-upload message and stops — it never falls
# back to load_dataset(), random values, or any hardcoded ranking.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester — Prioritization", page_icon="🎯",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_brand()

stage = st.session_state.get("gat_stage")
dataset = st.session_state.get("gat_dataset")

if stage != "unlocked" or dataset is None:
    sidebar_lock_notice()
    page_header(
        "PHASE 2 · PRIORITIZATION",
        "Prioritization Engine",
        "Rank and select tests under an energy budget — mandatory tests are always included",
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

page_header(
    "PHASE 2 · PRIORITIZATION",
    "Prioritization Engine",
    "Rank and select tests under an energy budget — mandatory tests are always included",
    pill_text=f"{len(scoring):,} {unit_label} · source: uploaded CSV",
)

if meta["assurance_source"]:
    st.caption(f"Assurance scoring derived from: {meta['assurance_source']}.")
else:
    st.caption(
        "No `assurance_score` or `safety_level` column found in the uploaded CSV — "
        "Energy Aware and Knapsack are unavailable until one is provided."
    )

# ---- Availability of each algorithm, based on what the CSV actually has ---
availability = {
    "default_ci": (True, None),
    "random": (True, None),
    "runtime_based": (True, None),
    "failure_history": (
        meta["has_status"],
        "Failure History requires a `status` column in the uploaded dataset.",
    ),
    "energy_aware": (
        meta["assurance_available"],
        "Energy Aware requires an `assurance_score` or `safety_level` column in the uploaded dataset.",
    ),
    "knapsack": (
        meta["assurance_available"],
        "Knapsack requires an `assurance_score` or `safety_level` column in the uploaded dataset.",
    ),
}

has_runtime_data = df["runtime_s"].notna().any()

# ---- Configuration -----------------------------------------------------
section_title("Configuration")
cfg1, cfg2, cfg3, cfg4 = st.columns([1.3, 1.2, 1.2, 1])

with cfg1:
    algo_labels = [
        (f"{label} — unavailable" if not availability[key][0] else label)
        for label, key in ALGORITHMS
    ]
    algo_choice_label = st.selectbox("Prioritization algorithm", algo_labels, index=0)
    algo_key = dict(zip(algo_labels, [key for _, key in ALGORITHMS]))[algo_choice_label]
    algo_display = {key: label for label, key in ALGORITHMS}
    algo_ok, algo_msg = availability[algo_key]

with cfg2:
    energy_budget_pct = st.slider("Energy budget (% of full-suite median energy)", 10, 100, 60, step=5)

with cfg3:
    if has_runtime_data:
        use_runtime_budget = st.checkbox("Also apply a runtime budget", value=False)
        runtime_budget_pct = st.slider(
            "Runtime budget (% of full-suite median runtime)", 10, 100, 100, step=5,
            disabled=not use_runtime_budget,
        )
    else:
        use_runtime_budget = False
        runtime_budget_pct = 100
        st.caption("No usable runtime data in the uploaded dataset — runtime budget is unavailable.")

with cfg4:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    generate_clicked = st.button("▶ Generate Prioritization", type="primary", use_container_width=True)

if algo_key == "random":
    st.caption("Random order is reshuffled with a fixed seed per run for reproducible comparison.")

# ---- Run the selected algorithm --------------------------------------------
if not algo_ok:
    st.warning(f"**{algo_display[algo_key]}** cannot generate results for this dataset: {algo_msg}")
    st.info("Choose a different algorithm above, or upload a CSV that includes the required column.")
    st.stop()

runtime_frac = (runtime_budget_pct / 100.0) if use_runtime_budget else None
selected = select_units(scoring, algo_key, energy_budget_pct / 100.0, runtime_budget_frac=runtime_frac)
summary = summarize_selection(scoring, selected, meta)

# ---- Selection Summary ------------------------------------------------------
section_title("Selection Summary")
c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Tests Selected", fmt_num(summary["num_selected"]), f"of {summary['num_total']} total",
                accent=COLORS["accent"])
with c2:
    metric_card("Energy Used", f"{summary['total_energy_wh']/1000:.3f} kWh",
                f"{summary['energy_saved_pct']:.1f}% saved vs. full suite", accent=COLORS["accent2"])
with c3:
    if has_runtime_data:
        metric_card("Runtime Used", f"{summary['total_runtime_s']/60:.1f} min",
                    f"{summary['runtime_saved_pct']:.1f}% saved vs. full suite", accent=COLORS["amber"])
    else:
        metric_card("Runtime Used", "N/A", "no runtime data", accent=COLORS["text_faint"])
with c4:
    if summary["assurance_retained_pct"] is not None:
        metric_card("Assurance Retained", f"{summary['assurance_retained_pct']:.1f}%", accent=COLORS["accent"])
    else:
        metric_card("Assurance Retained", "N/A", "no assurance data in dataset", accent=COLORS["text_faint"])

c5, c6 = st.columns(2)
with c5:
    if meta["has_mandatory"]:
        metric_card(
            "Mandatory Tests Included",
            f"{summary['mandatory_selected']} / {summary['mandatory_total']}",
            f"{summary['mandatory_coverage_pct']:.0f}% coverage", accent=COLORS["amber"],
        )
    else:
        metric_card("Mandatory Tests Included", "N/A", "no `mandatory` column in dataset",
                    accent=COLORS["text_faint"])
with c6:
    metric_card("Algorithm", algo_display[algo_key],
                f"energy budget {energy_budget_pct}%" + (f" · runtime budget {runtime_budget_pct}%" if use_runtime_budget else ""),
                accent=COLORS["accent2"])

# ---- Ranked list -------------------------------------------------------
section_title("Ranked Test List")

ranked = selected.copy()
if algo_key == "energy_aware":
    ranked = ranked.sort_values("utility_score", ascending=False, na_position="last")
elif algo_key == "knapsack":
    ranked = ranked.sort_values("assurance_score", ascending=False, na_position="last")
elif algo_key == "runtime_based":
    ranked = ranked.sort_values("median_runtime_s")
elif algo_key == "failure_history":
    ranked = ranked.sort_values("failure_rate", ascending=False)
else:
    ranked = ranked.sort_values(["mandatory", "unit_id"], ascending=[False, True])

ranked = ranked.reset_index(drop=True)
ranked.insert(0, "rank", range(1, len(ranked) + 1))

display_df = ranked.rename(columns={"unit_id": meta["unit_col"]}).copy()
display_df["mandatory"] = display_df["mandatory"].map({True: "✅ Mandatory", False: "Optional"})

display_cols = ["rank", meta["unit_col"]]
if meta["unit_col"] != "scenario_id":
    display_cols.append("scenario_id")
if meta["has_flight_phase"]:
    display_cols.append("flight_phase")
display_cols.append("mandatory")
if meta["has_status"]:
    display_df["failure_rate_pct"] = (display_df["failure_rate"] * 100).round(1)
    display_cols.append("failure_rate_pct")
display_cols += ["median_runtime_s", "median_energy_wh"]
if meta["assurance_available"]:
    display_cols += ["assurance_score", "utility_score"]

st.dataframe(display_df[display_cols], hide_index=True, use_container_width=True, height=420)

st.caption(f"Showing {len(ranked):,} selected {unit_label} (mandatory {unit_label} are always included first).")

# ---- CSV export --------------------------------------------------------
export_cols = ["rank", "unit_id"]
if meta["unit_col"] != "scenario_id":
    export_cols.append("scenario_id")
export_cols += ["mandatory", "median_runtime_s", "median_energy_wh"]
if meta["assurance_available"]:
    export_cols += ["assurance_score", "utility_score"]
export_df = ranked[export_cols].rename(columns={"unit_id": meta["unit_col"]}).copy()
export_df["method"] = algo_display[algo_key]
export_df["energy_budget_fraction"] = energy_budget_pct / 100.0
export_df["runtime_budget_fraction"] = runtime_frac if runtime_frac is not None else ""

st.download_button(
    "⬇ Export prioritization_decisions.csv", export_df.to_csv(index=False).encode(),
    file_name="prioritization_decisions.csv", mime="text/csv", type="primary",
)

# ---- Budget curve --------------------------------------------------------
section_title("Assurance Retained vs Energy Budget", tag=algo_display[algo_key])
if meta["assurance_available"]:
    budgets = list(range(10, 101, 10))
    curve_vals = []
    for b in budgets:
        sel_b = select_units(scoring, algo_key, b / 100.0)
        curve_vals.append(summarize_selection(scoring, sel_b, meta)["assurance_retained_pct"])
    curve = chart_budget_curve(
        budgets, curve_vals, chosen_budget=energy_budget_pct,
        title=f"{algo_display[algo_key]}: Assurance Retained as Budget Increases",
    )
    st.plotly_chart(curve, use_container_width=True, config={"displaylogo": False})
else:
    st.info(
        "This chart requires assurance data (`assurance_score` or `safety_level`) in the uploaded CSV, "
        "which isn't available for this dataset."
    )

st.markdown(
    f"""<div class="gat-footer-note">
    GreenAeroTester prioritization · driven entirely by the uploaded CSV
    (<code>{st.session_state.get('gat_active_file', '')}</code>, {len(df):,} rows, {len(scoring):,} {unit_label}) ·
    mandatory {unit_label} are subtracted from the budget first and always included ·
    upload a different CSV on the Home page at any time to refresh every ranking, KPI, and export here.
    </div>""",
    unsafe_allow_html=True,
)