"""Final visual polish layer for the Streamlit dashboard shell.

This module is intentionally loaded last so it can refine the existing design
system without changing business logic or tab rendering code.
"""

VISUAL_POLISH = r"""    /* ── Final visual polish layer ───────────────────────────
       Direction: brand-led light dashboard. White background, Boteco blue as
       the primary action/navigation color, amber as a small highlight, and
       neutral surfaces for data density. Loaded last to neutralize Streamlit
       dark-mode/system-preference overrides. */

    :root,
    .stApp,
    .stApp.stAppDark,
    .stApp.stAppDarkTheme {
        --brand: #005AAB;
        --brand-dark: #004080;
        --brand-darker: #003366;
        --brand-light: #2D7AC9;
        --brand-soft: #EBF4FF;
        --accent-amber: #FDB813;
        --accent-teal: #54C5D0;
        --accent-green: #A2D06E;
        --accent-coral: #005AAB;
        --surface: #FFFFFF;
        --surface-elevated: #FFFFFF;
        --surface-raised: #FFFFFF;
        --surface-muted: #F6FAFE;
        --table-header-bg: #F3F7FC;
        --text: #1E293B;
        --text-secondary: #475569;
        --text-muted: #64748B;
        --border: #E2E8F0;
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;
        --border-strong: #94A3B8;
        --shadow-card: 0 2px 8px rgba(15, 23, 42, 0.05);
        --shadow-card-hover: 0 8px 20px rgba(15, 23, 42, 0.08);
        --shadow-focus: 0 0 0 3px rgba(0, 90, 171, 0.18);
        --radius-xl: 16px;
        --font-size-kicker: 12px;
        --font-size-page-title: 26px;
        --font-size-section-title: 17px;
        --font-size-body: 15px;
        --font-size-label: 12px;
        --font-size-caption: 13px;
        --font-size-kpi: 32px;
        --control-height: 42px;
    }

    .app-shell,
    .stApp,
    .main,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main {
        background: var(--surface-muted) !important;
        color: var(--text) !important;
    }

    .main .block-container {
        max-width: 1240px !important;
        padding: var(--spacing-6) var(--spacing-8) var(--spacing-8) !important;
    }

    .top-tabs [data-testid="stTabs"] [role="tablist"],
    [data-testid="stTabs"] [role="tablist"] {
        position: sticky;
        top: 0;
        z-index: 20;
        display: inline-flex !important;
        gap: var(--spacing-2) !important;
        padding: var(--spacing-2) !important;
        margin: 0 0 var(--spacing-6) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 999px !important;
        background: var(--surface-elevated) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    button[data-baseweb="tab"] {
        min-height: var(--control-height) !important;
        padding: 0 var(--spacing-4) !important;
        border-radius: 999px !important;
        font-size: 0.92rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FFFFFF !important;
        background: var(--brand) !important;
        box-shadow: inset 0 -3px 0 var(--accent-amber) !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    .page-header,
    .page-hero {
        background: var(--surface-elevated) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-xl) !important;
        box-shadow: var(--shadow-sm) !important;
        padding: var(--spacing-4) var(--spacing-6) !important;
        margin-bottom: var(--spacing-6) !important;
    }
    .page-hero {
        border-top: 3px solid var(--brand) !important;
        align-items: center !important;
    }
    .page-hero-kicker {
        font-size: var(--font-size-kicker) !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--brand) !important;
        font-weight: 700 !important;
    }
    .page-hero-title {
        font-size: var(--font-size-page-title) !important;
        font-weight: 700 !important;
        line-height: 1.2 !important;
        color: var(--text) !important;
        margin: 0 !important;
    }
    .page-hero-subtitle {
        color: var(--text-secondary) !important;
        font-size: 0.95rem !important;
    }
    .page-hero-context {
        align-self: flex-start;
        border-radius: 999px;
        padding: 0.35rem 0.65rem;
        color: var(--brand-dark) !important;
        background: var(--brand-soft) !important;
        border: 1px solid rgba(0, 90, 171, 0.2) !important;
    }

    .section-title,
    .section-block-title {
        font-size: var(--font-size-section-title);
        font-weight: 600;
        color: var(--text);
    }
    .section-block-subtitle {
        font-size: var(--font-size-caption);
    }

    .section-card,
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    [data-testid="stPlotlyChart"],
    .kpi-primary-card,
    .kpi-secondary-card,
    .report-section-card,
    .context-band,
    .info-banner {
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        background: var(--surface-elevated) !important;
        box-shadow: var(--shadow-sm) !important;
    }

    .filter-row,
    .filter-strip {
        min-height: var(--control-height);
        border-radius: var(--radius-md) !important;
        padding: var(--spacing-2) var(--spacing-3) !important;
        gap: var(--spacing-2);
        margin-bottom: var(--spacing-3);
    }

    .kpi-grid,
    .kpi-snapshot-grid {
        gap: var(--spacing-3) !important;
    }
    .kpi-card,
    .kpi-item {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-subtle) !important;
        padding: var(--spacing-3) !important;
        min-height: 120px;
    }
    .kpi-label {
        font-size: var(--font-size-label) !important;
        letter-spacing: 0.05em;
    }
    .kpi-value {
        font-size: var(--font-size-kpi) !important;
        line-height: 1.1;
    }
    .delta-chip {
        font-size: var(--font-size-caption);
        font-weight: 600;
    }

    .btn,
    .stButton > button,
    .stDownloadButton > button,
    .stFormSubmitButton > button {
        min-height: var(--control-height) !important;
        border-radius: var(--radius-md) !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }
    .btn-primary,
    .stButton > button[kind="primary"] {
        background: var(--brand) !important;
        color: #FFFFFF !important;
        border-color: var(--brand) !important;
    }
    .btn-secondary,
    .stButton > button[kind="secondary"] {
        background: var(--surface-elevated) !important;
        color: var(--brand-dark) !important;
        border-color: var(--border-medium) !important;
    }
    .btn-secondary:hover,
    .stButton > button[kind="secondary"]:hover {
        background: var(--brand-soft) !important;
        border-color: var(--brand-light) !important;
    }

    .form-control,
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stTextArea textarea,
    .stSelectbox [data-baseweb="select"],
    .stMultiSelect [data-baseweb="select"] {
        min-height: var(--control-height) !important;
        border-radius: var(--radius-md) !important;
        border-color: var(--border-medium) !important;
        background: var(--surface-elevated) !important;
        color: var(--text) !important;
    }
    .stTextInput input:focus,
    .stNumberInput input:focus,
    .stDateInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox [data-baseweb="select"]:focus-within,
    .stMultiSelect [data-baseweb="select"]:focus-within {
        border-color: var(--brand) !important;
        box-shadow: var(--shadow-focus) !important;
    }

    .info-bar,
    .context-band {
        padding: var(--spacing-3) var(--spacing-4) !important;
        font-size: var(--font-size-caption);
        color: var(--text-secondary);
    }

    .analytics-filter-compact.mobile-layout-filters {
        padding: 0.35rem 0 !important;
        margin-bottom: 0.35rem !important;
        border: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    .analytics-filter-compact [data-testid="stHorizontalBlock"] {
        align-items: center !important;
        gap: 1rem !important;
    }
    .analytics-filter-compact [data-testid="stRadio"] {
        margin-bottom: 0 !important;
    }
    .analytics-filter-compact [role="radiogroup"] {
        gap: 0.85rem !important;
        align-items: center !important;
    }
    .analytics-filter-compact .stRadio > label {
        display: none !important;
    }
    .context-band.context-band--muted {
        padding: 0.75rem 1rem !important;
        margin: 0.25rem 0 0.75rem !important;
    }

    .sidebar,
    [data-testid="stSidebar"] {
        box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.1);
    }
    .sidebar-account-section {
        padding: var(--spacing-4) !important;
        border-radius: var(--radius-lg) !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        min-height: var(--control-height) !important;
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
        }
        [data-testid="stTabs"] [role="tablist"] {
            display: flex !important;
            width: 100% !important;
            overflow-x: auto;
            border-radius: var(--radius-lg) !important;
        }
        button[data-baseweb="tab"] {
            flex: 0 0 auto;
            padding: 0.5rem 0.75rem !important;
        }
        .page-hero {
            border-radius: var(--radius-lg) !important;
        }
    }

"""
