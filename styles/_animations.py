"""Skeleton pulse, page load animations, reduced-motion support."""

LOADING_SKELETON = r"""    /* ── Loading skeleton ────────────────────────────────── */
    @keyframes skeleton-pulse {
        0% { opacity: 0.6; }
        50% { opacity: 0.3; }
        100% { opacity: 0.6; }
    }
    .skeleton {
        background: linear-gradient(90deg, var(--surface) 25%, var(--border-subtle) 50%, var(--surface) 75%);
        background-size: 200% 100%;
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        border-radius: var(--radius-sm);
    }
    .skeleton-card {
        height: 120px;
        margin-bottom: 1rem;
    }
    .skeleton-chart {
        height: 380px;
        margin-bottom: 1rem;
    }
    .skeleton-metric {
        height: 80px;
        margin-bottom: 0.5rem;
    }
    .skeleton-table-row {
        height: 40px;
        margin-bottom: 0.5rem;
    }

"""

PAGE_LOAD_ANIMATIONS = r"""    /* ── Page load animations ─────────────────────────────── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes scaleIn {
        from { opacity: 0; transform: scale(0.97); }
        to   { opacity: 1; transform: scale(1); }
    }
    @keyframes slideInDown {
        from { opacity: 0; transform: translateY(-12px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* Staggered tab content entrance (50ms delay after container fadeIn) */
    [data-testid="stTabsContent"] > div {
        animation: fadeInUp 0.3s ease-out 50ms both;
    }

    /* Metric container entrance */
    [data-testid="stVerticalBlockBorderWrapper"] {
        animation: scaleIn 0.25s ease-out both;
    }

    /* Main block fade in */
    .main .block-container {
        animation: fadeIn 0.2s ease-out both;
    }

    /* Chart containers — staggered when multiple in a horizontal row */
    [data-testid="stPlotlyChart"] {
        animation: fadeInUp 0.35s ease-out both;
    }
    [data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stPlotlyChart"] { animation-delay: 0ms; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stPlotlyChart"] { animation-delay: 80ms; }
    [data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stPlotlyChart"] { animation-delay: 160ms; }
    [data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stPlotlyChart"] { animation-delay: 240ms; }

    /* Toast / alert slide-in from top (applies to Streamlit alerts) */
    [data-testid="stNotificationContent"],
    [data-testid="stAlert"] {
        animation: slideInDown 0.2s ease-out both;
    }

"""

REDUCED_MOTION_DISABLE_ALL_ANIMATIONS = r"""    /* ── Reduced motion — disable all animations ──────────── */
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }

"""

