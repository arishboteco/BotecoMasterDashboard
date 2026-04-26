"""High-priority contrast fixes for Streamlit-rendered labels and controls.

This layer is intentionally narrow: it only patches nested Streamlit/BaseWeb
selectors that can lose inherited foreground color in certain render paths.
"""

CONTRAST_FIX = r"""    /* ── Contrast safety layer (scoped selectors only) ───────────────────── */

    /* Buttons: force nested Streamlit labels to inherit the button foreground. */
    .stButton > button p,
    .stButton > button span,
    .stDownloadButton > button p,
    .stDownloadButton > button span,
    .stFormSubmitButton > button p,
    .stFormSubmitButton > button span,
    [data-testid="stSidebar"] .stButton > button p,
    [data-testid="stSidebar"] .stButton > button span {
        color: inherit !important;
    }

    /* Tabs: preserve intended foreground by inheriting to nested label nodes. */
    button[data-baseweb="tab"] p,
    button[data-baseweb="tab"] span {
        color: inherit !important;
    }

    /* Widget labels: use semantic tokenized text color for robust readability. */
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span {
        color: var(--text-secondary) !important;
    }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] span {
        color: var(--sidebar-muted) !important;
    }

    /* DataFrame cells: ensure rendered cell text inherits accessible table color. */
    [data-testid="stDataFrame"] td,
    [data-testid="stDataFrame"] td * {
        color: var(--text) !important;
    }

    /* Streamlit semantic alerts: shared tokenized surfaces for upload, validation, import status. */
    [data-testid="stAlert"] {
        background: var(--alert-neutral-bg) !important;
        color: var(--alert-neutral-text) !important;
        border: 1px solid var(--alert-neutral-border) !important;
        border-radius: var(--radius-sm) !important;
    }
    [data-testid="stAlert"] * {
        color: inherit !important;
    }
    [data-testid="stAlert"][kind="success"],
    [data-testid="stAlert"][kind="positive"],
    [data-testid="stAlert"] [data-baseweb="notification"][kind="success"],
    [data-testid="stAlert"] [data-baseweb="notification"][kind="positive"] {
        background: var(--alert-success-bg) !important;
        color: var(--alert-success-text) !important;
        border-color: var(--alert-success-border) !important;
    }
    [data-testid="stAlert"][kind="error"],
    [data-testid="stAlert"][kind="negative"],
    [data-testid="stAlert"] [data-baseweb="notification"][kind="error"],
    [data-testid="stAlert"] [data-baseweb="notification"][kind="negative"] {
        background: var(--alert-error-bg) !important;
        color: var(--alert-error-text) !important;
        border-color: var(--alert-error-border) !important;
    }
    [data-testid="stAlert"][kind="warning"],
    [data-testid="stAlert"] [data-baseweb="notification"][kind="warning"] {
        background: var(--alert-warning-bg) !important;
        color: var(--alert-warning-text) !important;
        border-color: var(--alert-warning-border) !important;
    }
    [data-testid="stAlert"][kind="info"],
    [data-testid="stAlert"] [data-baseweb="notification"][kind="info"] {
        background: var(--alert-info-bg) !important;
        color: var(--alert-info-text) !important;
        border-color: var(--alert-info-border) !important;
    }

"""
