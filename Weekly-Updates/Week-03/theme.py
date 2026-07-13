"""
utils/theme.py
==============
Centralized theming and chart-color engine for GreenAeroTester.

Everything the Settings page (and any future page) needs to render a
consistent dark/light theme and a consistent chart color scheme lives here:

* Two complete color palettes (dark & light) covering background, sidebar,
  cards, tables, buttons and text — not just one or two accent colors.
* A small set of chart-color presets (Corporate, Ocean, Forest, Sunset,
  Default Emerald) plus a fully custom mode driven by color pickers.
* All of it is persisted in ``st.session_state`` so it survives page
  navigation and can later be swapped for a user-preferences backend with
  no changes to callers — every getter here reads/writes session_state
  only, never module-level globals.

Usage from a page::

    from utils.theme import apply_theme, get_chart_colors, get_chart_type

    apply_theme()                      # injects CSS for the active theme
    colors = get_chart_colors()        # dict consumed by utils/charts.py
    chart_type = get_chart_type("trend")

Adoption note
-------------
Pages 1-7 currently inject their own static, inline CSS (a deliberate
constraint of an earlier deliverable). They do not yet call
``apply_theme()``, so the dark/light toggle only affects pages that use
this module today: ``app.py`` and ``pages/8_Settings.py``. Swapping each
legacy page's ``inject_css()`` call for ``apply_theme()`` (one line) is all
that's needed to bring them onto the same theme system later.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Full UI palettes — dark and light are BOTH complete, not spot-fixes.
# ---------------------------------------------------------------------------
DARK_THEME = {
    "bg": "#0A0F1C",
    "bg_grad": "linear-gradient(160deg, #0A0F1C 0%, #0D1526 55%, #0A0F1C 100%)",
    "panel": "#111A2E",
    "panel_alt": "#0E1626",
    "border": "#1E2A45",
    "border_soft": "#182238",
    "text": "#E9EEF7",
    "text_dim": "#8C97AE",
    "text_faint": "#5C6880",
    "accent": "#34D399",
    "accent_soft": "#0F3D30",
    "accent2": "#4FA3F7",
    "amber": "#F5A623",
    "danger": "#F0555C",
    "purple": "#A78BFA",
    "grid": "#182238",
    "on_accent": "#06231A",
    "plotly_template": "plotly_dark",
}

LIGHT_THEME = {
    "bg": "#F4F6FA",
    "bg_grad": "linear-gradient(160deg, #F8FAFC 0%, #EEF2F8 55%, #F4F6FA 100%)",
    "panel": "#FFFFFF",
    "panel_alt": "#F0F3F8",
    "border": "#DCE3ED",
    "border_soft": "#E7ECF3",
    "text": "#101828",
    "text_dim": "#57647A",
    "text_faint": "#8993A6",
    "accent": "#0E9F6E",
    "accent_soft": "#DCF5EA",
    "accent2": "#2F6FCE",
    "amber": "#B4670A",
    "danger": "#C0323C",
    "purple": "#6B46C1",
    "grid": "#E3E8F0",
    "on_accent": "#FFFFFF",
    "plotly_template": "plotly_white",
}

THEMES = {"Dark": DARK_THEME, "Light": LIGHT_THEME}

# ---------------------------------------------------------------------------
# Chart color presets — each defines the "signature" colors for bars, lines,
# area fills and pie slices. Background/grid/title/axis/legend/text are
# resolved from the active UI theme automatically UNLESS the user is in
# "Custom" mode, where every one of those is picked manually.
# ---------------------------------------------------------------------------
CHART_PRESETS = {
    "Default Emerald": {
        "bar": "#34D399", "line": "#4FA3F7", "area_fill": "rgba(52,211,153,0.20)",
        "pie": ["#34D399", "#4FA3F7", "#F5A623", "#F0555C", "#A78BFA", "#22C1C3"],
    },
    "Corporate": {
        "bar": "#2C5AA0", "line": "#4472C4", "area_fill": "rgba(68,114,196,0.20)",
        "pie": ["#2C5AA0", "#4472C4", "#8FAADC", "#1F3864", "#7F9DB9", "#BDD7EE"],
    },
    "Ocean": {
        "bar": "#0FA3B1", "line": "#0077B6", "area_fill": "rgba(0,180,216,0.20)",
        "pie": ["#03045E", "#0077B6", "#00B4D8", "#90E0EF", "#48CAE4", "#0FA3B1"],
    },
    "Forest": {
        "bar": "#4C9A2A", "line": "#2E6F40", "area_fill": "rgba(76,154,42,0.20)",
        "pie": ["#1B4332", "#2D6A4F", "#40916C", "#74C69D", "#95D5B2", "#A9C46C"],
    },
    "Sunset": {
        "bar": "#F3722C", "line": "#F94144", "area_fill": "rgba(249,132,74,0.22)",
        "pie": ["#F94144", "#F3722C", "#F8961E", "#F9C74F", "#B5179E", "#7209B7"],
    },
}

CHART_PRESET_NAMES = list(CHART_PRESETS.keys()) + ["Custom"]
TREND_CHART_TYPES = ["Bar", "Line", "Area", "Scatter"]
CATEGORY_CHART_TYPES = ["Bar", "Pie", "Donut"]

# Elements a user can recolor individually in "Custom" mode.
CUSTOM_COLOR_KEYS = [
    "bar", "line", "area_fill", "pie_1", "pie_2", "pie_3", "pie_4", "pie_5", "pie_6",
    "background", "grid", "title", "axis_label", "legend", "text",
]

_STYLE_CSS_PATH = Path(__file__).resolve().parent.parent / "styles" / "style.css"


# ---------------------------------------------------------------------------
# Session-state schema & defaults
# ---------------------------------------------------------------------------
def init_session_defaults() -> None:
    """Ensures every theming/chart key exists in ``st.session_state``.

    Safe to call from any page at any time (idempotent via ``setdefault``
    semantics), so pages don't need to worry about initialization order.
    """
    st.session_state.setdefault("gat_theme", "Dark")
    st.session_state.setdefault("gat_chart_preset", "Default Emerald")
    st.session_state.setdefault("gat_trend_chart_type", "Area")
    st.session_state.setdefault("gat_category_chart_type", "Bar")

    if "gat_custom_chart_colors" not in st.session_state:
        base = CHART_PRESETS["Default Emerald"]
        theme = THEMES[st.session_state["gat_theme"]]
        st.session_state["gat_custom_chart_colors"] = {
            "bar": base["bar"], "line": base["line"], "area_fill": base["area_fill"],
            "pie_1": base["pie"][0], "pie_2": base["pie"][1], "pie_3": base["pie"][2],
            "pie_4": base["pie"][3], "pie_5": base["pie"][4], "pie_6": base["pie"][5],
            "background": theme["panel_alt"], "grid": theme["grid"], "title": theme["text"],
            "axis_label": theme["text_dim"], "legend": theme["text_dim"], "text": theme["text_dim"],
        }

    # -----------------------------------------------------------------
    # DRAFT state — everything the Settings page's chart-palette widgets
    # write to. Nothing outside this module (charts.py, app.py, pages
    # 1-7) ever reads gat_draft_*, so nothing anywhere else changes until
    # the user presses "Save Changes" on the Settings page, which copies
    # draft -> the real gat_chart_preset / gat_custom_chart_colors /
    # gat_trend_chart_type / gat_category_chart_type keys above.
    # Dark/Light (gat_theme) is intentionally NOT drafted — it applies
    # immediately, same as before.
    # -----------------------------------------------------------------
    st.session_state.setdefault("gat_draft_chart_preset", st.session_state["gat_chart_preset"])
    st.session_state.setdefault("gat_draft_trend_chart_type", st.session_state["gat_trend_chart_type"])
    st.session_state.setdefault("gat_draft_category_chart_type", st.session_state["gat_category_chart_type"])
    st.session_state.setdefault("gat_draft_custom_chart_colors",
                                 dict(st.session_state["gat_custom_chart_colors"]))


def set_theme(theme_name: str) -> None:
    """Sets the active UI theme ('Dark' or 'Light') and reruns the page."""
    init_session_defaults()
    if theme_name not in THEMES:
        raise ValueError(f"Unknown theme: {theme_name}")
    st.session_state["gat_theme"] = theme_name


def get_theme_colors() -> dict:
    """Returns the full palette dict for the currently active theme."""
    init_session_defaults()
    return THEMES[st.session_state["gat_theme"]]


def set_chart_preset(preset_name: str) -> None:
    init_session_defaults()
    if preset_name not in CHART_PRESET_NAMES:
        raise ValueError(f"Unknown chart preset: {preset_name}")
    st.session_state["gat_chart_preset"] = preset_name


def set_custom_chart_color(key: str, value: str) -> None:
    """Updates a single custom color-picker value (only used in Custom mode)."""
    init_session_defaults()
    if key not in CUSTOM_COLOR_KEYS:
        raise ValueError(f"Unknown chart color key: {key}")
    st.session_state["gat_custom_chart_colors"][key] = value


def set_chart_type(category: str, chart_type: str) -> None:
    """Sets the chart type for either 'trend' or 'category' style charts."""
    init_session_defaults()
    if category == "trend":
        if chart_type not in TREND_CHART_TYPES:
            raise ValueError(f"Unknown trend chart type: {chart_type}")
        st.session_state["gat_trend_chart_type"] = chart_type
    elif category == "category":
        if chart_type not in CATEGORY_CHART_TYPES:
            raise ValueError(f"Unknown category chart type: {chart_type}")
        st.session_state["gat_category_chart_type"] = chart_type
    else:
        raise ValueError("category must be 'trend' or 'category'")


def get_chart_type(category: str) -> str:
    init_session_defaults()
    return (st.session_state["gat_trend_chart_type"] if category == "trend"
            else st.session_state["gat_category_chart_type"])


def get_chart_colors() -> dict:
    """Resolves the active chart color scheme into a flat dict.

    Returns
    -------
    dict
        Keys: bar, line, area_fill, pie (list[6]), background, grid,
        title, axis_label, legend, text.
    """
    init_session_defaults()
    preset = st.session_state["gat_chart_preset"]
    theme = get_theme_colors()

    if preset == "Custom":
        c = st.session_state["gat_custom_chart_colors"]
        return {
            "bar": c["bar"], "line": c["line"], "area_fill": c["area_fill"],
            "pie": [c["pie_1"], c["pie_2"], c["pie_3"], c["pie_4"], c["pie_5"], c["pie_6"]],
            "background": c["background"], "grid": c["grid"], "title": c["title"],
            "axis_label": c["axis_label"], "legend": c["legend"], "text": c["text"],
        }

    p = CHART_PRESETS[preset]
    return {
        "bar": p["bar"], "line": p["line"], "area_fill": p["area_fill"], "pie": p["pie"],
        "background": "transparent", "grid": theme["grid"], "title": theme["text"],
        "axis_label": theme["text_dim"], "legend": theme["text_dim"], "text": theme["text_dim"],
    }


# ---------------------------------------------------------------------------
# DRAFT chart-palette API — used ONLY by pages/8_Settings.py widgets.
# Mirrors the "real" setters/getters above but reads/writes gat_draft_*
# instead, so edits stay local to the Settings page's own preview until
# save_chart_settings() is called.
# ---------------------------------------------------------------------------
def set_draft_chart_preset(preset_name: str) -> None:
    init_session_defaults()
    if preset_name not in CHART_PRESET_NAMES:
        raise ValueError(f"Unknown chart preset: {preset_name}")
    st.session_state["gat_draft_chart_preset"] = preset_name


def set_draft_custom_chart_color(key: str, value: str) -> None:
    init_session_defaults()
    if key not in CUSTOM_COLOR_KEYS:
        raise ValueError(f"Unknown chart color key: {key}")
    st.session_state["gat_draft_custom_chart_colors"][key] = value


def set_draft_chart_type(category: str, chart_type: str) -> None:
    init_session_defaults()
    if category == "trend":
        if chart_type not in TREND_CHART_TYPES:
            raise ValueError(f"Unknown trend chart type: {chart_type}")
        st.session_state["gat_draft_trend_chart_type"] = chart_type
    elif category == "category":
        if chart_type not in CATEGORY_CHART_TYPES:
            raise ValueError(f"Unknown category chart type: {chart_type}")
        st.session_state["gat_draft_category_chart_type"] = chart_type
    else:
        raise ValueError("category must be 'trend' or 'category'")


def get_draft_chart_type(category: str) -> str:
    init_session_defaults()
    return (st.session_state["gat_draft_trend_chart_type"] if category == "trend"
            else st.session_state["gat_draft_category_chart_type"])


def get_draft_chart_colors() -> dict:
    """Same shape as get_chart_colors(), but resolved from the DRAFT preset/
    custom colors — i.e. what the Live Preview on Settings should show,
    which may not match what's actually saved yet."""
    init_session_defaults()
    preset = st.session_state["gat_draft_chart_preset"]
    theme = get_theme_colors()

    if preset == "Custom":
        c = st.session_state["gat_draft_custom_chart_colors"]
        return {
            "bar": c["bar"], "line": c["line"], "area_fill": c["area_fill"],
            "pie": [c["pie_1"], c["pie_2"], c["pie_3"], c["pie_4"], c["pie_5"], c["pie_6"]],
            "background": c["background"], "grid": c["grid"], "title": c["title"],
            "axis_label": c["axis_label"], "legend": c["legend"], "text": c["text"],
        }

    p = CHART_PRESETS[preset]
    return {
        "bar": p["bar"], "line": p["line"], "area_fill": p["area_fill"], "pie": p["pie"],
        "background": "transparent", "grid": theme["grid"], "title": theme["text"],
        "axis_label": theme["text_dim"], "legend": theme["text_dim"], "text": theme["text_dim"],
    }


