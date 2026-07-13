# ============================================================================
# GreenAeroTester — shared UI helpers + CSV-driven dataset model.
# This block is intentionally IDENTICAL across all 8 frontend files.
# Rationale: the brief restricts output to exactly 8 files with no shared
# utility module, so this same block is reproduced verbatim on every page.
#
# Phase 8 note: the dashboard NO LONGER generates a synthetic dummy dataset.
# The uploaded CSV (validated and normalized in `load_and_validate_csv`) is
# the single source of truth for every card, chart, and table on this page.
# It is stored in st.session_state["gat_dataset"] once it passes validation
# and stays active until a new CSV is successfully uploaded — selecting a
# replacement file or clicking Discard never touches the active dataset.
#
# Phase 9 note (bug-fix pass): three targeted fixes on top of Phase 8, with
# no other behavior touched:
#   1) The upload-success confirmation is now a self-contained, CSS-driven
#      popup gated by a one-shot session-state flag, instead of relying on
#      st.toast surviving an immediately-following st.rerun(). It only ever
#      fires on the single script run right after a *successful* upload.
#   2) The Change workflow no longer leaves a stale, previously-valid
#      dataset on screen when the newly selected replacement file fails
#      validation. A failed upload — whether it's the first upload or a
#      Change — now clears gat_dataset/gat_active_file/gat_validation_summary
#      entirely and drops back to the locked state, so the dashboard can
#      never render KPIs/charts/tables sourced from an older file. Instead,
#      only the validation errors for the *newly* uploaded file are shown.
#   3) render_validation_summary() now renders the checklist as a proper
#      bordered/zebra-striped HTML table with pass/fail badges instead of
#      plain markdown rows. Same information, no data changes.
# ============================================================================

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
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


