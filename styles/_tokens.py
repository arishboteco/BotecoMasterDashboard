"""Canonical design tokens shared by CSS, Streamlit theme config, and Python UI code.

Public exports:
  TOKEN_SYSTEM — full token block (light + dark + system-preference fallback).
  STREAMLIT_THEME_LIGHT / STREAMLIT_THEME_DARK — canonical values for `.streamlit/config.toml`.
"""

from __future__ import annotations

# ── Canonical semantic tokens (light) ─────────────────────────────────────────
COLOR_BG = "#F7FAFC"
COLOR_SURFACE = "#FFFFFF"
COLOR_SURFACE_ELEVATED = "#FFFFFF"
COLOR_TEXT_PRIMARY = "#1E293B"
COLOR_TEXT_SECONDARY = "#475569"
COLOR_TEXT_MUTED = "#64748B"
COLOR_BORDER = "#E2E8F0"
COLOR_PRIMARY = "#005AAB"
COLOR_PRIMARY_HOVER = "#004080"
COLOR_PRIMARY_SOFT = "#EBF4FF"
COLOR_SUCCESS_BG = "#F0FDF4"
COLOR_SUCCESS_TEXT = "#15803D"
COLOR_WARNING_BG = "#FFFBEB"
COLOR_WARNING_TEXT = "#B45309"
COLOR_ERROR_BG = "#FEF2F2"
COLOR_ERROR_TEXT = "#B91C1C"
COLOR_INFO_BG = "#EFF6FF"
COLOR_INFO_TEXT = "#1D4ED8"

PRIMARY = "#005AAB"
PRIMARY_DARK = "#004080"
PRIMARY_LIGHT = "#2D7AC9"
PRIMARY_SOFT = "#EBF4FF"

SURFACE = "#F7FAFC"
SURFACE_ELEVATED = "#FFFFFF"
SURFACE_RAISED = "#FFFFFF"
SURFACE_MUTED = "#EEF3F8"

TEXT = "#1E293B"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#64748B"

BORDER = "#E2E8F0"
BORDER_MEDIUM = "#CBD5E1"
BORDER_STRONG = "#94A3B8"

SUCCESS = "#15803D"
ERROR = "#B91C1C"

# ── Canonical semantic tokens (dark) ──────────────────────────────────────────
DARK_COLOR_BG = "#0F172A"
DARK_COLOR_SURFACE = "#1E293B"
DARK_COLOR_SURFACE_ELEVATED = "#334155"
DARK_COLOR_TEXT_PRIMARY = "#F1F5F9"
DARK_COLOR_TEXT_SECONDARY = "#CBD5E1"
DARK_COLOR_TEXT_MUTED = "#94A3B8"
DARK_COLOR_BORDER = "#334155"
DARK_COLOR_PRIMARY = "#2D7AC9"
DARK_COLOR_PRIMARY_HOVER = "#1F5FA8"
DARK_COLOR_PRIMARY_SOFT = "#1E3A5F"
DARK_COLOR_SUCCESS_BG = "#052E16"
DARK_COLOR_SUCCESS_TEXT = "#86EFAC"
DARK_COLOR_WARNING_BG = "#451A03"
DARK_COLOR_WARNING_TEXT = "#FCD34D"
DARK_COLOR_ERROR_BG = "#450A0A"
DARK_COLOR_ERROR_TEXT = "#FCA5A5"
DARK_COLOR_INFO_BG = "#1E1B4B"
DARK_COLOR_INFO_TEXT = "#A5B4FC"

DARK_PRIMARY = "#2D7AC9"
DARK_PRIMARY_DARK = "#1F5FA8"
DARK_PRIMARY_LIGHT = "#5A97D6"
DARK_PRIMARY_SOFT = "#1E3A5F"

DARK_SURFACE = "#0F172A"
DARK_SURFACE_ELEVATED = "#1E293B"
DARK_SURFACE_RAISED = "#334155"
DARK_SURFACE_MUTED = "#253245"

DARK_TEXT = "#F1F5F9"
DARK_TEXT_SECONDARY = "#CBD5E1"
DARK_TEXT_MUTED = "#94A3B8"

