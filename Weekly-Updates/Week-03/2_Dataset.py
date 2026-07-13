# ============================================================================
# GreenAeroTester — shared UI helpers.
# This block is intentionally IDENTICAL (in spirit) to the one in Home.py —
# see the note there about why each page reproduces it rather than importing
# a shared module. This copy is trimmed to only what the Dataset page needs.
#
# Phase 9 note (this page): the Dataset page no longer generates or reads any
# synthetic/dummy dataset (scenario_parameters / test_catalog / test_runs).
# It reads the SAME uploaded, validated dataset the Home page owns —
# st.session_state["gat_dataset"] — plus the SAME validation summary Home
# already computed — st.session_state["gat_validation_summary"] — so every
# number shown here (missing values, duplicate rows, invalid rows) is
# derived from the actual uploaded CSV, never recomputed from or replaced by
# hardcoded data. Whenever a new CSV is uploaded on Home (Upload/Change),
# this page automatically reflects it on its next render, because it always
# reads straight out of session state rather than caching anything locally.
# If no dataset is active (nothing uploaded yet, or the last upload failed
# validation), this page shows the same locked state as Home instead of any
# placeholder numbers.
# ============================================================================

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
    """Identical lock UI to Home.py: sidebar/nav stay visible but disabled,
    with a small explanatory note, whenever there's no active validated
    dataset (see the Home.py copy of this function for the full rationale)."""
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
# Flexible column lookup for the two optional dimensions the shared upload
# validator on Home.py doesn't canonicalize (weather / fault type). Every
# other column this page uses (run_id, scenario_id, test_id, flight_phase,
# status, mandatory, safety_level) is already canonicalized by Home's
# load_and_validate_csv, so they're addressed directly by their canonical
# name, exactly like Home.py does (has_status, has_flight_phase, etc.).
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


# ============================================================================
# PAGE: Dataset Overview (SRS §13.2, §9 cleaning rules)
#
# Phase 9: fully CSV-driven. There is exactly one active dataset — the same
# one Home.py stores in st.session_state["gat_dataset"] once it passes
# validation — and this page never generates, caches, or falls back to any
# data of its own. If Home's dataset changes (a new file is uploaded there,
# via first upload or Change), this page picks it up automatically on its
# next render since it reads session state fresh every run.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester — Dataset", page_icon="🗂️",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()
sidebar_brand()

stage = st.session_state.get("gat_stage")
dataset = st.session_state.get("gat_dataset")
summary = st.session_state.get("gat_validation_summary")

# ---- Locked state: no active validated dataset. Mirrors Home.py exactly —
# same sidebar lock notice, same "go upload a CSV" message, nothing below
# renders (no charts/tables/summaries with stale or placeholder numbers). --
if stage != "unlocked" or dataset is None:
    sidebar_lock_notice()
    page_header(
        "PHASE 1 · DATASET",
        "Dataset Overview",
        "Scenario catalog, parameter distributions and data-quality summary",
    )
    if st.session_state.get("gat_invalid_errors"):
        st.error(
            "The most recently uploaded file failed validation on the Home page, so no dataset is active. "
            "Go to Home to upload a corrected CSV."
        )
    else:
        st.info("No dataset uploaded yet. Please upload a CSV file on the Home page to begin.")
    st.stop()

# ---- Active dataset from here on ------------------------------------------
df = dataset
sidebar_status_footer(df, filename=st.session_state.get("gat_active_file"))

page_header(
    "PHASE 1 · DATASET",
    "Dataset Overview",
    "Scenario catalog, parameter distributions and data-quality summary",
    pill_text=f"{df['scenario_id'].nunique():,} scenarios · {len(df):,} runs",
)

# ---- Optional-column detection (same pattern as Home.py's has_status etc.) -
has_flight_phase = "flight_phase" in df.columns
has_status = "status" in df.columns
has_safety = "safety_level" in df.columns
has_mandatory = "mandatory" in df.columns
has_test_id = "test_id" in df.columns

weather_col = _find_column(df.columns, WEATHER_ALIASES)
fault_col = _find_column(df.columns, FAULT_ALIASES)
has_weather = weather_col is not None
has_fault = fault_col is not None

# ---- KPI row (from Home's validation summary — never recomputed here) -----
total_missing = summary["missing_values"]
duplicate_rows = summary["duplicate_rows"]
duplicate_run_ids = summary["duplicate_run_ids"]
duplicate_scenario_ids = summary["duplicate_scenario_ids"]
invalid_rows = summary["invalid_rows"]
negative_runtime = summary["negative_runtime"]
negative_energy = summary["negative_energy"]

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Total Scenarios", fmt_num(df["scenario_id"].nunique()), accent=COLORS["accent2"])
with c2:
    metric_card("Missing Values", fmt_num(total_missing),
                "none found" if total_missing == 0 else "flagged below",
                accent=COLORS["accent"] if total_missing == 0 else COLORS["amber"])