def relabel_upload_buttons():
    """Streamlit's file_uploader always renders its own internal button
    labeled 'Browse files' with no public API to rename it. A CSS overlay
    (transparent text + ::after content) is fragile — it can render both
    layers at once and look garbled, which is what happened before. This
    instead rewrites the button's actual text in the DOM, and re-applies
    on every rerender via a MutationObserver, so every file_uploader on
    this page reliably reads 'Select File'."""
    components.html(
        """
        <script>
        const relabel = () => {
            const doc = window.parent.document;
            doc.querySelectorAll('[data-testid="stFileUploaderDropzone"] button').forEach((btn) => {
                const t = btn.textContent.trim().toLowerCase();
                if (t.startsWith('browse') || t.startsWith('select file')) {
                    btn.textContent = 'Select File';
                }
            });
        };
        relabel();
        new MutationObserver(relabel).observe(window.parent.document.body, {childList: true, subtree: true});
        </script>
        """,
        height=0,
    )


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
    """Rendered in the sidebar whenever no dataset has been uploaded yet.
    The sidebar itself (and Streamlit's auto-generated page navigation)
    stays visible so the user can see what the app offers, but the nav
    links are visually disabled and clicks on them are intercepted client
    side so no navigation actually occurs (SRS: sidebar visible, locked)."""
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
                 No dataset uploaded yet. Please upload a CSV file to unlock the application.
            </div>
            """,
            unsafe_allow_html=True,
        )
    # Client-side click interception: Streamlit's built-in multipage nav has
    # no public "disabled" API, so real navigation is prevented by capturing
    # the click before it bubbles, and a small toast explains why.
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
# Dataset model (SRS §5–§12): the uploaded CSV is the ONLY dataset used by
# this page. CARBON_INTENSITY_G_PER_KWH is kept as a documented fixed
# grid-average assumption, used only as a fallback when the CSV has no
# carbon column of its own.
# ---------------------------------------------------------------------------
CARBON_INTENSITY_G_PER_KWH = 475.0
SCHEMA_VERSION = "v1.0"
MAX_UPLOAD_MB = 100

# canonical_name -> acceptable header spellings (matched case/space/underscore-insensitively)
REQUIRED_COLUMN_ALIASES = {
    "run_id": ["run_id", "runid", "run id"],
    "scenario_id": ["scenario_id", "scenarioid", "scenario id"],
    "runtime_s": ["runtime_s", "runtime", "runtime_sec", "runtime_seconds", "runtime (s)"],
    "software_energy_wh": ["software_energy_wh", "energy_wh", "software_energy", "energy",
                            "software energy (wh)"],
}
OPTIONAL_COLUMN_ALIASES = {
    "status": ["status", "run_status", "test_status"],
    "test_id": ["test_id", "testid"],
    "flight_phase": ["flight_phase", "phase", "category"],
    "mandatory": ["mandatory", "is_mandatory"],
    "safety_level": ["safety_level", "dal", "safety"],
    "assurance_score": ["assurance_score", "assurance"],
    "timestamp": ["timestamp", "time", "datetime"],
    "avg_power_w": ["avg_power_w", "power_w", "avg_power"],
    "carbon_gco2": ["carbon_gco2", "carbon_g", "estimated_carbon_gco2", "carbon"],
}


def _norm(s):
    return str(s).strip().lower().replace(" ", "_")


def _find_column(columns, aliases):
    normalized = {_norm(c): c for c in columns}
    for a in aliases:
        if _norm(a) in normalized:
            return normalized[_norm(a)]
    return None


def load_and_validate_csv(uploaded_file):
    """Reads the uploaded CSV in full, resolves required/optional columns
    (flexible header matching), and computes a validation summary. Never
    raises — returns (ok, df_normalized_or_None, summary_dict, error_messages).
    This is the ONLY place a raw CSV is turned into the dataset the rest of
    the Home page reads from."""
    try:
        size_mb = uploaded_file.size / (1024 * 1024)
        if size_mb > MAX_UPLOAD_MB:
            return False, None, {}, [f"This file is {size_mb:.1f} MB, which exceeds the {MAX_UPLOAD_MB} MB upload limit."]

        uploaded_file.seek(0)
        raw = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)

        if raw.shape[1] == 0:
            return False, None, {}, ["No columns were found in this file. Please check the CSV and try again."]
        if raw.dropna(how="all").empty:
            return False, None, {}, ["This file doesn't contain any data rows."]

    except pd.errors.EmptyDataError:
        return False, None, {}, ["This file is empty. Please choose a CSV file that contains data."]
    except pd.errors.ParserError:
        return False, None, {}, ["This file could not be parsed as a valid CSV. It may be corrupted."]
    except UnicodeDecodeError:
        return False, None, {}, ["This file's encoding isn't supported. Please export it as a UTF-8 CSV."]
    except Exception:
        return False, None, {}, ["This file could not be read. Please check the file and try again."]

    # ---- Resolve required columns -----------------------------------------
    colmap = {}
    missing_required = []
    for canon, aliases in REQUIRED_COLUMN_ALIASES.items():
        found = _find_column(raw.columns, aliases)
        if found:
            colmap[canon] = found
        else:
            missing_required.append(canon)

    if missing_required:
        msgs = [f"This CSV cannot be fully analyzed because {m} is missing." for m in missing_required]
        return False, None, {}, msgs

    # ---- Resolve optional columns ------------------------------------------
    for canon, aliases in OPTIONAL_COLUMN_ALIASES.items():
        found = _find_column(raw.columns, aliases)
        if found:
            colmap[canon] = found

    df = raw.rename(columns={src: canon for canon, src in colmap.items()}).copy()

    # ---- Numeric coercion for required numeric fields ----------------------
    runtime_numeric = pd.to_numeric(df["runtime_s"], errors="coerce")
    energy_numeric = pd.to_numeric(df["software_energy_wh"], errors="coerce")
    runtime_numeric_ok = runtime_numeric.notna().all()
    energy_numeric_ok = energy_numeric.notna().all()
    df["runtime_s"] = runtime_numeric
    df["software_energy_wh"] = energy_numeric

    run_ids_ok = df["run_id"].notna().all() and df["run_id"].astype(str).str.strip().ne("").all()
    scenario_ids_ok = df["scenario_id"].notna().all() and df["scenario_id"].astype(str).str.strip().ne("").all()

    negative_runtime = int((df["runtime_s"] < 0).sum())
    negative_energy = int((df["software_energy_wh"] < 0).sum())
    missing_values = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    duplicate_run_ids = int(df["run_id"].duplicated().sum())
    duplicate_scenario_ids = int(df["scenario_id"].duplicated().sum())

    invalid_row_mask = (
        df["runtime_s"].isna() | df["software_energy_wh"].isna() |
        (df["runtime_s"] < 0) | (df["software_energy_wh"] < 0)
    )
    invalid_rows = int(invalid_row_mask.sum())
    total_rows = len(df)

    # ---- Reject ONLY for the three documented cases ------------------------
    # 1) a required column is missing (already handled earlier in this
    #    function, before we ever reach this point).
    # 2) every runtime/energy value is invalid (missing or negative) — there
    #    is nothing usable left to analyze.
    if total_rows > 0 and invalid_rows == total_rows:
        return False, None, {}, [
            "This CSV cannot be analyzed because all runtime/energy values are missing or negative."
        ]

    # Exclude invalid/negative rows from analysis instead of rejecting the
    # whole file — this is the "warn, don't reject" case.
    cleaned = df[~invalid_row_mask].reset_index(drop=True)

    # 3) after excluding invalid/negative rows, zero valid rows remain.
    if cleaned.empty:
        return False, None, {}, [
            "This CSV cannot be analyzed because no valid rows remain after removing invalid or "
            "negative runtime/energy values."
        ]

    if "timestamp" in cleaned.columns:
        cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"], errors="coerce")

    summary = dict(
        required_columns_ok=True,
        run_ids_ok=bool(run_ids_ok),
        scenario_ids_ok=bool(scenario_ids_ok),
        runtime_numeric_ok=bool(runtime_numeric_ok),
        energy_numeric_ok=bool(energy_numeric_ok),
        missing_values=missing_values,
        duplicate_rows=duplicate_rows,
        invalid_rows=invalid_rows,
        excluded_invalid_rows=invalid_rows,
        duplicate_run_ids=duplicate_run_ids,
        duplicate_scenario_ids=duplicate_scenario_ids,
        negative_runtime=negative_runtime,
        negative_energy=negative_energy,
        status_column="status" in df.columns,
        energy_column=True,
        row_count=len(cleaned),
    )

    return True, cleaned, summary, []


# ---------------------------------------------------------------------------
# FIX #3: Validation Summary table — redesigned as a bordered, zebra-striped
# HTML table with pass/fail badges, matching the professional look of the
# rest of the dashboard's tables/cards. The information shown is unchanged;
# only the presentation is new.
# ---------------------------------------------------------------------------
def render_validation_summary(summary):
    section_title("Validation Summary", tag="upload check")

    checks = [
        ("Required Columns", summary["required_columns_ok"]),
        ("Run IDs", summary["run_ids_ok"]),
        ("Scenario IDs", summary["scenario_ids_ok"]),
        ("Runtime Numeric", summary["runtime_numeric_ok"]),
        ("Energy Numeric", summary["energy_numeric_ok"]),
        ("Status Column", summary["status_column"]),
        ("Energy Column", summary["energy_column"]),
    ]

    rows_html = ""
    for i, (label, ok) in enumerate(checks):
        icon = "✓" if ok else "✗"
        state_cls = "gat-vt-ok" if ok else "gat-vt-bad"
        zebra_cls = "gat-vt-alt" if i % 2 == 1 else ""
        rows_html += f"""
        <tr class="{zebra_cls}">
            <td class="gat-vt-label">{label}</td>
            <td class="gat-vt-status">
                <span class="gat-vt-badge {state_cls}">{icon} {'Pass' if ok else 'Fail'}</span>
            </td>
        </tr>
        """

    st.markdown(
        f"""
        <style>
        .gat-vt-wrap {{
            border: 1px solid {COLORS.get('border', 'rgba(128,128,128,0.25)')};
            border-radius: 12px;
            overflow: hidden;
            background: {COLORS.get('bg_elevated', 'rgba(128,128,128,0.06)')};
        }}
        .gat-vt-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Inter', sans-serif;
            font-size: 13.5px;
        }}
        .gat-vt-table td {{
            padding: 11px 18px;
            border-bottom: 1px solid {COLORS.get('border', 'rgba(128,128,128,0.15)')};
            vertical-align: middle;
        }}
        .gat-vt-table tr:last-child td {{ border-bottom: none; }}
        .gat-vt-alt {{ background: rgba(128,128,128,0.045); }}
        .gat-vt-label {{ color: {COLORS.get('text_faint', '#c9c9c9')}; font-weight: 500; }}
        .gat-vt-status {{ text-align: right; width: 1%; white-space: nowrap; }}
        .gat-vt-badge {{
            display: inline-flex; align-items: center; gap: 5px;
            padding: 3px 11px; border-radius: 999px; font-size: 12px; font-weight: 600;
            letter-spacing: 0.2px;
        }}
        .gat-vt-ok {{
            background: {COLORS['accent']}1f; color: {COLORS['accent']}; border: 1px solid {COLORS['accent']}55;
        }}
        .gat-vt-bad {{
            background: {COLORS['danger']}1f; color: {COLORS['danger']}; border: 1px solid {COLORS['danger']}55;
        }}
        @media (max-width: 640px) {{
            .gat-vt-table td {{ padding: 8px 12px; font-size: 12.5px; }}
            .gat-vt-badge {{ padding: 2px 8px; font-size: 11px; }}
        }}
        </style>
        <div class="gat-vt-wrap">
            <table class="gat-vt-table">
                {rows_html}
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        metric_card("Missing Values", fmt_num(summary["missing_values"]),
                    accent=(COLORS["amber"] if summary["missing_values"] else COLORS["accent"]))
    with rc2:
        metric_card("Duplicate Rows", fmt_num(summary["duplicate_rows"]),
                    accent=(COLORS["amber"] if summary["duplicate_rows"] else COLORS["accent"]))
    with rc3:
        metric_card("Invalid Rows", fmt_num(summary["invalid_rows"]),
                    accent=(COLORS["danger"] if summary["invalid_rows"] else COLORS["accent"]))

    warnings = []
    if summary["duplicate_run_ids"]:
        warnings.append(f"{summary['duplicate_run_ids']} duplicate run_id value(s) were found.")
    if summary["duplicate_scenario_ids"]:
        warnings.append(f"{summary['duplicate_scenario_ids']} duplicate scenario_id value(s) were found.")
    if summary.get("excluded_invalid_rows"):
        warnings.append(
            f"Dataset contains invalid negative runtime/energy values. These rows will be excluded "
            f"from analysis. ({summary['excluded_invalid_rows']} row(s) excluded.)"
        )
        if summary["negative_runtime"]:
            warnings.append(f"{summary['negative_runtime']} row(s) have a negative runtime value.")
        if summary["negative_energy"]:
            warnings.append(f"{summary['negative_energy']} row(s) have a negative software_energy_wh value.")
    if warnings:
        st.warning("  \n".join(warnings))


