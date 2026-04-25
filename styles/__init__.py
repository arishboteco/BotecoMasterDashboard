"""Boteco Dashboard CSS — split from styles.py for maintainability.

Public API: get_css() and get_login_css() — used by app.py and auth.py.
Internal layout: one module per concern (tokens, base, components, sidebar,
animations, responsive, print, fonts, login). Section ordering preserved
byte-for-byte from the original styles.py to avoid CSS cascade regressions.
"""

from __future__ import annotations

from . import (
    _fonts,
    _tokens,
    _base,
    _components,
    _sidebar,
    _animations,
    _responsive,
    _print,
    _login,
)


def get_css() -> str:
    """Return the complete CSS stylesheet for the main dashboard."""
    parts: list[str] = [
        "\n<style>\n",
        _fonts.FONTS,
        _tokens.TOKEN_SYSTEM,
        _base.BASE_TYPOGRAPHY,
        _base.BRANDED_HEADER,
        _components.BUTTON_SYSTEM,
        _components.KPI_METRIC_VALUES,
        _components.COMPACT_KPIS_FOR_REPORT_TAB,
        _components.METRIC_CARDS_CONTAINERS,
        _components.ALERT_STATUS_BOXES,
        _components.UPLOAD_ZONE,
        _components.DATA_TABLES,
        _components.EXPANDER_LABELS,
        _sidebar.SIDEBAR,
        _components.DATE_NAVIGATION,
        _components.WHATSAPP_SHARE_BUTTONS,
        _components.ICON_ONLY_ACTION_BUTTONS,
        _components.UPLOAD_ZONE_STYLING,
        _components.SECTION_DIVIDERS,
        _base.LAYOUT_SPACING,
        _base.INLINE_HTML_UTILITIES,
        _base.SCROLLBAR_STYLING,
        _base.FOCUS_RINGS,
        _components.SECTION_LABELS,
        _components.WORKFLOW_AND_SURFACES,
        _components.EMPTY_STATE,
        _sidebar.SIDEBAR_IMPROVEMENTS,
        _components.TABLE_COMPACT_STYLING,
        _animations.LOADING_SKELETON,
        _responsive.TOUCH_TARGET_IMPROVEMENTS,
        _responsive.RESPONSIVE_BREAKPOINTS,
        _components.REDUCE_VERTICAL_WHITESPACE_FOR_REPORT_TAB,
        _responsive.MOBILE_TOUCH_IMPROVEMENTS,
        _responsive.RESPONSIVE_PLOTLY_HEIGHT,
        _animations.PAGE_LOAD_ANIMATIONS,
        _animations.REDUCED_MOTION_DISABLE_ALL_ANIMATIONS,
        _base.SUBTLE_BACKGROUND_TEXTURE,
        _sidebar.SIDEBAR_GRADIENT_REFINEMENT,
        _base.SECTION_HEADERS_REFINED_STYLING,
        _base.TAB_BAR_REFINEMENT,
        _components.IMPROVED_FORM_INPUTS,
        _components.DATAFRAME_REFINEMENT,
        _components.CRITICAL_ALERT,
        _print.PRINT_STYLES,
        _base.COMPREHENSIVE_FOCUS_INDICATORS,
        "</style>\n",
    ]
    return "".join(parts)


def get_login_css() -> str:
    """Return CSS specific to the login/setup pages. Reuses token system."""
    return _login.LOGIN_CSS