with c3:
    metric_card("Duplicate Rows", fmt_num(duplicate_rows),
                "SRS §9 rule 1" if duplicate_rows else "none found",
                accent=COLORS["accent"] if duplicate_rows == 0 else COLORS["danger"])
with c4:
    metric_card("Invalid Rows", fmt_num(invalid_rows),
                "SRS §9 rule 2" if invalid_rows else "none found",
                accent=COLORS["accent"] if invalid_rows == 0 else COLORS["danger"])

# ---- Dataset Preview --------------------------------------------------------
section_title("Dataset Preview", tag=f"{len(df):,} rows total")
show_full = st.checkbox("Show full dataset instead of the first 20 rows", value=False)
st.dataframe(df if show_full else df.head(20), use_container_width=True,
             height=420 if show_full else 320, hide_index=True)

# ---- Distributions --------------------------------------------------------
section_title("Scenario Composition")

dist_cols = []
if has_flight_phase:
    dist_cols.append("phase")
if has_weather:
    dist_cols.append("weather")
if has_fault:
    dist_cols.append("fault")
if has_safety:
    dist_cols.append("safety")

if dist_cols:
    for i in range(0, len(dist_cols), 2):
        row = dist_cols[i:i + 2]
        cols = st.columns(len(row))
        for kind, col in zip(row, cols):
            with col:
                if kind == "phase":
                    ph = df["flight_phase"].value_counts()
                    fig = go.Figure(go.Bar(x=ph.values, y=ph.index, orientation="h",
                                            marker=dict(color=CHART_COLORS["bar"])))
                    fig.update_layout(title="Flight Phase Distribution")
                    st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True,
                                     config={"displaylogo": False})
                elif kind == "weather":
                    we = df[weather_col].value_counts()
                    fig = go.Figure(go.Pie(labels=we.index, values=we.values, hole=0.55))
                    fig.update_traces(marker=dict(colors=CHART_COLORS["pie"]))
                    fig.update_layout(title="Weather Condition Mix")
                    st.plotly_chart(apply_plotly_theme(fig, 320), use_container_width=True,
                                     config={"displaylogo": False})
                elif kind == "fault":
                    fa = df[fault_col].value_counts()
                    fig = go.Figure(go.Bar(x=fa.index, y=fa.values, marker=dict(color=CHART_COLORS["bar"])))
                    fig.update_layout(title="Fault Type Distribution")
                    st.plotly_chart(apply_plotly_theme(fig, 300), use_container_width=True,
                                     config={"displaylogo": False})
                elif kind == "safety":
                    sl = df["safety_level"].value_counts()
                    fig = go.Figure(go.Bar(x=sl.index, y=sl.values, marker=dict(color=CHART_COLORS["line"])))
                    fig.update_layout(title="Safety Level (DAL) Distribution")
                    st.plotly_chart(apply_plotly_theme(fig, 300), use_container_width=True,
                                     config={"displaylogo": False})
else:
    st.info("The uploaded CSV doesn't include flight phase, weather, fault type, or safety level columns — "
            "composition charts aren't available for this dataset.")

# ---- Missing-Value Summary --------------------------------------------------
section_title("Missing-Value Summary")
missing_rows = []
col_missing = df.isna().sum()
for col, cnt in col_missing.items():
    if cnt > 0:
        missing_rows.append({
            "Column": col, "Missing Count": int(cnt),
            "Missing %": round(100 * cnt / len(df), 2),
        })

if missing_rows:
    st.dataframe(pd.DataFrame(missing_rows).sort_values("Missing Count", ascending=False),
                 use_container_width=True, hide_index=True)
else:
    st.success("No missing values found in the uploaded dataset.")

# ---- Duplicate-Row Summary ---------------------------------------------------
section_title("Duplicate-Row Summary")
dr1, dr2, dr3 = st.columns(3)
with dr1:
    metric_card("Duplicate Rows (exact)", fmt_num(duplicate_rows),
                accent=(COLORS["danger"] if duplicate_rows else COLORS["accent"]))
with dr2:
    metric_card("Duplicate run_id", fmt_num(duplicate_run_ids),
                accent=(COLORS["danger"] if duplicate_run_ids else COLORS["accent"]))
with dr3:
    metric_card("Duplicate scenario_id", fmt_num(duplicate_scenario_ids),
                accent=(COLORS["amber"] if duplicate_scenario_ids else COLORS["accent"]))