# ---------------------------------------------------------------------------
# FIX #2 support: rendered INSTEAD of the dashboard whenever the most
# recently uploaded CSV (whether it's the first upload or a Change) fails
# validation. This never mixes in data from an older dataset — by the time
# this renders, gat_dataset/gat_active_file/gat_validation_summary have
# already been cleared, so nothing below this point can read stale data.
# ---------------------------------------------------------------------------
def render_validation_errors_panel(filename, errors):
    section_title("Validation Summary", tag="upload check")
    st.markdown(
        f"""
        <style>
        .gat-vfail-wrap {{
            border: 1px solid {COLORS['danger']}55;
            border-radius: 12px;
            overflow: hidden;
            background: {COLORS.get('bg_elevated', 'rgba(128,128,128,0.06)')};
        }}
        .gat-vfail-head {{
            display: flex; align-items: center; gap: 12px;
            padding: 16px 18px;
            border-bottom: 1px solid {COLORS.get('border', 'rgba(128,128,128,0.2)')};
        }}
        .gat-vfail-icon {{
            display: flex; align-items: center; justify-content: center;
            width: 34px; height: 34px; border-radius: 50%;
            background: {COLORS['danger']}1f; color: {COLORS['danger']};
            font-size: 17px; font-weight: 700; flex-shrink: 0;
        }}
        .gat-vfail-title {{
            font-family: 'Space Grotesk', sans-serif; font-size: 14.5px; font-weight: 600;
            color: {COLORS.get('text_faint', '#e6e6e6')};
        }}
        .gat-vfail-file {{
            font-size: 12.5px; color: {COLORS.get('text_dim', '#9a9a9a')}; margin-top: 2px;
        }}
        .gat-vfail-list {{
            list-style: none; margin: 0; padding: 6px 18px 16px 18px;
        }}
        .gat-vfail-list li {{
            display: flex; align-items: flex-start; gap: 10px;
            padding: 8px 0; font-size: 13.5px;
            color: {COLORS.get('text_faint', '#e6e6e6')};
            border-bottom: 1px solid {COLORS.get('border', 'rgba(128,128,128,0.1)')};
        }}
        .gat-vfail-list li:last-child {{ border-bottom: none; }}
        .gat-vfail-bullet {{
            color: {COLORS['danger']}; font-weight: 700; flex-shrink: 0; line-height: 1.4;
        }}
        </style>
        <div class="gat-vfail-wrap">
            <div class="gat-vfail-head">
                <span class="gat-vfail-icon">✗</span>
                <div>
                    <div class="gat-vfail-title">This CSV cannot be fully analyzed</div>
                    <div class="gat-vfail-file">{filename}</div>
                </div>
            </div>
            <ul class="gat-vfail-list">
                {''.join(f'<li><span class="gat-vfail-bullet">✗</span><span>{e}</span></li>' for e in errors)}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "No dashboard data is being shown for this file. Upload a corrected CSV to view scenarios, "
        "charts, and summary cards for it."
    )


# ---------------------------------------------------------------------------
# FIX #1 support: a self-dismissing success popup, rendered exactly once on
# the script run immediately following a successful upload (see the one-shot
# `gat_show_success_popup` flag at the call site). Using a pure-CSS animation
# gated by session state — rather than st.toast() right before st.rerun() —
# means the popup always appears on that run, instead of depending on
# st.toast's fragile "survive exactly one rerun" behavior.
# ---------------------------------------------------------------------------
def render_success_popup(message="Dataset uploaded successfully."):
    st.markdown(
        f"""
        <style>
        @keyframes gatPopupInOut {{
            0%   {{ opacity: 0; transform: translate(-50%, -14px); }}
            8%   {{ opacity: 1; transform: translate(-50%, 0); }}
            85%  {{ opacity: 1; transform: translate(-50%, 0); }}
            100% {{ opacity: 0; transform: translate(-50%, -14px); }}
        }}
        .gat-success-popup {{
            position: fixed;
            top: 18px;
            left: 50%;
            z-index: 100000;
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 20px;
            border-radius: 10px;
            background: {COLORS.get('bg_elevated', '#1f2430')};
            border: 1px solid {COLORS['accent']}66;
            box-shadow: 0 8px 24px rgba(0,0,0,0.28);
            color: {COLORS.get('text_faint', '#e6e6e6')};
            font-family: 'Inter', sans-serif;
            font-size: 13.5px;
            font-weight: 500;
            pointer-events: none;
            animation: gatPopupInOut 3.6s ease forwards;
        }}
        .gat-success-popup .gat-success-icon {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 20px; height: 20px;
            border-radius: 50%;
            background: {COLORS['accent']}22;
            color: {COLORS['accent']};
            font-size: 12.5px;
            flex-shrink: 0;
        }}
        </style>
        <div class="gat-success-popup">
            <span class="gat-success-icon">✓</span>
            <span>{message}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# PAGE: Home — Mission Control (SRS §13.1)
