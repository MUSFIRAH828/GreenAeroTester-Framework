# ============================================================================
# GreenAeroTester — shared UI helpers.
# This block is intentionally IDENTICAL (in spirit) to the one in Home.py /
# Dataset.py / Energy.py — see the note in Home.py for why each page
# reproduces it rather than importing a shared module. This copy is trimmed
# to only what the Assurance page needs.
#
# Phase 9 note (this page): the Assurance page no longer generates or reads
# any synthetic/dummy dataset (load_dataset(), the 500-scenario random
# model, the synthetic safety/coverage/fault/novelty/flakiness/
# certification generators, etc). It reads the SAME uploaded, validated
# dataset the Home page owns — st.session_state["gat_dataset"] — so every
# KPI, chart, and table on this page is derived from the actual uploaded
# CSV, never from hardcoded arrays or randomly generated values.
#
# Whenever a new CSV is uploaded on Home (Upload/Change), this page picks it
# up automatically on its next render, because it always reads straight out
# of session state rather than caching anything locally.
#
# If no dataset is active (nothing uploaded yet, or the last upload failed
# validation), this page shows the same locked state as Home/Dataset/Energy
# instead of any placeholder numbers.
#
# Column contract: `assurance_score` and `safety_level` are canonicalized by
# Home.py's load_and_validate_csv() when present (OPTIONAL_COLUMN_ALIASES).
# The finer-grained scoring components (requirement coverage, fault
# history, recent-change relevance, novelty, flakiness, certification
# relevance, and a raw safety-criticality value) are NOT canonicalized by
# the shared validator, so this page does its own flexible, alias-based
# column detection for them (see ASSURANCE_COLUMN_ALIASES below) and
# gracefully hides/labels any visualization whose required column isn't
# present, instead of crashing or fabricating data.
# ============================================================================

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from utils.theme import apply_theme, get_theme_colors, get_chart_colors, get_chart_type, init_session_defaults
from utils.charts import chart_weights_radar, chart_generic_histogram, chart_two_group_scatter, \
    chart_box_by_group, chart_grouped_counts
import streamlit.components.v1 as components

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
    """Identical lock UI to Home.py/Dataset.py/Energy.py: sidebar/nav stay
    visible but disabled, with a small explanatory note, whenever there's
    no active validated dataset."""
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


# ---------------------------------------------------------------------------
# Scoring methodology reference (SRS §10): a documented, fixed weighting
# scheme — NOT dataset content. This is shown purely as a reference for how
# an assurance_score *would* typically be composed; it is never used to
# fabricate or recompute an assurance_score for a row. If the uploaded CSV
# doesn't already contain assurance_score, this page shows the "not found"
# message instead of inventing one from these weights.
# ---------------------------------------------------------------------------
ASSURANCE_WEIGHTS = {
    "safety": 0.30,
    "coverage": 0.20,
    "fault": 0.15,
    "recent": 0.10,
    "novelty": 0.10,
    "flaky": 0.05,
    "cert": 0.10,
}
ASSURANCE_WEIGHT_LABELS = {
    "safety": "Safety criticality",
    "coverage": "Requirement coverage",
    "fault": "Fault history",
    "recent": "Recent change relevance",
    "novelty": "Novelty",
    "flaky": "Flakiness (inverted)",
    "cert": "Certification relevance",
}
ASSURANCE_COMPONENT_INVERTED = {"flaky"}  # flakiness is weighted as (100 - flakiness)

SAFETY_LEVELS_ORDER = ["DAL-A", "DAL-B", "DAL-C", "DAL-D"]
SAFETY_LEVEL_TO_CRITICALITY = {"DAL-A": 100, "DAL-B": 80, "DAL-C": 55, "DAL-D": 30}


# ---------------------------------------------------------------------------
# Flexible column lookup, same pattern as Dataset.py's weather/fault
# detection and Energy.py's CPU/hardware detection — for the scoring
# component columns the shared upload validator on Home.py does NOT
# canonicalize. `assurance_score` and `safety_level` ARE canonicalized by
# Home's load_and_validate_csv, so they're addressed directly by name.
# ---------------------------------------------------------------------------
def _norm(s):
    return str(s).strip().lower().replace(" ", "_")


