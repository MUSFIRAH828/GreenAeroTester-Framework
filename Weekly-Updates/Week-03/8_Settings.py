"""
pages/8_Settings.py
====================
Dashboard settings: theme (Dark/Light), chart color presets, full custom
color pickers, and chart-type selection — all persisted in
``st.session_state`` via utils.theme, with live previews rendered through
utils.charts against the shared dataset from utils.load_data.

Save behavior
-------------
Dark/Light applies immediately (unchanged). Chart Palette and Chart Type
edits are DRAFT-only: they only update the "Live Preview" below while you
edit them. Nothing else in the app (Home, and anywhere else that calls
utils.charts / get_chart_colors()) changes until you press "Save Changes".
"Discard Changes" throws the draft away and snaps back to what's saved.
"""

import streamlit as st
from utils.theme import apply_theme, get_theme_colors

apply_theme()
from utils.theme import (
    apply_theme, get_theme_colors, get_chart_colors, get_chart_type,
    set_theme, set_chart_preset, set_custom_chart_color, set_chart_type,
    reset_to_defaults, CHART_PRESETS, CHART_PRESET_NAMES, TREND_CHART_TYPES,
    CATEGORY_CHART_TYPES, CUSTOM_COLOR_KEYS, init_session_defaults,
    # draft API — everything below only touches the draft, not the saved settings
    get_draft_chart_colors, get_draft_chart_type, set_draft_chart_preset,
    set_draft_custom_chart_color, set_draft_chart_type,
    has_unsaved_chart_changes, save_chart_settings, discard_chart_draft,
)
from utils.load_data import load_dataset, get_baseline_data
from utils.charts import (
    chart_status_distribution, chart_flight_phase_distribution,
    chart_mandatory_vs_optional, chart_energy_over_time, chart_carbon_analytics,
    chart_priority_chart, chart_assurance_distribution, chart_carbon_by_fault_type,
    chart_runtime_trend, chart_cpu_usage_trend, chart_memory_usage_trend,
    chart_energy_distribution, chart_baseline_comparison,
    chart_hw_sw_energy_by_phase, chart_hw_sw_energy_trend, chart_hw_sw_avg_power,
    chart_hw_sw_energy_distribution,
    # newly added for full page coverage
    chart_home_status_donut, chart_home_energy_by_phase, chart_home_runs_over_time,
    chart_weather_condition_mix, chart_fault_type_distribution, chart_safety_level_distribution,
    chart_hw_sw_diff_trend, chart_hw_sw_accuracy_scatter,
    chart_baseline_energy_carbon_grouped, chart_highlight_bar, chart_single_series_bar,
)

st.set_page_config(page_title="GreenAeroTester — Settings", page_icon="⚙️",
                    layout="wide", initial_sidebar_state="expanded")
init_session_defaults()
apply_theme()

