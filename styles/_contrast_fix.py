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

    /* DataFrame cells: ensure rendered cell text inherits accessible table color. */
    [data-testid="stDataFrame"] td,
    [data-testid="stDataFrame"] td * {
        color: var(--text) !important;
    }

"""