def _find_column(columns, aliases):
    normalized = {_norm(c): c for c in columns}
    for a in aliases:
        if _norm(a) in normalized:
            return normalized[_norm(a)]
    return None


ASSURANCE_COMPONENT_SPECS = {
    "safety": dict(
        aliases=["safety_criticality", "safety_score", "safety_criticality_score"],
        label="Safety Criticality (0–100)",
    ),
    "coverage": dict(
        aliases=["requirement_coverage", "req_coverage", "coverage", "requirement_coverage_pct"],
        label="Requirement Coverage (%)",
    ),
    "fault": dict(
        aliases=["fault_history", "fault_hist", "failure_history"],
        label="Fault History (0–100)",
    ),
    "recent": dict(
        aliases=["recent_change_relevance", "recent_change", "change_relevance"],
        label="Recent Change Relevance (0–100)",
    ),
    "novelty": dict(
        aliases=["novelty", "novelty_score"],
        label="Novelty (0–100)",
    ),
    "flaky": dict(
        aliases=["flakiness", "flaky", "flakiness_score"],
        label="Flakiness (0–100, lower is better)",
    ),
    "cert": dict(
        aliases=["certification_relevance", "certification", "cert_relevance"],
        label="Certification Relevance (0–100)",
    ),
}


# ============================================================================
# PAGE: Assurance Scoring
# Source of truth: st.session_state["gat_dataset"] (the same validated CSV
# Home.py stores). No load_dataset(), no random values, no hardcoded arrays.
# assurance_score is read AS-IS from the uploaded CSV when present; it is
# never computed/fabricated by this page.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester — Assurance", page_icon="🛡️",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_brand()

stage = st.session_state.get("gat_stage")
dataset = st.session_state.get("gat_dataset")