def has_unsaved_chart_changes() -> bool:
    """True while the Settings page draft differs from what's actually saved
    (i.e. what every other page/chart in the app is currently rendering with)."""
    init_session_defaults()
    return (
        st.session_state["gat_draft_chart_preset"] != st.session_state["gat_chart_preset"]
        or st.session_state["gat_draft_trend_chart_type"] != st.session_state["gat_trend_chart_type"]
        or st.session_state["gat_draft_category_chart_type"] != st.session_state["gat_category_chart_type"]
        or st.session_state["gat_draft_custom_chart_colors"] != st.session_state["gat_custom_chart_colors"]
    )


def save_chart_settings() -> None:
    """Commits the draft palette/chart-type choices. After this call,
    get_chart_colors()/get_chart_type() — which is what charts.py, app.py,
    and every page's charts actually render with — return the new values
    everywhere in the app, not just on the Settings page."""
    init_session_defaults()
    st.session_state["gat_chart_preset"] = st.session_state["gat_draft_chart_preset"]
    st.session_state["gat_trend_chart_type"] = st.session_state["gat_draft_trend_chart_type"]
    st.session_state["gat_category_chart_type"] = st.session_state["gat_draft_category_chart_type"]
    st.session_state["gat_custom_chart_colors"] = dict(st.session_state["gat_draft_custom_chart_colors"])