#
# Upload workflow — persistent toolbar
# -------------------------------------
# The entire upload lifecycle lives in a single horizontal toolbar pinned to
# the very top of the app. The toolbar is rendered unconditionally, before
# anything else on the page, and never unmounts — it is the same block of
# code whether the dashboard is locked or already showing data. Only its
# *contents* (which buttons are enabled, what the status area says) change
# with state, exactly like a desktop app's toolbar would.
#
# State machine (st.session_state["gat_stage"]):
#   "locked"   -> nothing uploaded yet, OR the most recently uploaded file
#                 failed validation (see gat_invalid_errors below). Sidebar
#                 visible but nav is disabled, dashboard hidden.
#   "staged"   -> a CSV has been picked in the Select File control but not
#                 committed with Upload yet.
#   "unlocked" -> a dataset has been committed and PASSED validation.
#                 Sidebar nav + dashboard render below the toolbar, driven
#                 entirely by st.session_state["gat_dataset"]. "Change" lets
#                 the user stage a replacement file without ever leaving
#                 this page. The previously uploaded dataset keeps driving
#                 every card/chart/table only until Upload is clicked; the
#                 instant a replacement is submitted, the outcome of ITS OWN
#                 validation — not the old dataset — decides what's shown
#                 next (see gat_invalid_errors).
#
# gat_invalid_errors / gat_invalid_filename hold the validation errors for
# the most recently *rejected* upload (initial or Change). Whenever they are
# set, gat_dataset/gat_active_file/gat_validation_summary are guaranteed to
# be None — a failed upload always fully clears any previously active
# dataset, so the dashboard can never show results from an older file.
# ============================================================================