# ---- Locked state: no active validated dataset. Mirrors Home.py/Dataset.py/
# Energy.py exactly — nothing below renders. -------------------------------
if stage != "unlocked" or dataset is None:
    sidebar_lock_notice()
    page_header(
        "PHASE 2 · ASSURANCE",
        "Assurance Scoring",
        "Assurance score and its contributing factors — generated entirely from your uploaded dataset",
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

has_test_id = "test_id" in df.columns
has_mandatory = "mandatory" in df.columns
has_safety_level = "safety_level" in df.columns
has_assurance_score = "assurance_score" in df.columns

group_col = "test_id" if has_test_id else "scenario_id"
group_label = "Test" if has_test_id else "Scenario"

# ---- Flexible detection of the scoring-component columns -------------------
component_cols = {}
for key, spec in ASSURANCE_COMPONENT_SPECS.items():
    found = _find_column(df.columns, spec["aliases"])
    if found:
        component_cols[key] = found

# Safety criticality can also be derived from safety_level (DAL) when no raw
# safety-criticality column exists — a deterministic, documented mapping of
# real uploaded data, not a fabricated value.
safety_derived_from_dal = False
if "safety" not in component_cols and has_safety_level:
    df["_safety_criticality_derived"] = df["safety_level"].map(SAFETY_LEVEL_TO_CRITICALITY)
    if df["_safety_criticality_derived"].notna().any():
        component_cols["safety"] = "_safety_criticality_derived"
        safety_derived_from_dal = True

page_header(
    "PHASE 2 · ASSURANCE",
    "Assurance Scoring",
    "Assurance score and its contributing factors — generated entirely from your uploaded dataset",
    pill_text=f"{df[group_col].nunique():,} {group_label.lower()}s · {len(df):,} rows",
)

# ---------------------------------------------------------------------------
# Per-group aggregation (dedupe to one row per test/scenario, since scoring
# components are typically constant per test but the uploaded CSV is at
# run-level granularity). Uses mean so any row-level noise within the same
# group is smoothed rather than double-counted.
# ---------------------------------------------------------------------------
agg_map = {}
if has_assurance_score:
    agg_map["assurance_score"] = ("assurance_score", "mean")
for key, col in component_cols.items():
    agg_map[f"_comp_{key}"] = (col, "mean")
agg_map["median_energy_wh"] = ("software_energy_wh", "median")
if has_mandatory:
    agg_map["mandatory"] = ("mandatory", "max")
if has_safety_level:
    agg_map["safety_level"] = ("safety_level", "first")

scoring = df.groupby(group_col).agg(**agg_map).reset_index()

# ============================================================================
# SECTION — Assurance Score (top-level KPIs + distribution)
# ============================================================================
section_title("Assurance Score", tag="assurance_score" if has_assurance_score else "unavailable")

if not has_assurance_score:
    st.info("Assurance score not found. Please upload assurance_features.csv or run backend scoring.")
else:
    valid_scores = scoring["assurance_score"].dropna()
    if valid_scores.empty:
        st.info("Assurance score not found. Please upload assurance_features.csv or run backend scoring.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Mean Assurance Score", f"{valid_scores.mean():.1f}", accent=COLORS["accent"])
        with c2:
            metric_card("Median Score", f"{valid_scores.median():.1f}", accent=COLORS["accent2"])
        with c3:
            metric_card("Highest Score", f"{valid_scores.max():.1f}", accent=COLORS["amber"])
        with c4:
            metric_card("Lowest Score", f"{valid_scores.min():.1f}", accent=COLORS["danger"])

        st.caption(f"Computed from {len(valid_scores):,} {group_label.lower()}(s) in the uploaded CSV "
                   f"(one value per {group_col}, averaged across its runs).")

        g1, g2 = st.columns(2)
        with g1:
            hist = chart_generic_histogram(valid_scores, "Assurance Score Distribution",
                                            xaxis_title="Score", yaxis_title=f"# {group_label}s")
            st.plotly_chart(hist, use_container_width=True, config={"displaylogo": False})
        with g2:
            if has_safety_level:
                box_src = scoring.dropna(subset=["assurance_score", "safety_level"])
                present_levels = [lvl for lvl in SAFETY_LEVELS_ORDER if lvl in box_src["safety_level"].unique()]
                present_levels += sorted(set(box_src["safety_level"].unique()) - set(present_levels))
                if not box_src.empty and present_levels:
                    box = chart_box_by_group(box_src, "safety_level", "assurance_score", present_levels,
                                              "Assurance Score by Safety Level (DAL)")
                    st.plotly_chart(box, use_container_width=True, config={"displaylogo": False})
                else:
                    st.info("Not enough data to break down assurance score by safety level.")
            else:
                st.info("The uploaded CSV doesn't include a `safety_level` column — assurance score by "
                        "safety level isn't available for this dataset.")

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ============================================================================
# SECTION — Scoring methodology reference (config only, not dataset content)
# ============================================================================
section_title("Scoring Methodology Reference", tag="documented weighting scheme")
st.caption("Shown for reference only — these weights describe how an assurance score is typically composed. "
           "They are never used to compute or replace the `assurance_score` values in your uploaded CSV.")

weights_display = pd.DataFrame([
    {"component": ASSURANCE_WEIGHT_LABELS[k], "weight": v} for k, v in ASSURANCE_WEIGHTS.items()
])
wc1, wc2 = st.columns([1, 1.4])
with wc1:
    st.dataframe(weights_display, hide_index=True, use_container_width=True, height=280)
    st.caption(f"Weights sum to {weights_display['weight'].sum():.2f} (should equal 1.00).")
with wc2:
    radar = chart_weights_radar(weights_display["component"].tolist(), weights_display["weight"].tolist())
    st.plotly_chart(radar, use_container_width=True, config={"displaylogo": False})

# ---- Weighted contribution breakdown — only for components actually found -
if component_cols:
    section_title("Weighted Contribution — Which Factor Drives the Score Most",
                   tag=f"{len(component_cols)} of 7 components found in CSV")
    contrib_rows = []
    for key, weight in ASSURANCE_WEIGHTS.items():
        if key not in component_cols:
            continue
        raw_mean = scoring[f"_comp_{key}"].mean()
        if pd.isna(raw_mean):
            continue
        effective_mean = (100 - raw_mean) if key in ASSURANCE_COMPONENT_INVERTED else raw_mean
        label = ASSURANCE_WEIGHT_LABELS[key]
        if key == "safety" and safety_derived_from_dal:
            label += " (derived from safety_level)"
        contrib_rows.append({
            "component": label, "weight": weight,
            "avg_raw_value": round(raw_mean, 1),
            "avg_contribution_to_score": round(weight * effective_mean, 2),
        })

    if contrib_rows:
        contrib_df = pd.DataFrame(contrib_rows).sort_values("avg_contribution_to_score", ascending=False)
        cc1, cc2 = st.columns([1.3, 1])
        with cc1:
            fig = go.Figure(go.Bar(
                x=contrib_df["avg_contribution_to_score"], y=contrib_df["component"],
                orientation="h", marker_color=CHART_COLORS["bar"],
            ))
            fig.update_layout(title="Average Contribution to Assurance Score (points out of 100)",
                               xaxis_title="Avg. contribution", showlegend=False)
            st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True, config={"displaylogo": False})
        with cc2:
            st.dataframe(
                contrib_df.rename(columns={
                    "component": "Component", "weight": "Weight", "avg_raw_value": "Avg Raw Value",
                    "avg_contribution_to_score": "Avg Contribution",
                }),
                hide_index=True, use_container_width=True, height=320,
            )
    missing_keys = [k for k in ASSURANCE_WEIGHTS if k not in component_cols]
    if missing_keys:
        missing_labels = ", ".join(ASSURANCE_WEIGHT_LABELS[k] for k in missing_keys)
        st.caption(f"Not found in the uploaded CSV, so excluded from this breakdown: {missing_labels}.")