def discard_chart_draft() -> None:
    """Throws away unsaved edits, snapping the draft back to whatever is
    currently saved. Dark/Light is untouched since it was never drafted."""
    init_session_defaults()
    st.session_state["gat_draft_chart_preset"] = st.session_state["gat_chart_preset"]
    st.session_state["gat_draft_trend_chart_type"] = st.session_state["gat_trend_chart_type"]
    st.session_state["gat_draft_category_chart_type"] = st.session_state["gat_category_chart_type"]
    st.session_state["gat_draft_custom_chart_colors"] = dict(st.session_state["gat_custom_chart_colors"])


def reset_to_defaults() -> None:
    """Clears all GreenAeroTester session_state keys back to first-run defaults."""
    for key in list(st.session_state.keys()):
        if key.startswith("gat_"):
            del st.session_state[key]
    init_session_defaults()


# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------
def _variable_block(theme: dict) -> str:
    return f"""
    <style>
    :root {{
        --gat-bg: {theme['bg']};
        --gat-bg-grad: {theme['bg_grad']};
        --gat-panel: {theme['panel']};
        --gat-panel-alt: {theme['panel_alt']};
        --gat-border: {theme['border']};
        --gat-border-soft: {theme['border_soft']};
        --gat-text: {theme['text']};
        --gat-text-dim: {theme['text_dim']};
        --gat-text-faint: {theme['text_faint']};
        --gat-accent: {theme['accent']};
        --gat-accent-soft: {theme['accent_soft']};
        --gat-accent2: {theme['accent2']};
        --gat-amber: {theme['amber']};
        --gat-danger: {theme['danger']};
        --gat-purple: {theme['purple']};
        --gat-grid: {theme['grid']};
        --gat-on-accent: {theme['on_accent']};
    }}
    </style>
    """


def _load_style_css() -> str:
    try:
        return _STYLE_CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""  # gracefully degrade if the stylesheet isn't deployed alongside


def apply_theme() -> None:
    """Initializes defaults and injects the active theme's CSS.

    Call this once near the top of a page, after ``st.set_page_config``.
    """
    init_session_defaults()
    theme = get_theme_colors()
    st.markdown(_variable_block(theme), unsafe_allow_html=True)
    css = _load_style_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)