st.set_page_config(page_title="GreenAeroTester — Home", page_icon="🌱",
                    layout="wide", initial_sidebar_state="expanded")
inject_css()

# ---- Toolbar / upload state --------------------------------------------------
if "gat_stage" not in st.session_state:
    st.session_state["gat_stage"] = "locked"          # locked | staged | unlocked
if "gat_active_file" not in st.session_state:
    st.session_state["gat_active_file"] = None
if "gat_uploader_key" not in st.session_state:
    st.session_state["gat_uploader_key"] = 0
if "gat_change_mode" not in st.session_state:
    st.session_state["gat_change_mode"] = False
if "gat_status_msg" not in st.session_state:
    st.session_state["gat_status_msg"] = None          # (kind, text)
if "gat_dataset" not in st.session_state:
    st.session_state["gat_dataset"] = None              # the ONLY data source once unlocked
if "gat_validation_summary" not in st.session_state:
    st.session_state["gat_validation_summary"] = None
if "gat_invalid_errors" not in st.session_state:
    st.session_state["gat_invalid_errors"] = None       # errors for the most recently rejected upload
if "gat_invalid_filename" not in st.session_state:
    st.session_state["gat_invalid_filename"] = None
if "gat_show_success_popup" not in st.session_state:
    st.session_state["gat_show_success_popup"] = False  # one-shot flag, see FIX #1

stage = st.session_state["gat_stage"]

# ---- Sidebar: ALWAYS visible. Navigation is only enabled once unlocked. ----
sidebar_brand()
if stage != "unlocked":
    sidebar_lock_notice()

# ---- Project heading first, upload toolbar right below it -------------------
page_header(
    "MISSION CONTROL",
    "GreenAeroTester",
    "Energy-aware validation for aviation cyber-physical systems — live dataset overview",
    pill_text=(st.session_state["gat_active_file"] if stage == "unlocked" else f"Schema {SCHEMA_VERSION}"),
)

# ---- Toolbar styling ----------------------------------------------------
# The anchor div lets us target "the stHorizontalBlock that comes right
# after this marker" with CSS, which is how the toolbar gets pinned to the
# top of the viewport (position: sticky) and kept visually distinct from
# the rest of the page, without needing a custom Streamlit component.
st.markdown(
    f"""
    <style>
    #gat-toolbar-anchor + div [data-testid="stHorizontalBlock"] {{
        position: sticky;
        top: 0;
        z-index: 999;
        background: {COLORS.get('bg_elevated', 'var(--secondary-background-color)')};
        border: 1px solid {COLORS.get('border', 'rgba(128,128,128,0.25)')};
        border-radius: 12px;
        padding: 10px 14px;
        margin: 8px 0 20px 0;
        align-items: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.15);
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }}
    #gat-toolbar-anchor + div [data-testid="stFileUploader"] {{
        padding: 0 !important;
    }}
    #gat-toolbar-anchor + div [data-testid="stFileUploaderDropzone"] {{
        min-height: 0 !important;
        padding: 8px 16px !important;
        min-width: 190px;
        border-style: dashed !important;
        transition: border-color 0.2s ease, background 0.2s ease;
    }}
    #gat-toolbar-anchor + div [data-testid="stFileUploaderDropzoneInstructions"] {{
        display: none !important;
    }}
    #gat-toolbar-anchor + div div[data-testid="stVerticalBlock"] {{
        gap: 0.25rem;
    }}
    #gat-toolbar-anchor + div [data-testid="stFileUploaderDropzone"] button,
    #gat-toolbar-anchor + div [data-testid="stFileUploaderDropzone"] button p {{
        white-space: nowrap !important;
        overflow: visible !important;
    }}
    #gat-toolbar-anchor + div [data-testid="stFileUploaderDropzone"] button {{
        min-width: 150px;
        padding: 0.5rem 1.1rem !important;
        transition: filter 0.15s ease, transform 0.05s ease;
    }}
    #gat-toolbar-anchor + div [data-testid="stFileUploaderDropzone"] button:hover {{
        filter: brightness(1.12);
    }}
    #gat-toolbar-anchor + div button:disabled {{
        opacity: 0.45 !important;
        cursor: not-allowed !important;
    }}
    #gat-toolbar-anchor + div button:not(:disabled):hover {{
        filter: brightness(1.1);
    }}
    #gat-toolbar-anchor + div button:not(:disabled):active {{
        transform: translateY(1px);
    }}
    </style>
    <div id="gat-toolbar-anchor"></div>
    """,
    unsafe_allow_html=True,
)
relabel_upload_buttons()

# ---- Toolbar --------------------------------------------------------------
tb_browse, tb_info, tb_upload, tb_change, tb_discard, tb_status = st.columns(
    [2.2, 2.4, 1, 1, 1, 2]
)

# The Select File control is "live" (a real file_uploader) whenever the user
# is allowed to pick a new file: while locked, while a file is staged but
# not yet committed, or while in "Change" mode after a dataset is already
# active.
browsing_enabled = (stage in ("locked", "staged")) or (stage == "unlocked" and st.session_state["gat_change_mode"])
in_change_mode = stage == "unlocked" and st.session_state["gat_change_mode"]

