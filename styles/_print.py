"""Print-safe rules for hard-copy export."""

PRINT_STYLES = r"""    /* ── Print styles ─────────────────────────────────────── */
    @media print {
        [data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stDecoration"],
        [data-testid="stToolbar"],
        [data-testid="stTabs"] [role="tablist"],
        .stButton,
        .stFileUploader,
        .stDateInput,
        [data-testid="stExpander"] {
            display: none !important;
        }
        .main .block-container {
            padding: 0 !important;
            max-width: 100% !important;
        }
        [data-testid="stAppViewContainer"] {
            background: #fff !important;
        }
        h1, h2, h3 {
            color: #000 !important;
        }
        [data-testid="stDataFrame"] {
            overflow: visible !important;
        }
        @page {
            margin: 1.5cm;
            size: A4 landscape;
        }
    }

"""