else:
    st.info("The uploaded CSV doesn't include any of the assurance scoring component columns (safety, "
            "coverage, fault history, recent change relevance, novelty, flakiness, certification relevance), "
            "so a weighted contribution breakdown isn't available.")

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ============================================================================
# SECTION — Assurance Components (each factor, individually gated)
# ============================================================================
section_title("Assurance Components", tag="every factor found in the uploaded CSV")

comp_cards = st.columns(4)
i = 0
for key, spec in ASSURANCE_COMPONENT_SPECS.items():
    with comp_cards[i % 4]:
        if key in component_cols:
            vals = scoring[f"_comp_{key}"].dropna()
            label = spec["label"].split(" (")[0]
            if key == "safety" and safety_derived_from_dal:
                label += "*"
            metric_card(label, f"{vals.mean():.1f}" if not vals.empty else "N/A", accent=COLORS["accent2"])
        else:
            metric_card(spec["label"].split(" (")[0], "N/A", "not in CSV", accent=COLORS["text_faint"])
    i += 1

if safety_derived_from_dal:
    st.caption("*Safety Criticality was derived from the `safety_level` (DAL) column — no raw safety-"
               "criticality column was found in the uploaded CSV.")

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

comp_grid = st.columns(2)
i = 0
for key, spec in ASSURANCE_COMPONENT_SPECS.items():
    with comp_grid[i % 2]:
        if key in component_cols:
            vals = scoring[f"_comp_{key}"].dropna()
            if not vals.empty:
                hist = chart_generic_histogram(vals, spec["label"],
                                                xaxis_title=spec["label"].split(" (")[0], yaxis_title=f"# {group_label}s")
                st.plotly_chart(hist, use_container_width=True, config={"displaylogo": False})
            else:
                st.info(f"{spec['label']}: column found but contains no usable values.")
        else:
            st.info(f"{spec['label']}: not available — this column wasn't found in the uploaded CSV.")
    i += 1

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ============================================================================
# SECTION — Assurance vs Energy scatter
# ============================================================================
section_title("Assurance vs Energy", tag="best = top-left quadrant")

if not has_assurance_score:
    st.info("Assurance vs Energy comparison cannot be generated because assurance_score is missing.")
