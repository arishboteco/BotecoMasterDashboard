"""Responsive breakpoints and touch-target tuning."""

TOUCH_TARGET_IMPROVEMENTS = r"""    /* ── Touch target improvements ────────────────────────── */
    @media (pointer: coarse) {
        .stButton > button,
        .action-btn {
            min-height: 44px !important;
            min-width: 44px !important;
        }
        .date-nav-btn {
            min-height: 44px !important;
        }
    }

"""

RESPONSIVE_BREAKPOINTS = r"""    /* ── Responsive breakpoints ────────────────────────────── */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem !important;
        }
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.2rem !important; }
        h3 { font-size: 1.05rem !important; }
        .date-display {
            font-size: 1rem !important;
            min-width: auto !important;
            padding: 0.4rem 0.75rem !important;
        }
        .date-nav-container {
            flex-direction: column !important;
            gap: 0.5rem !important;
        }
        .date-nav-btn {
            width: 100% !important;
        }
    }

    @media (max-width: 480px) {
        .main .block-container {
            padding: 0.75rem !important;
        }
        h1 { font-size: 1.35rem !important; }
        h2 { font-size: 1.1rem !important; }
        .boteco-header-name { font-size: 1.25rem !important; }
        .boteco-header-sub { font-size: 0.75rem !important; }
        [data-testid="stDataFrame"] td {
            font-size: 0.75rem !important;
        }
    }

    @media (min-width: 1440px) {
        .main .block-container {
            max-width: 1400px;
        }
    }

"""

MOBILE_TOUCH_IMPROVEMENTS = r"""    /* ── Mobile touch improvements ───────────────────────── */
    @media (max-width: 480px) {
        .action-btn-row .action-btn {
            width: 44px !important;
            height: 44px !important;
        }
        .stButton > button {
            min-height: 44px !important;
            font-size: 0.9rem !important;
        }
        [data-testid="stVerticalBlock"] {
            gap: 0.5rem !important;
        }
        /* Stack column layouts only when a child is wide content that would
           squish to illegibility on narrow screens (charts, tables, metrics,
           form inputs). Icon rows and centering layouts with [1,2,1] / [1,4,1]
           spacers stay horizontal. Requires :has() — Chrome 105+, Safari 15.4+,
           Firefox 121+; older browsers keep the row layout (harmless fallback). */
        [data-testid="stHorizontalBlock"]:is(
            :has([data-testid="stPlotlyChart"]),
            :has([data-testid="stDataFrame"]),
            :has([data-testid="stMetric"]),
            :has([data-testid="stTextInput"]),
            :has([data-testid="stNumberInput"]),
            :has([data-testid="stSelectbox"]),
            :has([data-testid="stDateInput"]),
            :has([data-testid="stTextArea"]),
            :has([data-testid="stFileUploader"])
        ) {
            flex-direction: column !important;
        }
        [data-testid="stHorizontalBlock"]:is(
            :has([data-testid="stPlotlyChart"]),
            :has([data-testid="stDataFrame"]),
            :has([data-testid="stMetric"]),
            :has([data-testid="stTextInput"]),
            :has([data-testid="stNumberInput"]),
            :has([data-testid="stSelectbox"]),
            :has([data-testid="stDateInput"]),
            :has([data-testid="stTextArea"]),
            :has([data-testid="stFileUploader"])
        ) > div {
            width: 100% !important;
        }
        /* Scrollable tables on mobile */
        [data-testid="stDataFrame"] {
            overflow-x: auto !important;
        }
        .stMarkdown table {
            display: block;
            overflow-x: auto;
            white-space: nowrap;
        }
    }

"""

RESPONSIVE_PLOTLY_HEIGHT = r"""    /* ── Responsive Plotly chart height ───────────────────── */
    @media (max-width: 768px) {
        [data-testid="stPlotlyChart"] {
            height: 280px !important;
        }
        [data-testid="stPlotlyChart"] > div,
        [data-testid="stPlotlyChart"] .js-plotly-plot {
            height: 280px !important;
        }
    }

"""