colors_theme = get_theme_colors()
unsaved = has_unsaved_chart_changes()

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
    st.markdown(
        f'<div class="gat-sidebar-status"><span class="gat-dot"></span>'
        f'Theme: {st.session_state["gat_theme"]} · Palette: {st.session_state["gat_chart_preset"]}'
        f'{" · Unsaved edits" if unsaved else ""}</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
    <div class="gat-header">
        <div>
            <div class="gat-eyebrow">CONFIGURATION</div>
            <div class="gat-title">Dashboard Settings</div>
            <div class="gat-subtitle">Theme applies instantly. Chart palette / chart type are drafts — press Save to apply them everywhere.</div>
        </div>
        <div class="gat-pill">{""}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Save bar — right-aligned, only visible when there's something to save.
if unsaved:
    sp, sb1, sb2 = st.columns([5, 1, 1])
    with sp:
        st.caption("You have unsaved palette/chart-type edits. The Live Preview below already "
                   "reflects them, but Home and every other page still show the last **saved** version "
                   "until you press Save.")
    with sb1:
        if st.button("💾 Save Changes", use_container_width=True, type="primary", key="save_top"):
            save_chart_settings()
            st.rerun()
    with sb2:
        if st.button("↩ Discard", use_container_width=True, key="discard_top"):
            discard_chart_draft()
            st.rerun()
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

df = load_dataset()

# ===========================================================================
# Theme  (applies immediately — not part of the draft/save system)
# ===========================================================================
st.markdown('<div class="gat-section-title">Theme <span class="tag">dark / light · applies instantly</span></div>',
            unsafe_allow_html=True)

tc1, tc2, tc3 = st.columns([1, 1, 2])
with tc1:
    if st.button("🌙 Dark Mode", use_container_width=True,
                  type="primary" if st.session_state["gat_theme"] == "Dark" else "secondary"):
        set_theme("Dark")
        st.rerun()
with tc2:
    if st.button("☀️ Light Mode", use_container_width=True,
                  type="primary" if st.session_state["gat_theme"] == "Light" else "secondary"):
        set_theme("Light")
        st.rerun()
with tc3:
    st.caption("")

swatch_html = "".join(
    f'<div class="gat-swatch"><span class="chip" style="background:{v}"></span>{k}</div>'
    for k, v in colors_theme.items() if k not in ("bg_grad", "plotly_template")
)
st.markdown(f'<div class="gat-swatch-row">{swatch_html}</div>', unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ===========================================================================
# Chart palette  (DRAFT — needs Save to take effect elsewhere)
# ===========================================================================
st.markdown('<div class="gat-section-title">Chart Palette '
            '<span class="tag">presets + custom · draft, needs Save</span></div>',
            unsafe_allow_html=True)

draft_preset = st.session_state["gat_draft_chart_preset"]
preset = st.selectbox(
    "Palette preset", CHART_PRESET_NAMES,
    index=CHART_PRESET_NAMES.index(draft_preset),
    help="Choose a ready-made palette, or select Custom to pick every chart color yourself. "
         "This edits the draft — a Save Changes button will appear at the top once you have edits.",
)
if preset != draft_preset:
    set_draft_chart_preset(preset)
    st.rerun()

if preset != "Custom":
    p = CHART_PRESETS[preset]
    preview_html = "".join(
        f'<div class="gat-swatch"><span class="chip" style="background:{c}"></span></div>'
        for c in [p["bar"], p["line"]] + p["pie"]
    )
    st.markdown(f'<div class="gat-swatch-row">{preview_html}</div>', unsafe_allow_html=True)
else:
    st.caption("Custom mode — pick a color for every chart element below. "
               "**Area fill** takes an `rgba(r,g,b,alpha)` string (needs transparency, "
               "so it's a text box rather than a swatch); **Pie slice 1-6** are the six colors "
               "used for pie/donut charts like Run Status or Flight Phase.")
    custom = st.session_state["gat_draft_custom_chart_colors"]
    labels = {
        "bar": "Bar color", "line": "Line color", "area_fill": "Area fill (rgba string)",
        "pie_1": "Pie slice 1", "pie_2": "Pie slice 2", "pie_3": "Pie slice 3",
        "pie_4": "Pie slice 4", "pie_5": "Pie slice 5", "pie_6": "Pie slice 6",
        "background": "Chart background", "grid": "Grid lines", "title": "Chart title",
        "axis_label": "Axis labels", "legend": "Legend text", "text": "General text",
    }
    cols = st.columns(5)
    for i, key in enumerate(CUSTOM_COLOR_KEYS):
        with cols[i % 5]:
            if key == "area_fill":
                new_val = st.text_input(labels[key], value=custom[key], key=f"draft_custom_{key}")
            else:
                new_val = st.color_picker(labels[key], value=custom[key], key=f"draft_custom_{key}")
            if new_val != custom[key]:
                set_draft_custom_chart_color(key, new_val)
                st.rerun()

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ===========================================================================
# Chart type  (DRAFT — needs Save to take effect elsewhere)
# ===========================================================================
st.markdown('<div class="gat-section-title">Chart Type '
            '<span class="tag">applied where compatible · draft, needs Save</span></div>',
            unsafe_allow_html=True)

ctc1, ctc2 = st.columns(2)
with ctc1:
    draft_trend_type = st.session_state["gat_draft_trend_chart_type"]
    trend_type = st.selectbox(
        "Trend & numeric charts (energy, carbon, runtime, CPU, memory)",
        TREND_CHART_TYPES, index=TREND_CHART_TYPES.index(draft_trend_type),
    )
    if trend_type != draft_trend_type:
        set_draft_chart_type("trend", trend_type)
        st.rerun()
with ctc2:
    draft_category_type = st.session_state["gat_draft_category_chart_type"]
    category_type = st.selectbox(
        "Category charts (status, flight phase, mandatory vs optional)",
        CATEGORY_CHART_TYPES, index=CATEGORY_CHART_TYPES.index(draft_category_type),
    )
    if category_type != draft_category_type:
        set_draft_chart_type("category", category_type)
        st.rerun()

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ===========================================================================
# Live preview — reflects the DRAFT (unsaved) palette/chart-type so you can
# see the effect before committing it. Includes every chart utils/charts.py
# knows how to build.
# ===========================================================================
st.markdown('<div class="gat-section-title">Live Preview '
            '<span class="tag">shared dataset · shows your draft</span></div>',
            unsafe_allow_html=True)

preview_colors = get_draft_chart_colors()
preview_trend_type = get_draft_chart_type("trend")
preview_category_type = get_draft_chart_type("category")
baseline = get_baseline_data(df)

pv1, pv2 = st.columns(2)
with pv1:
    st.plotly_chart(chart_status_distribution(df, chart_type=preview_category_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with pv2:
    st.plotly_chart(chart_flight_phase_distribution(df, chart_type=preview_category_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
st.markdown('<div class="gat-section-title">Home Page Charts</div>', unsafe_allow_html=True)
hpv1, hpv2, hpv3 = st.columns(3)
with hpv1:
    st.plotly_chart(chart_home_status_donut(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with hpv2:
    st.plotly_chart(chart_home_energy_by_phase(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with hpv3:
    st.plotly_chart(chart_home_runs_over_time(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
st.markdown('<div class="gat-section-title">Dataset Overview Charts</div>', unsafe_allow_html=True)
dpv1, dpv2, dpv3 = st.columns(3)
with dpv1:
    st.plotly_chart(chart_weather_condition_mix(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with dpv2:
    st.plotly_chart(chart_fault_type_distribution(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with dpv3:
    st.plotly_chart(chart_safety_level_distribution(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})    
pv3, pv4 = st.columns(2)
with pv3:
    st.plotly_chart(chart_mandatory_vs_optional(df, chart_type=preview_category_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with pv4:
    st.plotly_chart(chart_assurance_distribution(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})

pv5, pv6 = st.columns(2)
with pv5:
    st.plotly_chart(chart_energy_over_time(df, chart_type=preview_trend_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with pv6:
    st.plotly_chart(chart_carbon_analytics(df, chart_type=preview_trend_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})

pv7, pv8 = st.columns(2)
with pv7:
    st.plotly_chart(chart_runtime_trend(df, chart_type=preview_trend_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with pv8:
    st.plotly_chart(chart_cpu_usage_trend(df, chart_type=preview_trend_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})

pv9, pv10 = st.columns(2)
with pv9:
    st.plotly_chart(chart_memory_usage_trend(df, chart_type=preview_trend_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with pv10:
    st.plotly_chart(chart_energy_distribution(df, chart_type=preview_trend_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})

pv11, pv12 = st.columns(2)
with pv11:
    st.plotly_chart(chart_carbon_by_fault_type(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with pv12:
    st.plotly_chart(chart_priority_chart(baseline, "assurance_retained_pct",
                                          chart_type=preview_trend_type, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})

st.plotly_chart(chart_baseline_comparison(baseline, colors=preview_colors),
                 use_container_width=True, config={"displaylogo": False})

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
st.markdown('<div class="gat-section-title">Software vs Hardware '
            '<span class="tag">simulated — see note below</span></div>',
            unsafe_allow_html=True)
st.caption("No physical power meter is wired in yet (SRS §8), so 'Hardware' here is a deterministic, "
           "seeded simulation of what a meter would likely read, built the same way as the Energy page's "
           "own simulation — but computed against the full shared dataset rather than the Energy page's "
           "filtered view, so exact numbers may differ slightly from that page.")

hw1, hw2 = st.columns(2)
with hw1:
    st.plotly_chart(chart_hw_sw_energy_by_phase(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with hw2:
    st.plotly_chart(chart_hw_sw_energy_trend(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})

hw3, hw4 = st.columns(2)
with hw3:
    st.plotly_chart(chart_hw_sw_avg_power(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with hw4:
    st.plotly_chart(chart_hw_sw_energy_distribution(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
hw5, hw6 = st.columns(2)
with hw5:
    st.plotly_chart(chart_hw_sw_diff_trend(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
    winner_method = baseline.sort_values("assurance_retained_pct", ascending=False).iloc[0]["method"]
highlighted = [m == winner_method for m in baseline["method"]]

bpv1, bpv2 = st.columns(2)
with bpv1:
    st.plotly_chart(
        chart_highlight_bar(baseline["method"].tolist(), baseline["assurance_retained_pct"].tolist(),
                             highlighted, "Assurance Retained (%)", colors=preview_colors),
        use_container_width=True, config={"displaylogo": False})
with bpv2:
    st.plotly_chart(
        chart_single_series_bar(baseline["method"].tolist(), baseline["energy_saved_pct"].tolist(),
                                 "Energy Saved vs Full Suite (%)", color_key="line", colors=preview_colors),
        use_container_width=True, config={"displaylogo": False})

bpv3, bpv4 = st.columns(2)
with bpv3:
    st.plotly_chart(chart_baseline_energy_carbon_grouped(baseline, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
with bpv4:
    st.plotly_chart(
        chart_single_series_bar(baseline["method"].tolist(), baseline["runtime_saved_pct"].tolist(),
                                 "Runtime Saved vs Full Suite (%)", color_key="bar", colors=preview_colors),
        use_container_width=True, config={"displaylogo": False})
with hw6:
    st.plotly_chart(chart_hw_sw_accuracy_scatter(df, colors=preview_colors),
                     use_container_width=True, config={"displaylogo": False})
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ===========================================================================
# Reset
# ===========================================================================
st.markdown('<div class="gat-section-title">Reset</div>', unsafe_allow_html=True)
rc1, rc2 = st.columns([1, 3])
with rc1:
    if st.button("↺ Reset to Defaults", use_container_width=True):
        reset_to_defaults()
        st.rerun()
with rc2:
    st.caption("")