else:
    scatter_src = scoring.dropna(subset=["assurance_score", "median_energy_wh"])
    if scatter_src.empty:
        st.info("Not enough data (assurance score and software energy) to plot Assurance vs Energy.")
    else:
        median_energy = scatter_src["median_energy_wh"].median()
        median_score = scatter_src["assurance_score"].median()

        if has_mandatory:
            group_mask = scatter_src["mandatory"].astype(bool)
            group_labels = ("Mandatory", "Optional")
        else:
            group_mask = pd.Series(False, index=scatter_src.index)
            group_labels = ("N/A", "All Runs")

        scatter = chart_two_group_scatter(
            x=scatter_src["median_energy_wh"], y=scatter_src["assurance_score"],
            group_mask=group_mask, group_labels=group_labels,
            title=f"Assurance vs Median Energy per {group_label}",
            xaxis_title="Median Energy (Wh)", yaxis_title="Assurance Score",
            text=scatter_src[group_col],
        )
        scatter.add_vline(x=median_energy, line_dash="dot", line_color=COLORS["grid"])
        scatter.add_hline(y=median_score, line_dash="dot", line_color=COLORS["grid"])
        scatter.add_annotation(x=scatter_src["median_energy_wh"].min(), y=100,
                                xref="x", yref="y", text="Best: high assurance, low energy",
                                showarrow=False, font=dict(color=COLORS["accent"], size=11),
                                xanchor="left", yanchor="top", bgcolor="rgba(0,0,0,0)")
        scatter.add_annotation(x=scatter_src["median_energy_wh"].max(), y=scatter_src["assurance_score"].min(),
                                xref="x", yref="y", text="Worst: low assurance, high energy",
                                showarrow=False, font=dict(color=COLORS["danger"], size=11),
                                xanchor="right", yanchor="bottom", bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(scatter, use_container_width=True, config={"displaylogo": False})

        if has_mandatory or has_safety_level:
            count_labels, count_values = [], []
            if has_safety_level:
                count_labels.append("Safety-critical (DAL-A)")
                count_values.append(int((scoring.get("safety_level") == "DAL-A").sum()))
            if has_mandatory:
                count_labels += ["Mandatory", "Optional"]
                count_values += [int(scoring["mandatory"].astype(bool).sum()),
                                  int((~scoring["mandatory"].astype(bool)).sum())]
            fig = chart_grouped_counts(count_labels, count_values, "Coverage Counts")
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ============================================================================
# SECTION — Ranked tests / scenarios
# ============================================================================
section_title("Ranked " + group_label + "s")

if not has_assurance_score:
    st.info("A ranked table cannot be generated because assurance_score is missing from the uploaded CSV.")
else:
    ranked_src = scoring.dropna(subset=["assurance_score"]).copy()
    if ranked_src.empty:
        st.info("No rows with a usable assurance_score were found.")
    else:
        rename_cols = {group_col: group_label + " ID", "assurance_score": "Assurance Score",
                       "median_energy_wh": "Median Energy (Wh)"}
        show_cols = [group_col, "assurance_score"]
        if has_safety_level:
            show_cols.append("safety_level")
            rename_cols["safety_level"] = "DAL"
        if has_mandatory:
            show_cols.append("mandatory")
            rename_cols["mandatory"] = "Mandatory"
        for key, spec in ASSURANCE_COMPONENT_SPECS.items():
            if key in component_cols:
                col = f"_comp_{key}"
                show_cols.append(col)
                rename_cols[col] = spec["label"].split(" (")[0]
        show_cols.append("median_energy_wh")

        tab1, tab2, tab3 = st.tabs([f"Top 15 by Assurance", f"Bottom 15 by Assurance", "Full Table"])
        with tab1:
            top = ranked_src.sort_values("assurance_score", ascending=False).head(15)[show_cols].rename(columns=rename_cols)
            st.dataframe(top, hide_index=True, use_container_width=True)
        with tab2:
            bot = ranked_src.sort_values("assurance_score", ascending=True).head(15)[show_cols].rename(columns=rename_cols)
            st.dataframe(bot, hide_index=True, use_container_width=True)
        with tab3:
            search = st.text_input(f"Search {group_label.lower()} ID", key="assurance_search")
            full = ranked_src[show_cols].copy()
            if search:
                full = full[full[group_col].astype(str).str.upper().str.contains(search.strip().upper(), na=False)]
            full_show = full.rename(columns=rename_cols)
            for c in full_show.select_dtypes(include=[float]).columns:
                full_show[c] = full_show[c].round(2)
            st.dataframe(full_show, hide_index=True, use_container_width=True, height=340)
            st.download_button(
                "⬇ Download assurance_scoring.csv", full_show.to_csv(index=False).encode(),
                file_name="assurance_scoring.csv", mime="text/csv",
            )

st.markdown(
    f"""<div class="gat-footer-note">
    GreenAeroTester assurance view · driven entirely by the uploaded CSV
    (<code>{st.session_state.get('gat_active_file', '')}</code>, {len(df):,} rows) · upload a different CSV on the
    Home page at any time to refresh every KPI, chart, and table here.
    </div>""",
    unsafe_allow_html=True,
)