staged_file = None
with tb_browse:
    if browsing_enabled:
        raw_file = st.file_uploader(
            "Select File", type=["csv"], label_visibility="collapsed",
            key=f"gat_toolbar_uploader_{st.session_state['gat_uploader_key']}",
            help="Accepted format: .csv",
        )
        # type=["csv"] already restricts the OS picker, but a renamed file
        # could still slip through — double-check the extension defensively.
        if raw_file is not None and not raw_file.name.lower().endswith(".csv"):
            st.session_state["gat_status_msg"] = (
                "error", "Only CSV files are supported. Please select a .csv file.")
            staged_file = None
        else:
            staged_file = raw_file
    else:
        st.button("📁 Select File", disabled=True, use_container_width=True,
                   help="Use Change to select a replacement file")

with tb_info:
    if stage == "locked" and staged_file is None:
        st.caption("Please select and upload a CSV file to continue.")
    elif staged_file is not None and stage != "unlocked":
        size_kb = staged_file.size / 1024
        size_label = f"{size_kb/1024:.2f} MB" if size_kb > 1024 else f"{size_kb:.1f} KB"
        st.markdown(f"📄 **{staged_file.name}** &nbsp;·&nbsp; {size_label} &nbsp;·&nbsp; "
                    f"<span style='color:{COLORS['text_faint']}'>not yet uploaded</span>",
                    unsafe_allow_html=True)
    elif in_change_mode:
        if staged_file is not None:
            size_kb = staged_file.size / 1024
            size_label = f"{size_kb/1024:.2f} MB" if size_kb > 1024 else f"{size_kb:.1f} KB"
            dup_note = ("same name as active file — uploading will refresh it"
                        if staged_file.name == st.session_state["gat_active_file"]
                        else "replacement staged, not yet uploaded")
            st.markdown(f"📄 **{staged_file.name}** &nbsp;·&nbsp; {size_label} &nbsp;·&nbsp; "
                        f"<span style='color:{COLORS['text_faint']}'>{dup_note}</span>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"Current: **{st.session_state['gat_active_file']}** &nbsp;·&nbsp; "
                        f"<span style='color:{COLORS['text_faint']}'>select a replacement file</span>",
                        unsafe_allow_html=True)
    elif stage == "unlocked":
        row_count = st.session_state["gat_validation_summary"]["row_count"] if st.session_state["gat_validation_summary"] else 0
        st.markdown(f"📄 **{st.session_state['gat_active_file']}** &nbsp;·&nbsp; "
                    f"<span style='color:{COLORS['text_faint']}'>active dataset · {row_count:,} rows</span>",
                    unsafe_allow_html=True)

with tb_upload:
    upload_disabled = staged_file is None
    if st.button("⬆ Upload", type=("primary" if not upload_disabled else "secondary"),
                 use_container_width=True, disabled=upload_disabled,
                 help="Select a CSV file first" if upload_disabled else "Upload the selected file"):
        with st.spinner("Validating and uploading dataset…"):
            ok, df, summary, errors = load_and_validate_csv(staged_file)
        if not ok:
            # FIX #2: a failed upload — whether it's the very first upload or
            # a Change on top of an already-valid dataset — always fully
            # clears any previously active dataset. The dashboard is never
            # allowed to keep showing an older file's data once a different
            # file has been submitted; only this new file's errors are shown.
            st.session_state["gat_dataset"] = None
            st.session_state["gat_validation_summary"] = None
            st.session_state["gat_active_file"] = None
            st.session_state["gat_stage"] = "locked"
            st.session_state["gat_change_mode"] = False
            st.session_state["gat_uploader_key"] += 1
            st.session_state["gat_invalid_errors"] = errors
            st.session_state["gat_invalid_filename"] = staged_file.name
            st.session_state["gat_show_success_popup"] = False
            st.session_state["gat_status_msg"] = (
                "error", "This file could not be analyzed — see the validation details below.")
            st.rerun()
        else:
            # Replace the active dataset only now that validation passed.
            st.session_state["gat_dataset"] = df
            st.session_state["gat_validation_summary"] = summary
            st.session_state["gat_active_file"] = staged_file.name
            st.session_state["gat_stage"] = "unlocked"
            st.session_state["gat_change_mode"] = False
            st.session_state["gat_uploader_key"] += 1
            st.session_state["gat_invalid_errors"] = None
            st.session_state["gat_invalid_filename"] = None
            st.session_state["gat_status_msg"] = ("success", "🟢 Dataset Loaded")
            # FIX #1: one-shot flag, consumed on the very next render below —
            # guarantees the popup appears exactly once, right after this
            # successful upload, and never on validation failures.
            st.session_state["gat_show_success_popup"] = True
            st.rerun()

with tb_change:
    change_disabled = (stage != "unlocked") or in_change_mode
    if st.button("🔁 Change", use_container_width=True, disabled=change_disabled,
                 help="Select a different dataset file"):
        st.session_state["gat_change_mode"] = True
        st.session_state["gat_uploader_key"] += 1
        st.session_state["gat_status_msg"] = None
        st.rerun()

