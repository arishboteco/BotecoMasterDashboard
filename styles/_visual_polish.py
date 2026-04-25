"""Final visual polish layer for the Streamlit dashboard shell.

This module is intentionally loaded last so it can refine the existing design
system without changing business logic or tab rendering code.
"""

VISUAL_POLISH = r"""    /* ── Final visual polish layer ─────────────────────────── */
    :root {
        --radius-xl: 20px;
        --shadow-card: 0 14px 30px rgba(15, 23, 42, 0.08), 0 2px 8px rgba(15, 23, 42, 0.04);
        --shadow-card-hover: 0 18px 42px rgba(15, 23, 42, 0.12), 0 4px 12px rgba(15, 23, 42, 0.06);
        --shadow-focus: 0 0 0 4px rgba(0, 90, 171, 0.14);
    }

    .stApp {
        background:
            radial-gradient(circle at 12% -10%, rgba(0, 90, 171, 0.10), transparent 32rem),
            radial-gradient(circle at 90% 0%, rgba(84, 197, 208, 0.10), transparent 28rem),
            linear-gradient(180deg, #F8FBFF 0%, var(--surface) 42%, #FFFFFF 100%) !important;
    }

    .main .block-container {
        max-width: 1320px !important;
        padding-top: 1.25rem !important;
    }

    /* Make the tab bar feel like app navigation rather than default widgets. */
    [data-testid="stTabs"] [role="tablist"] {
        position: sticky;
        top: 0;
        z-index: 20;
        display: inline-flex !important;
        width: auto !important;
        max-width: 100%;
        gap: 0.35rem !important;
        padding: 0.35rem !important;
        margin: 0 0 1.15rem !important;
        border: 1px solid rgba(148, 163, 184, 0.22) !important;
        border-radius: 999px !important;
        background: rgba(255, 255, 255, 0.82) !important;
        box-shadow: var(--shadow-sm) !important;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
    }
    button[data-baseweb="tab"] {
        min-height: 40px !important;
        padding: 0.5rem 1rem !important;
        border-radius: 999px !important;
    }
    button[data-baseweb="tab"]:hover {
        transform: translateY(-1px);
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FFFFFF !important;
        background: linear-gradient(135deg, var(--brand), var(--brand-dark)) !important;
        box-shadow: 0 8px 18px rgba(0, 90, 171, 0.22) !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* Elevated content surfaces: metrics, bordered containers, expanders and charts. */
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    [data-testid="stPlotlyChart"] {
        border: 1px solid rgba(148, 163, 184, 0.20) !important;
        border-radius: var(--radius-lg) !important;
        background: rgba(255, 255, 255, 0.88) !important;
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
        border-color: rgba(148, 163, 184, 0.22) !important;
        background: rgba(255, 255, 255, 0.90) !important;
        box-shadow: var(--shadow-card) !important;
    }
    .metric-card,
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        position: relative;
        border-left: none !important;
    }
    .metric-card::before,
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: linear-gradient(180deg, var(--brand), var(--accent-teal));
        border-radius: var(--radius-lg) 0 0 var(--radius-lg);
    }

    div[data-testid="stMetricValue"] {
        letter-spacing: -0.035em !important;
        line-height: 1.05 !important;
    }
    div[data-testid="stMetricLabel"] {
        color: var(--text-muted) !important;
    }

    /* Buttons with clearer hierarchy and a more tactile hover state. */
    .stButton > button {
        border-radius: var(--radius-md) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-md) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--brand), var(--brand-dark)) !important;
        box-shadow: 0 10px 20px rgba(0, 90, 171, 0.22) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, var(--brand-light), var(--brand)) !important;
    }

    /* Inputs and selectors should read as modern controls, not plain form fields. */
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stTextArea textarea,
    .stSelectbox [data-baseweb="select"],
    .stMultiSelect [data-baseweb="select"] {
        min-height: 42px !important;
        border-radius: var(--radius-md) !important;
        border-color: rgba(148, 163, 184, 0.34) !important;
        background: rgba(255, 255, 255, 0.92) !important;
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

    /* File uploader: clearer destination area and premium dashed border. */
    .upload-zone-container [data-testid="stFileUploaderDropzone"] {
        min-height: 164px !important;
        border-color: rgba(0, 90, 171, 0.45) !important;
        background:
            linear-gradient(135deg, rgba(235, 244, 255, 0.88), rgba(255,255,255,0.92)) !important;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.65), var(--shadow-card) !important;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--brand) !important;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.75), var(--shadow-card-hover) !important;
    }

    /* Sidebar polish: glass account card and better logo treatment. */
    [data-testid="stSidebar"] img {
        border-radius: var(--radius-lg) !important;
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18) !important;
    }
    .sidebar-account-section {
        background: rgba(255, 255, 255, 0.16) !important;
        border-color: rgba(255, 255, 255, 0.24) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.14) !important;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
    }
    .sidebar-user-initials {
        width: 32px !important;
        height: 32px !important;
        background: rgba(255, 255, 255, 0.24) !important;
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.22) !important;
    }
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        background: rgba(255, 255, 255, 0.14) !important;
        border-color: rgba(255, 255, 255, 0.28) !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] * {
        color: #FFFFFF !important;
    }

    /* Tables: make dense data easier to scan. */
    [data-testid="stDataFrame"] th {
        background: linear-gradient(180deg, #F8FAFC, #EEF2F7) !important;
    }
    [data-testid="stDataFrame"] td {
        border-bottom-color: rgba(226, 232, 240, 0.72) !important;
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
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
