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
        --sidebar-bg: #FFFFFF;
        --sidebar-border: #E2E8F0;
        --table-header-bg: #F3F7FC;

        --text: #1E293B;
        --text-secondary: #475569;
        --text-muted: #64748B;
        --border: #E2E8F0;
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;
        --border-strong: #94A3B8;

        --shadow-card: 0 8px 20px rgba(15, 23, 42, 0.055), 0 1px 3px rgba(15, 23, 42, 0.04);
        --shadow-card-hover: 0 12px 26px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.045);
        --shadow-focus: 0 0 0 3px rgba(0, 90, 171, 0.14);
        --radius-xl: 20px;
    }

    .stApp,
    .main,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main {
        background: #FFFFFF !important;
        color: var(--text) !important;
    }

    .main .block-container {
        max-width: 1280px !important;
        padding: 1.25rem 1.6rem 2rem !important;
    }

    /* Hero and section surfaces: calm, white, and clearly grouped. */
    .page-hero {
        background: var(--surface-elevated) !important;
        border: 1px solid var(--border-subtle) !important;
        border-top: 4px solid var(--brand) !important;
        border-radius: var(--radius-xl) !important;
        box-shadow: var(--shadow-card) !important;
        padding: 1.15rem 1.25rem !important;
    }
    .page-hero-kicker {
        color: var(--brand) !important;
        font-weight: 700 !important;
    }
    .page-hero-title {
        color: var(--text) !important;
        letter-spacing: -0.03em !important;
    }
    .page-hero-subtitle {
        color: var(--text-secondary) !important;
    }
    .page-hero-context {
        background: var(--brand-soft) !important;
        border-color: rgba(0, 90, 171, 0.18) !important;
        color: var(--brand-dark) !important;
    }

    h2, h3,
    .stMarkdown h2, .stMarkdown h3,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        border-left-color: var(--accent-amber) !important;
    }

    /* App navigation: simple pill tabs, strong active state, no dark shell. */
    [data-testid="stTabs"] [role="tablist"] {
        position: sticky;
        top: 0;
        z-index: 20;
        display: inline-flex !important;
        width: auto !important;
        max-width: 100%;
        gap: 0.3rem !important;
        padding: 0.35rem !important;
        margin: 0 0 1.15rem !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 999px !important;
        background: #FFFFFF !important;
        box-shadow: var(--shadow-card) !important;
    }
    button[data-baseweb="tab"] {
        min-height: 40px !important;
        padding: 0.5rem 1rem !important;
        border-radius: 999px !important;
        color: var(--text-secondary) !important;
    }
    button[data-baseweb="tab"]:hover {
        background: var(--brand-soft) !important;
        color: var(--brand-dark) !important;
        transform: translateY(-1px);
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FFFFFF !important;
        background: var(--brand) !important;
        box-shadow: inset 0 -3px 0 var(--accent-amber), 0 6px 14px rgba(0, 90, 171, 0.16) !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* Elevated content surfaces: use white cards and subtle depth. */
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    [data-testid="stPlotlyChart"] {
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        background: #FFFFFF !important;
        box-shadow: var(--shadow-card) !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stExpander"],
    [data-testid="stPlotlyChart"] {
        overflow: hidden !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover,
    [data-testid="stExpander"]:hover,
    [data-testid="stPlotlyChart"]:hover {
        box-shadow: var(--shadow-card-hover) !important;
        transform: translateY(-1px);
    }
    [data-testid="stPlotlyChart"] {
        padding: 0.65rem !important;
    }

    .metric-card,
    .kpi-primary-card,
    .kpi-secondary-card,
    .upload-zone,
    .context-band,
    .info-banner,
    .empty-state,
    .filter-strip,
    .date-display {
        border-color: var(--border-subtle) !important;
        background: #FFFFFF !important;
        box-shadow: var(--shadow-card) !important;
    }
    .metric-card,
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        position: relative;
        border-left: none !important;
        background: #FFFFFF !important;
    }
    .metric-card::before,
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: var(--brand);
        border-radius: var(--radius-lg) 0 0 var(--radius-lg);
    }
    .kpi-primary-card {
        border-top: 3px solid var(--brand) !important;
    }
    .kpi-secondary-card {
        background: var(--surface-muted) !important;
    }

    div[data-testid="stMetricValue"] {
        letter-spacing: -0.035em !important;
        line-height: 1.05 !important;
        color: var(--text) !important;
    }
    div[data-testid="stMetricLabel"] {
        color: var(--text-muted) !important;
    }
    div[data-testid="stMetricDelta"] {
        color: var(--brand-dark) !important;
    }

    /* Buttons: clear hierarchy, brand blue for primary actions, amber only as a highlight. */
    .stButton > button {
        border-radius: var(--radius-md) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-md) !important;
    }
    .stButton > button[kind="primary"] {
        background: var(--brand) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--brand) !important;
        box-shadow: 0 6px 14px rgba(0, 90, 171, 0.16) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--brand-dark) !important;
        border-color: var(--brand-dark) !important;
    }
    .stButton > button[kind="secondary"] {
        background: #FFFFFF !important;
        color: var(--brand-dark) !important;
        border: 1px solid var(--border-medium) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: var(--brand-soft) !important;
        border-color: var(--brand-light) !important;
    }

    /* Inputs and selectors: white controls on a white app, with clearer focus. */
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stTextArea textarea,
    .stSelectbox [data-baseweb="select"],
    .stMultiSelect [data-baseweb="select"] {
        min-height: 42px !important;
        border-radius: var(--radius-md) !important;
        border-color: var(--border-medium) !important;
        background: #FFFFFF !important;
        color: var(--text) !important;
        box-shadow: var(--shadow-sm) !important;
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

    /* File uploader: visible destination area, still clean and brand-aligned. */
    .upload-zone-container [data-testid="stFileUploaderDropzone"] {
        min-height: 164px !important;
        border: 1.5px dashed rgba(0, 90, 171, 0.45) !important;
        background: #FFFFFF !important;
        box-shadow: var(--shadow-card) !important;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--brand) !important;
        background: var(--brand-soft) !important;
        box-shadow: var(--shadow-card-hover) !important;
    }

    /* Sidebar: switch from dark/gradient rail to a polished light brand sidebar. */
    [data-testid="stSidebar"] {
        background: #FFFFFF !important;
        border-right: 1px solid var(--border-subtle) !important;
        box-shadow: 8px 0 24px rgba(15, 23, 42, 0.04) !important;
    }
    [data-testid="stSidebar"]::before {
        height: 4px !important;
        background: var(--brand) !important;
    }
    [data-testid="stSidebar"] img {
        background: #FFFFFF !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-card) !important;
        padding: 8px !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] small {
        color: var(--text-secondary) !important;
    }
    [data-testid="stSidebar"] strong,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6 {
        color: var(--text) !important;
        border-left: none !important;
        padding-left: 0 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--border-subtle) !important;
    }
    .sidebar-account-section {
        background: var(--brand-soft) !important;
        border: 1px solid rgba(0, 90, 171, 0.16) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: none !important;
    }
    .sidebar-account-section .user-name {
        color: var(--brand-dark) !important;
        font-weight: 700 !important;
    }
    .sidebar-account-section .role-label,
    .sidebar-account-section .location-row {
        color: var(--text-secondary) !important;
    }
    .sidebar-user-initials {
        width: 32px !important;
        height: 32px !important;
        background: var(--brand) !important;
        color: #FFFFFF !important;
        box-shadow: inset 0 -2px 0 var(--accent-amber) !important;
    }
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        background: #FFFFFF !important;
        border-color: var(--border-medium) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] * {
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: #FFFFFF !important;
        color: var(--brand-dark) !important;
        border: 1px solid var(--border-medium) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: var(--brand-soft) !important;
        border-color: var(--brand-light) !important;
    }
    .sidebar-footer-text {
        color: var(--text-muted) !important;
    }

    /* Tables: readable, neutral, and dense-data friendly. */
    [data-testid="stDataFrame"] th {
        background: var(--table-header-bg) !important;
        color: var(--brand-dark) !important;
    }
    [data-testid="stDataFrame"] td {
        border-bottom-color: var(--border-subtle) !important;
        color: var(--text) !important;
    }
    [data-testid="stDataFrame"] tr:hover {
        background-color: var(--brand-soft) !important;
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