DARK_BORDER = "#334155"
DARK_BORDER_MEDIUM = "#475569"
DARK_BORDER_STRONG = "#64748B"

DARK_SUCCESS = "#86EFAC"
DARK_ERROR = "#FCA5A5"

# ── Streamlit config maps from canonical semantic tokens ──────────────────────
STREAMLIT_THEME_LIGHT = {
    "primaryColor": PRIMARY,
    "backgroundColor": SURFACE_ELEVATED,
    "secondaryBackgroundColor": SURFACE_MUTED,
    "textColor": TEXT,
    "font": "sans serif",
}

STREAMLIT_THEME_DARK = {
    "primaryColor": DARK_PRIMARY,
    "backgroundColor": DARK_SURFACE,
    "secondaryBackgroundColor": DARK_SURFACE_ELEVATED,
    "textColor": DARK_TEXT,
    "font": "sans serif",
}

TOKEN_SYSTEM = f"""
    /* ── Light mode tokens (default) ─────────────────────────── */
    :root {{
        /* Canonical semantic aliases */
        --COLOR_BG: {COLOR_BG};
        --COLOR_SURFACE: {COLOR_SURFACE};
        --COLOR_SURFACE_ELEVATED: {COLOR_SURFACE_ELEVATED};
        --COLOR_TEXT_PRIMARY: {COLOR_TEXT_PRIMARY};
        --COLOR_TEXT_SECONDARY: {COLOR_TEXT_SECONDARY};
        --COLOR_TEXT_MUTED: {COLOR_TEXT_MUTED};
        --COLOR_BORDER: {COLOR_BORDER};
        --COLOR_PRIMARY: {COLOR_PRIMARY};
        --COLOR_PRIMARY_HOVER: {COLOR_PRIMARY_HOVER};
        --COLOR_PRIMARY_SOFT: {COLOR_PRIMARY_SOFT};
        --COLOR_SUCCESS_BG: {COLOR_SUCCESS_BG};
        --COLOR_SUCCESS_TEXT: {COLOR_SUCCESS_TEXT};
        --COLOR_WARNING_BG: {COLOR_WARNING_BG};
        --COLOR_WARNING_TEXT: {COLOR_WARNING_TEXT};
        --COLOR_ERROR_BG: {COLOR_ERROR_BG};
        --COLOR_ERROR_TEXT: {COLOR_ERROR_TEXT};
        --COLOR_INFO_BG: {COLOR_INFO_BG};
        --COLOR_INFO_TEXT: {COLOR_INFO_TEXT};

        --primary: {PRIMARY};
        --surface: {SURFACE};
        --text: {TEXT};
        --border: {BORDER};
        --success: {SUCCESS};
        --error: {ERROR};

        /* Brand palette */
        --brand: #005AAB;
        --brand-dark: {PRIMARY_DARK};
        --brand-darker: #003366;
        --brand-light: {PRIMARY_LIGHT};
        --brand-soft: {PRIMARY_SOFT};

        /* Surface palette */
        --surface-elevated: {SURFACE_ELEVATED};
        --surface-raised: {SURFACE_RAISED};
        --surface-muted: {SURFACE_MUTED};
        --sidebar-bg: {PRIMARY};
        --sidebar-border: {PRIMARY_DARK};
        --table-header-bg: #EEF2F7;

        /* Text palette */
        --text-secondary: {TEXT_SECONDARY};
        --text-muted: {TEXT_MUTED};

        /* Border palette */
        --border-subtle: #E2E8F0;
        --border-medium: {BORDER_MEDIUM};
        --border-strong: {BORDER_STRONG};

        /* Accent colors */
        --accent-coral: {PRIMARY};
        --accent-teal: #54C5D0;
        --accent-amber: #FDB813;
        --accent-green: #A2D06E;
        --accent-slate: {PRIMARY};

        /* Semantic colors */
        --success-bg: #F0FDF4;
        --success-text: var(--success);
        --success-border: #BBF7D0;
        --warning-bg: #FFFBEB;
        --warning-text: #B45309;
        --warning-border: #FDE68A;
        --error-bg: #FEF2F2;
        --error-text: var(--error);
        --error-border: #FECACA;
        --info-bg: #EFF6FF;
        --info-text: #1D4ED8;
        --info-border: #BFDBFE;

        /* Typography */
        --font-display: 'Plus Jakarta Sans', sans-serif;
        --font-body: 'Inter', sans-serif;
        --font-size-xs: 12px;
        --font-size-sm: 14px;
        --font-size-base: 16px;
        --font-size-lg: 18px;

        /* Spacing scale (4px base) */
        --spacing-xs: 4px;
        --spacing-sm: 8px;
        --spacing-md: 16px;
        --spacing-lg: 24px;
        --spacing-xl: 32px;

        /* Shadows */
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.05);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);

        /* Border radius */
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;

        /* Button heights */
        --btn-height-sm: 32px;
        --btn-height-md: 40px;
        --btn-height-lg: 48px;
        --btn-padding-x: 1rem;
        --btn-padding-y: 0.5rem;

        /* Icon */
        --icon-size: 18px;

        /* Material Symbols */
        .material-symbols-outlined {{
            font-family: 'Material Symbols Outlined';
            font-weight: normal;
            font-style: normal;
            font-size: 24px;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            text-rendering: optimizeLegibility;
            font-feature-settings: 'liga';
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }}

        /* Z-index scale */
        --z-index-dropdown: 10;
        --z-index-modal: 100;
        --z-index-toast: 1000;

        /* Transitions */
        --transition-fast: 150ms;
        --transition-normal: 200ms;
    }}

    :root[data-theme="dark"] {{
        --COLOR_BG: {DARK_COLOR_BG};
        --COLOR_SURFACE: {DARK_COLOR_SURFACE};
        --COLOR_SURFACE_ELEVATED: {DARK_COLOR_SURFACE_ELEVATED};
        --COLOR_TEXT_PRIMARY: {DARK_COLOR_TEXT_PRIMARY};
        --COLOR_TEXT_SECONDARY: {DARK_COLOR_TEXT_SECONDARY};
        --COLOR_TEXT_MUTED: {DARK_COLOR_TEXT_MUTED};
        --COLOR_BORDER: {DARK_COLOR_BORDER};
        --COLOR_PRIMARY: {DARK_COLOR_PRIMARY};
        --COLOR_PRIMARY_HOVER: {DARK_COLOR_PRIMARY_HOVER};
        --COLOR_PRIMARY_SOFT: {DARK_COLOR_PRIMARY_SOFT};
        --COLOR_SUCCESS_BG: {DARK_COLOR_SUCCESS_BG};
        --COLOR_SUCCESS_TEXT: {DARK_COLOR_SUCCESS_TEXT};
        --COLOR_WARNING_BG: {DARK_COLOR_WARNING_BG};
        --COLOR_WARNING_TEXT: {DARK_COLOR_WARNING_TEXT};
        --COLOR_ERROR_BG: {DARK_COLOR_ERROR_BG};
        --COLOR_ERROR_TEXT: {DARK_COLOR_ERROR_TEXT};
        --COLOR_INFO_BG: {DARK_COLOR_INFO_BG};
        --COLOR_INFO_TEXT: {DARK_COLOR_INFO_TEXT};

        --primary: {DARK_PRIMARY};
        --surface: {DARK_SURFACE};
        --text: {DARK_TEXT};
        --border: {DARK_BORDER};
        --success: {DARK_SUCCESS};
        --error: {DARK_ERROR};

        --brand: #2D7AC9;
        --brand-dark: {DARK_PRIMARY_DARK};
        --brand-darker: {PRIMARY};
        --brand-light: {DARK_PRIMARY_LIGHT};
        --brand-soft: {DARK_PRIMARY_SOFT};

        --surface-elevated: {DARK_SURFACE_ELEVATED};
        --surface-raised: {DARK_SURFACE_RAISED};
        --surface-muted: {DARK_SURFACE_MUTED};
        --sidebar-bg: {DARK_SURFACE};
        --sidebar-border: {DARK_SURFACE_ELEVATED};
        --table-header-bg: {DARK_SURFACE_ELEVATED};

        --text-secondary: {DARK_TEXT_SECONDARY};
        --text-muted: {DARK_TEXT_MUTED};

        --border-subtle: #334155;
        --border-medium: {DARK_BORDER_MEDIUM};
        --border-strong: {DARK_BORDER_STRONG};

        --accent-coral: {DARK_PRIMARY};
        --accent-teal: #7DD3E0;
        --accent-amber: #FBBF24;
        --accent-green: #A2D06E;
        --accent-slate: {DARK_PRIMARY};

        --success-bg: #052E16;
        --success-text: var(--success);
        --success-border: #166534;
        --warning-bg: #451A03;
        --warning-text: #FCD34D;
        --warning-border: #B45309;
        --error-bg: #450A0A;
        --error-text: var(--error);
        --error-border: #7F1D1D;
        --info-bg: #1E1B4B;
        --info-text: #A5B4FC;
        --info-border: #3730A3;

        --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.45), 0 4px 6px -4px rgba(0,0,0,0.3);
    }}

    .stApp.stAppDark,
    .stApp.stAppDarkTheme {{
        --COLOR_BG: {DARK_COLOR_BG};
        --COLOR_SURFACE: {DARK_COLOR_SURFACE};
        --COLOR_SURFACE_ELEVATED: {DARK_COLOR_SURFACE_ELEVATED};
        --COLOR_TEXT_PRIMARY: {DARK_COLOR_TEXT_PRIMARY};
        --COLOR_TEXT_SECONDARY: {DARK_COLOR_TEXT_SECONDARY};
        --COLOR_TEXT_MUTED: {DARK_COLOR_TEXT_MUTED};
        --COLOR_BORDER: {DARK_COLOR_BORDER};
        --COLOR_PRIMARY: {DARK_COLOR_PRIMARY};
        --COLOR_PRIMARY_HOVER: {DARK_COLOR_PRIMARY_HOVER};
        --COLOR_PRIMARY_SOFT: {DARK_COLOR_PRIMARY_SOFT};
        --COLOR_SUCCESS_BG: {DARK_COLOR_SUCCESS_BG};
        --COLOR_SUCCESS_TEXT: {DARK_COLOR_SUCCESS_TEXT};
        --COLOR_WARNING_BG: {DARK_COLOR_WARNING_BG};
        --COLOR_WARNING_TEXT: {DARK_COLOR_WARNING_TEXT};
        --COLOR_ERROR_BG: {DARK_COLOR_ERROR_BG};
        --COLOR_ERROR_TEXT: {DARK_COLOR_ERROR_TEXT};
        --COLOR_INFO_BG: {DARK_COLOR_INFO_BG};
        --COLOR_INFO_TEXT: {DARK_COLOR_INFO_TEXT};

        --primary: {DARK_PRIMARY};
        --surface: {DARK_SURFACE};
        --text: {DARK_TEXT};
        --border: {DARK_BORDER};
        --success: {DARK_SUCCESS};
        --error: {DARK_ERROR};
        --brand: #2D7AC9;
        --brand-dark: {DARK_PRIMARY_DARK};
        --brand-darker: {PRIMARY};
        --brand-light: {DARK_PRIMARY_LIGHT};
        --brand-soft: {DARK_PRIMARY_SOFT};
        --surface-elevated: {DARK_SURFACE_ELEVATED};
        --surface-raised: {DARK_SURFACE_RAISED};
        --surface-muted: {DARK_SURFACE_MUTED};
        --sidebar-bg: {DARK_SURFACE};
        --sidebar-border: {DARK_SURFACE_ELEVATED};
        --table-header-bg: {DARK_SURFACE_ELEVATED};
        --text-secondary: {DARK_TEXT_SECONDARY};
        --text-muted: {DARK_TEXT_MUTED};
        --border-subtle: #334155;
        --border-medium: {DARK_BORDER_MEDIUM};
        --border-strong: {DARK_BORDER_STRONG};
        --accent-coral: {DARK_PRIMARY};
        --accent-teal: #7DD3E0;
        --accent-amber: #FBBF24;
        --accent-green: #A2D06E;
        --accent-slate: {DARK_PRIMARY};
        --success-bg: #052E16;
        --success-text: var(--success);
        --success-border: #166534;
        --warning-bg: #451A03;
        --warning-text: #FCD34D;
        --warning-border: #B45309;
        --error-bg: #450A0A;
        --error-text: var(--error);
        --error-border: #7F1D1D;
        --info-bg: #1E1B4B;
        --info-text: #A5B4FC;
        --info-border: #3730A3;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.45), 0 4px 6px -4px rgba(0,0,0,0.3);
    }}

    .stApp.stAppDark [data-testid="stSidebar"],
    .stApp.stAppDarkTheme [data-testid="stSidebar"] {{
        background: var(--sidebar-bg) !important;
    }}

    @media (prefers-color-scheme: dark) {{
        :root:not([data-theme="light"]) {{
            --COLOR_BG: {DARK_COLOR_BG};
            --COLOR_SURFACE: {DARK_COLOR_SURFACE};
            --COLOR_SURFACE_ELEVATED: {DARK_COLOR_SURFACE_ELEVATED};
            --COLOR_TEXT_PRIMARY: {DARK_COLOR_TEXT_PRIMARY};
            --COLOR_TEXT_SECONDARY: {DARK_COLOR_TEXT_SECONDARY};
            --COLOR_TEXT_MUTED: {DARK_COLOR_TEXT_MUTED};
            --COLOR_BORDER: {DARK_COLOR_BORDER};
            --COLOR_PRIMARY: {DARK_COLOR_PRIMARY};
            --COLOR_PRIMARY_HOVER: {DARK_COLOR_PRIMARY_HOVER};
            --COLOR_PRIMARY_SOFT: {DARK_COLOR_PRIMARY_SOFT};
            --COLOR_SUCCESS_BG: {DARK_COLOR_SUCCESS_BG};
            --COLOR_SUCCESS_TEXT: {DARK_COLOR_SUCCESS_TEXT};
            --COLOR_WARNING_BG: {DARK_COLOR_WARNING_BG};
            --COLOR_WARNING_TEXT: {DARK_COLOR_WARNING_TEXT};
            --COLOR_ERROR_BG: {DARK_COLOR_ERROR_BG};
            --COLOR_ERROR_TEXT: {DARK_COLOR_ERROR_TEXT};
            --COLOR_INFO_BG: {DARK_COLOR_INFO_BG};
            --COLOR_INFO_TEXT: {DARK_COLOR_INFO_TEXT};

            --primary: {DARK_PRIMARY};
            --surface: {DARK_SURFACE};
            --text: {DARK_TEXT};
            --border: {DARK_BORDER};
            --success: {DARK_SUCCESS};
            --error: {DARK_ERROR};
            --brand: #2D7AC9;
            --brand-dark: {DARK_PRIMARY_DARK};
            --brand-darker: {PRIMARY};
            --brand-light: {DARK_PRIMARY_LIGHT};
            --brand-soft: {DARK_PRIMARY_SOFT};
            --surface-elevated: {DARK_SURFACE_ELEVATED};
            --surface-raised: {DARK_SURFACE_RAISED};
            --surface-muted: {DARK_SURFACE_MUTED};
            --sidebar-bg: {DARK_SURFACE};
            --sidebar-border: {DARK_SURFACE_ELEVATED};
            --table-header-bg: {DARK_SURFACE_ELEVATED};
            --text-secondary: {DARK_TEXT_SECONDARY};
            --text-muted: {DARK_TEXT_MUTED};
            --border-subtle: #334155;
            --border-medium: {DARK_BORDER_MEDIUM};
            --border-strong: {DARK_BORDER_STRONG};
            --accent-coral: {DARK_PRIMARY};
            --accent-teal: #7DD3E0;
            --accent-amber: #FBBF24;
            --accent-green: #A2D06E;
            --accent-slate: {DARK_PRIMARY};
            --success-bg: #052E16;
            --success-text: var(--success);
            --success-border: #166534;
            --warning-bg: #451A03;
            --warning-text: #FCD34D;
            --warning-border: #B45309;
            --error-bg: #450A0A;
            --error-text: var(--error);
            --error-border: #7F1D1D;
            --info-bg: #1E1B4B;
            --info-text: #A5B4FC;
            --info-border: #3730A3;
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.45), 0 4px 6px -4px rgba(0,0,0,0.3);
        }}
    }}
"""