with tb_discard:
    if in_change_mode:
        # Changing an already-uploaded dataset: Discard only cancels the
        # staged replacement file (or exits Change mode) — it must NOT wipe
        # out the already-active dataset or send the user back to locked.
        if st.button("🗑 Discard", use_container_width=True,
                     help="Discard the selected replacement file"):
            st.session_state["gat_change_mode"] = False
            st.session_state["gat_uploader_key"] += 1
            st.session_state["gat_status_msg"] = ("info", "Selected file discarded. Your active dataset is unchanged.")
            st.rerun()
    elif stage == "unlocked":
        # A dataset is active and nothing is staged. Discard here must never
        # remove the active dataset — there is simply nothing pending to
        # discard, so this is a safe no-op with a clarifying message.
        if st.button("🗑 Discard", use_container_width=True,
                     help="No pending selection to discard"):
            st.session_state["gat_status_msg"] = ("info", "Nothing to discard — your dataset is still active.")
            st.rerun()
    else:
        discard_disabled = (stage == "locked" and staged_file is None)
        if st.button("🗑 Discard", use_container_width=True, disabled=discard_disabled,
                     help="Clear the current selection"):
            st.session_state["gat_stage"] = "locked"
            st.session_state["gat_active_file"] = None
            st.session_state["gat_change_mode"] = False
            st.session_state["gat_uploader_key"] += 1
            st.session_state["gat_invalid_errors"] = None
            st.session_state["gat_invalid_filename"] = None
            st.session_state["gat_status_msg"] = ("info", "Selected file discarded.")
            st.rerun()
            # Note: gat_dataset / gat_validation_summary are never touched
            # here — this branch only runs while stage == "locked", i.e.
            # before any dataset has ever been committed.

with tb_status:
    kind_text = st.session_state.get("gat_status_msg")
    if kind_text:
        kind, text = kind_text
        if kind == "success":
            st.success(text, icon="✅")
        elif kind == "info":
            st.info(text, icon="ℹ️")
        elif kind == "error":
            st.error(text, icon="⚠️")
        # One-shot: clear it now so it doesn't linger indefinitely in this
        # persistent toolbar (mirrors "disappears after a few seconds").
        st.session_state["gat_status_msg"] = None
    elif stage == "unlocked":
        st.success("🟢 Dataset Loaded", icon="✅")
    else:
        st.caption("⏳ Awaiting upload")

# ---- FIX #1: one-shot success popup, consumed immediately so it never
# reappears on subsequent reruns triggered by unrelated interactions. -------
if st.session_state.get("gat_show_success_popup"):
    render_success_popup("Dataset uploaded successfully.")
    st.session_state["gat_show_success_popup"] = False

# ---- Dashboard: fully locked until a dataset has been uploaded AND passed
# validation. If the most recently uploaded file was rejected, show its
# validation errors instead of a generic message (FIX #2) — never the old
# dataset's dashboard. ---------------------------------------------------
if stage != "unlocked" or st.session_state["gat_dataset"] is None:
    if st.session_state.get("gat_invalid_errors"):
        render_validation_errors_panel(
            st.session_state.get("gat_invalid_filename") or "the uploaded file",
            st.session_state["gat_invalid_errors"],
        )
    else:
        st.info("No dataset uploaded yet. Please upload a CSV file to begin.")
    st.stop()

# ---- Everything below only renders once a validated CSV is active ----------
df = st.session_state["gat_dataset"]
summary = st.session_state["gat_validation_summary"]
sidebar_status_footer(df, filename=st.session_state.get("gat_active_file"))

render_validation_summary(summary)
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ---- Derived fields ----------------------------------------------------
has_status = "status" in df.columns
has_carbon = "carbon_gco2" in df.columns
has_flight_phase = "flight_phase" in df.columns
has_timestamp = "timestamp" in df.columns and df["timestamp"].notna().any()
has_mandatory = "mandatory" in df.columns
has_avg_power = "avg_power_w" in df.columns

energy_kwh_series = df["software_energy_wh"] / 1000.0
carbon_kg_series = (df["carbon_gco2"] / 1000.0) if has_carbon else (energy_kwh_series * CARBON_INTENSITY_G_PER_KWH / 1000.0)

# ---- Top KPI row -----------------------------------------------------------
total_scenarios = df["scenario_id"].nunique()
total_runs = len(df)
total_energy_kwh = float(energy_kwh_series.sum(skipna=True))
total_carbon_kg = float(carbon_kg_series.sum(skipna=True))

if has_status:
    status_counts = df["status"].value_counts()
    clean_runs = int(status_counts.get("Clean", 0))
else:
    status_counts = pd.Series(dtype=int)
    clean_runs = None

mandatory_tests = int(df.loc[df["mandatory"].astype(bool), "scenario_id"].nunique()) if has_mandatory else None

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: metric_card("Total Scenarios", fmt_num(total_scenarios), accent=COLORS["accent2"])
with c2: metric_card("Total Runs", fmt_num(total_runs), accent=COLORS["accent"])
with c3:
    metric_card("Clean Runs", fmt_num(clean_runs) if clean_runs is not None else "N/A",
                (f"{100*clean_runs/total_runs:.1f}% of runs" if clean_runs is not None and total_runs else None),
                accent=COLORS["accent"])
with c4:
    metric_card("Mandatory Tests", fmt_num(mandatory_tests) if mandatory_tests is not None else "N/A",
                (f"{100*mandatory_tests/total_scenarios:.1f}% of catalog"
                 if mandatory_tests is not None and total_scenarios else None),
                accent=COLORS["amber"])
with c5: metric_card("Software Energy", f"{total_energy_kwh:.2f} kWh", "Σ across all runs", accent=COLORS["accent2"])
with c6:
    carbon_note = f"@ {int(CARBON_INTENSITY_G_PER_KWH)} gCO₂/kWh" if not has_carbon else "from CSV carbon column"
    metric_card("Carbon Emissions", f"{total_carbon_kg:.2f} kg CO₂e", carbon_note, accent=COLORS["danger"])

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Failed Runs", fmt_num(int(status_counts.get("Failed", 0))) if has_status else "N/A",
                accent=COLORS["danger"])
