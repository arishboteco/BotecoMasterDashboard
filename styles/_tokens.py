"""Canonical design tokens shared by CSS, Streamlit theme config, and Python UI code.

Public exports:
  TOKEN_SYSTEM — light-mode token block.
  STREAMLIT_THEME_LIGHT — canonical values for `.streamlit/config.toml`.
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
COLOR_NEUTRAL_BG = "#F8FAFC"
COLOR_NEUTRAL_TEXT = "#334155"

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

SUCCESS = "#166534"
ERROR = "#991B1B"
CARD_SURFACE_NORMAL = "#FFFFFF"
CARD_SURFACE_ELEVATED = "#FFFFFF"
CARD_SURFACE_KPI_PRIMARY = "#FFFFFF"
CARD_SURFACE_REPORT_SECTION = "#EEF3F8"
CARD_SURFACE_EMPTY_STATE = "#FFFFFF"
KPI_LABEL_FG = TEXT_SECONDARY
KPI_VALUE_FG = TEXT
KPI_DELTA_NEUTRAL_FG = TEXT_SECONDARY
KPI_DELTA_POSITIVE_FG = SUCCESS
KPI_DELTA_NEGATIVE_FG = ERROR

# ── Streamlit config maps from canonical semantic tokens ──────────────────────
STREAMLIT_THEME_LIGHT = {
    "primaryColor": PRIMARY,
    "backgroundColor": SURFACE_ELEVATED,
    "secondaryBackgroundColor": SURFACE_MUTED,
    "textColor": TEXT,
    "font": "sans serif",
}

TOKEN_SYSTEM = f"""
    /* ── Light mode tokens (default) ─────────────────────────── */
    :root {{
        color-scheme: light;
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
        --COLOR_NEUTRAL_BG: {COLOR_NEUTRAL_BG};
        --COLOR_NEUTRAL_TEXT: {COLOR_NEUTRAL_TEXT};

        /* Semantic design-system aliases */
        --color-bg: var(--COLOR_BG);
        --color-surface: var(--COLOR_SURFACE);
        --color-surface-muted: var(--surface-muted);
        --color-border: var(--COLOR_BORDER);
        --color-border-strong: var(--border-strong);
        --color-text-primary: var(--COLOR_TEXT_PRIMARY);
        --color-text-secondary: var(--COLOR_TEXT_SECONDARY);
        --color-text-muted: var(--COLOR_TEXT_MUTED);
        --color-primary: var(--COLOR_PRIMARY);
        --color-primary-hover: var(--COLOR_PRIMARY_HOVER);
        --color-primary-soft: var(--COLOR_PRIMARY_SOFT);
        --color-accent: var(--accent-amber);
        --color-success: var(--success);
        --color-danger: var(--error);

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
        --sidebar-surface: var(--sidebar-bg);
        --sidebar-text: #FFFFFF;
        --sidebar-muted: rgba(255, 255, 255, 0.78);
        --sidebar-active-bg: rgba(255, 255, 255, 0.16);
        --sidebar-active-fg: var(--sidebar-text);
        --sidebar-active-border: rgba(255, 255, 255, 0.4);
        --sidebar-account-bg: rgba(255, 255, 255, 0.12);
        --sidebar-account-border: rgba(255, 255, 255, 0.24);
        --sidebar-avatar-bg: rgba(255, 255, 255, 0.28);
        --sidebar-avatar-fg: var(--sidebar-text);
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
        --neutral-bg: #F8FAFC;
        --neutral-text: #334155;
        --neutral-border: #CBD5E1;

        /* Unified semantic alert tokens */
        --alert-success-bg: var(--success-bg);
        --alert-success-text: var(--success-text);
        --alert-success-border: var(--success-border);
        --alert-error-bg: var(--error-bg);
        --alert-error-text: var(--error-text);
        --alert-error-border: var(--error-border);
        --alert-warning-bg: var(--warning-bg);
        --alert-warning-text: var(--warning-text);
        --alert-warning-border: var(--warning-border);
        --alert-info-bg: var(--info-bg);
        --alert-info-text: var(--info-text);
        --alert-info-border: var(--info-border);
        --alert-neutral-bg: var(--neutral-bg);
        --alert-neutral-text: var(--neutral-text);
        --alert-neutral-border: var(--neutral-border);

        /* Typography */
        --font-display: 'Plus Jakarta Sans', sans-serif;
        --font-body: 'Inter', sans-serif;
        --font-size-xs: 12px;
        --font-size-sm: 14px;
        --font-size-base: 16px;
        --font-size-lg: 18px;
        --font-size-xl: 24px;
        --font-size-2xl: 28px;
        --font-size-display: 32px;
        --font-size-caption: 13px;
        --font-size-label: 12px;
        --font-size-kpi: 32px;
        --font-weight-regular: 400;
        --font-weight-medium: 500;
        --font-weight-semibold: 600;
        --font-weight-bold: 700;

        /* Spacing scale (4px base) */
        --spacing-1: 4px;
        --spacing-2: 8px;
        --spacing-3: 12px;
        --spacing-4: 16px;
        --spacing-6: 24px;
        --spacing-8: 32px;
        --spacing-10: 40px;
        --spacing-xs: var(--spacing-1);
        --spacing-sm: var(--spacing-2);
        --spacing-md: var(--spacing-4);
        --spacing-lg: var(--spacing-6);
        --spacing-xl: var(--spacing-8);

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
        --btn-default-bg: var(--surface);
        --btn-default-fg: var(--text);
        --btn-default-border: var(--border-subtle);
        --btn-default-hover-bg: var(--brand-soft);
        --btn-default-hover-fg: var(--brand-dark);
        --btn-default-hover-border: var(--brand);
        --btn-primary-bg: var(--brand);
        --btn-primary-fg: #FFFFFF;
        --btn-primary-border: var(--brand);
        --btn-primary-hover-bg: var(--brand-dark);
        --btn-primary-hover-fg: #FFFFFF;
        --btn-primary-hover-border: var(--brand-dark);
        --btn-disabled-bg: var(--surface-elevated);
        --btn-disabled-fg: var(--text-muted);
        --btn-disabled-border: var(--border-subtle);
        --btn-download-bg: var(--surface-elevated);
        --btn-download-fg: var(--text);
        --btn-download-border: var(--border-subtle);
        --btn-download-hover-bg: var(--brand-soft);
        --btn-download-hover-fg: var(--brand-dark);
        --btn-download-hover-border: var(--brand);
        --btn-form-submit-bg: var(--brand);
        --btn-form-submit-fg: #FFFFFF;
        --btn-form-submit-border: var(--brand);
        --btn-form-submit-hover-bg: var(--brand-dark);
        --btn-form-submit-hover-fg: #FFFFFF;
        --btn-form-submit-hover-border: var(--brand-dark);
        --btn-sidebar-bg: #EBF4FF;
        --btn-sidebar-fg: var(--brand-darker);
        --btn-sidebar-border: rgba(255, 255, 255, 0.72);
        --btn-sidebar-hover-bg: #DCEBFF;
        --btn-sidebar-hover-fg: var(--brand-darker);
        --btn-sidebar-hover-border: rgba(255, 255, 255, 0.88);
        --btn-sidebar-active-bg: #CFE2FF;
        --btn-sidebar-active-fg: var(--brand-darker);
        --btn-sidebar-active-border: rgba(255, 255, 255, 0.96);
        --btn-sidebar-disabled-bg: rgba(255, 255, 255, 0.22);
        --btn-sidebar-disabled-fg: rgba(255, 255, 255, 0.74);
        --btn-sidebar-disabled-border: rgba(255, 255, 255, 0.45);

        --select-option-bg: var(--surface-elevated);
        --select-option-fg: var(--text);
        --select-option-hover-bg: var(--brand-soft);
        --select-option-hover-fg: var(--brand-dark);
        --select-option-selected-bg: #DCEBFF;
        --select-option-selected-fg: var(--brand-darker);
        --select-option-disabled-bg: var(--surface-elevated);
        --select-option-disabled-fg: var(--text-muted);

        /* Navigation tabs */
        --tab-inactive-bg: transparent;
        --tab-inactive-fg: var(--text-secondary);
        --tab-inactive-border: transparent;
        --tab-hover-bg: var(--brand-soft);
        --tab-hover-fg: var(--brand);
        --tab-hover-border: var(--brand-light);
        --tab-active-bg: var(--brand);
        --tab-active-fg: #FFFFFF;
        --tab-active-border: var(--brand-dark);
        --tab-focus-ring: var(--brand);

        /* Card / KPI semantic tokens */
        --card-surface-normal: {CARD_SURFACE_NORMAL};
        --card-surface-elevated: {CARD_SURFACE_ELEVATED};
        --card-surface-kpi-primary: {CARD_SURFACE_KPI_PRIMARY};
        --card-surface-report-section: {CARD_SURFACE_REPORT_SECTION};
        --card-surface-empty-state: {CARD_SURFACE_EMPTY_STATE};
        --kpi-label-fg: {KPI_LABEL_FG};
        --kpi-value-fg: {KPI_VALUE_FG};
        --kpi-delta-neutral-fg: {KPI_DELTA_NEUTRAL_FG};
        --kpi-delta-positive-fg: {KPI_DELTA_POSITIVE_FG};
        --kpi-delta-negative-fg: {KPI_DELTA_NEGATIVE_FG};

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

"""
