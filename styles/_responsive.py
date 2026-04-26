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
        .page-hero {
            flex-direction: column;
            padding: 0.85rem;
        }
        .page-hero-context {
            white-space: normal;
            width: 100%;
            text-align: center;
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
        .mobile-layout-stack [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 0.55rem !important;
        }
        .mobile-layout-stack [data-testid="stHorizontalBlock"] > div {
            width: 100% !important;
        }
        .mobile-layout-filters {
            position: sticky;
            top: 0;
            z-index: 50;
            background: var(--surface);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 0.6rem;
            margin-bottom: 0.65rem;
        }
        .mobile-layout-secondary details,
        .mobile-layout-secondary [data-testid="stExpander"] {
            margin-top: 0.4rem;
        }
        .mobile-layout-primary-action {
            position: sticky;
            bottom: 0.35rem;
            z-index: 60;
            background: linear-gradient(
                180deg,
                color-mix(in srgb, var(--surface) 0%, transparent),
                var(--surface) 35%
            );
            padding-top: 0.45rem;
        }
        .mobile-layout-primary-action .stButton > button,
        .mobile-layout-primary-action [data-testid="baseButton-primary"] {
            box-shadow: 0 6px 20px color-mix(in srgb, var(--brand) 25%, transparent);
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