if duplicate_rows == 0 and duplicate_run_ids == 0 and duplicate_scenario_ids == 0:
    st.success("No duplicate rows, run IDs, or scenario IDs found in the uploaded dataset.")

# ---- Invalid Rows Summary ----------------------------------------------------
section_title("Invalid Rows Summary")
invalid_check_rows = [
    {"Check": "Invalid Rows (runtime/energy missing or negative)", "Count": invalid_rows,
     "Description": "Rows with a missing/negative runtime_s or software_energy_wh (SRS §9 rule 2)"},
    {"Check": "Negative Runtime", "Count": negative_runtime,
     "Description": "Rows with a negative runtime_s value"},
    {"Check": "Negative Energy", "Count": negative_energy,
     "Description": "Rows with a negative software_energy_wh value"},
    {"Check": "Duplicate Run IDs", "Count": duplicate_run_ids,
     "Description": "Same run_id appearing more than once in the uploaded CSV"},
    {"Check": "Duplicate Scenario IDs", "Count": duplicate_scenario_ids,
     "Description": "Same scenario_id appearing more than once in the uploaded CSV"},
]
if has_safety:
    invalid_check_rows.append({
        "Check": "Missing Safety Level", "Count": int(df["safety_level"].isna().sum()),
        "Description": "Rows without a DAL safety level assigned",
    })

invalid_checks = pd.DataFrame(invalid_check_rows)
invalid_checks["Status"] = invalid_checks["Count"].apply(lambda c: "✅ OK" if c == 0 else "⚠ Flagged")
st.dataframe(invalid_checks, use_container_width=True, hide_index=True)
st.caption("Per SRS §9: outliers/invalid rows are flagged here, not silently removed. "
           "Processed data may exclude these, with the reason documented.")

# ---- Filters + search --------------------------------------------------------
section_title("Uploaded Dataset Explorer")

filter_defs = []
if has_flight_phase:
    filter_defs.append(("flight_phase", "Flight phase", sorted(df["flight_phase"].dropna().unique().tolist())))
if has_weather:
    filter_defs.append((weather_col, "Weather", sorted(df[weather_col].dropna().unique().tolist())))
if has_fault:
    filter_defs.append((fault_col, "Fault type", sorted(df[fault_col].dropna().unique().tolist())))
if has_safety:
    filter_defs.append(("safety_level", "Safety level", sorted(df["safety_level"].dropna().unique().tolist())))
if has_status:
    filter_defs.append(("status", "Status", sorted(df["status"].dropna().unique().tolist())))

selections = {}
for i in range(0, len(filter_defs), 4):
    row = filter_defs[i:i + 4]
    cols = st.columns(len(row))
    for (col_name, label, options), c in zip(row, cols):
        with c:
            selections[col_name] = st.multiselect(label, options, default=[], key=f"gat_ds_filter_{col_name}")

fc1, fc2 = st.columns([1, 2])
with fc1:
    f_mandatory = (st.selectbox("Mandatory", ["All", "Mandatory only", "Optional only"])
                   if has_mandatory else "All")
with fc2:
    search_hint = "run_id" + (" / scenario_id" ) + (" / test_id" if has_test_id else "")
    f_search = st.text_input(f"Search by {search_hint}", placeholder="e.g. R000123 or S0250")

view = df.copy()
for col_name, values in selections.items():
    if values:
        view = view[view[col_name].isin(values)]
if has_mandatory:
    if f_mandatory == "Mandatory only":
        view = view[view["mandatory"].astype(bool)]
    elif f_mandatory == "Optional only":
        view = view[~view["mandatory"].astype(bool)]
if f_search:
    s = f_search.strip().upper()
    id_cols = ["run_id", "scenario_id"] + (["test_id"] if has_test_id else [])
    mask = False
    for col_name in id_cols:
        mask = mask | view[col_name].astype(str).str.upper().str.contains(s, na=False)
    view = view[mask]

st.caption(f"Showing {len(view):,} of {len(df):,} rows")
st.dataframe(view, use_container_width=True, height=380, hide_index=True)

st.download_button(
    "⬇ Download filtered dataset (CSV)", view.to_csv(index=False).encode(),
    file_name="dataset_filtered.csv", mime="text/csv",
)

st.markdown(
    f"""<div class="gat-footer-note">
    GreenAeroTester dataset view · driven entirely by the uploaded CSV (<code>{st.session_state.get('gat_active_file', '')}</code>,
    {len(df):,} rows) · upload a different CSV on the Home page at any time to refresh every chart, filter, and summary here.
    </div>""",
    unsafe_allow_html=True,
)