with c2:
    metric_card("Timeout Runs", fmt_num(int(status_counts.get("Timeout", 0))) if has_status else "N/A",
                accent=COLORS["amber"])
with c3:
    metric_card("Crashed Runs", fmt_num(int(status_counts.get("Crashed", 0))) if has_status else "N/A",
                accent=COLORS["purple"])
with c4:
    metric_card("Hardware Energy", "Pending / Not Connected", "awaiting sensor integration", accent=COLORS["text_faint"])

# ---- Charts -----------------------------------------------------------------
section_title("Suite Health", tag="from upload")
cc1, cc2 = st.columns([1, 1.4])

with cc1:
    if has_status and len(status_counts):
        donut = go.Figure(data=[go.Pie(
            labels=status_counts.index, values=status_counts.values, hole=0.62,
            marker=dict(colors=CHART_COLORS["pie"]),
            textinfo="label+percent", sort=False,
        )])
        donut.update_layout(title="Run Status Breakdown", showlegend=False)
        st.plotly_chart(apply_plotly_theme(donut, 330), use_container_width=True, config={"displaylogo": False})
    else:
        st.info("No `status` column in the uploaded CSV — status breakdown isn't available for this dataset.")

with cc2:
    if has_flight_phase:
        phase_energy = df.groupby("flight_phase")["software_energy_wh"].sum().sort_values(ascending=True) / 1000.0
        bar = go.Figure(go.Bar(
            x=phase_energy.values, y=phase_energy.index, orientation="h",
            marker=dict(color=CHART_COLORS["bar"]),
        ))
        bar.update_layout(title="Software Energy by Flight Phase (kWh)")
        st.plotly_chart(apply_plotly_theme(bar, 330), use_container_width=True, config={"displaylogo": False})
    else:
        top_scn = df.groupby("scenario_id")["software_energy_wh"].sum().sort_values(ascending=False).head(15) / 1000.0
        bar = go.Figure(go.Bar(
            x=top_scn.values[::-1], y=top_scn.index[::-1], orientation="h",
            marker=dict(color=CHART_COLORS["bar"]),
        ))
        bar.update_layout(title="Top 15 Scenarios by Software Energy (kWh)")
        st.plotly_chart(apply_plotly_theme(bar, 330), use_container_width=True, config={"displaylogo": False})

section_title("Test Volume Over Time", tag=f"{len(df):,} rows")
tv1, tv2 = st.columns(2)

with tv1:
    if has_timestamp:
        runs_by_hour = df.dropna(subset=["timestamp"]).set_index("timestamp").resample("h").size().rename("runs")
        area = go.Figure(go.Scatter(
            x=runs_by_hour.index, y=runs_by_hour.values, fill="tozeroy",
            line=dict(color=CHART_COLORS["line"], width=2), fillcolor=CHART_COLORS["area_fill"],
        ))
        area.update_layout(title="Runs Executed Per Hour")
        st.plotly_chart(apply_plotly_theme(area, 260), use_container_width=True, config={"displaylogo": False})
    else:
        st.info("No `timestamp` column in the uploaded CSV — the runs-over-time chart isn't available.")

with tv2:
    if has_timestamp:
        energy_by_hour = df.dropna(subset=["timestamp"]).set_index("timestamp").resample("h")["software_energy_wh"].sum() / 1000.0
        energy_area = go.Figure(go.Scatter(
            x=energy_by_hour.index, y=energy_by_hour.values, fill="tozeroy",
            line=dict(color=CHART_COLORS["bar"], width=2), fillcolor=CHART_COLORS["area_fill"],
        ))
        energy_area.update_layout(title="Software Energy Consumed Per Hour (kWh)")
        st.plotly_chart(apply_plotly_theme(energy_area, 260), use_container_width=True, config={"displaylogo": False})
    else:
        st.info("No `timestamp` column in the uploaded CSV — the energy-over-time chart isn't available.")

# ---- Recent activity --------------------------------------------------------
section_title("Recent Runs")
display_cols = [c for c in ["run_id", "test_id", "scenario_id", "status", "runtime_s",
                             "software_energy_wh", "avg_power_w", "timestamp"] if c in df.columns]
recent = (df.sort_values("timestamp", ascending=False) if has_timestamp else df).head(10)[display_cols].copy()

col_config = {}
if "runtime_s" in recent.columns:
    col_config["runtime_s"] = st.column_config.NumberColumn("runtime_s", format="%.1f")
if "software_energy_wh" in recent.columns:
    col_config["software_energy_wh"] = st.column_config.NumberColumn("software_energy_wh", format="%.1f")
if "avg_power_w" in recent.columns:
    col_config["avg_power_w"] = st.column_config.NumberColumn("avg_power_w", format="%.1f")

st.dataframe(
    recent,
    use_container_width=True,
    height=380,
    hide_index=True,
    column_config=col_config,
)

st.markdown(
    f"""<div class="gat-footer-note">
    GreenAeroTester dashboard · driven entirely by the uploaded CSV (<code>{st.session_state['gat_active_file']}</code>,
    {summary['row_count']:,} rows) · upload a different CSV at any time to refresh every card, chart, and table.
    </div>""",
    unsafe_allow_html=True,
)