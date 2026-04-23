"""Sidebar styling — base, account section, gradient refinement."""

SIDEBAR = r"""
    /* ── Sidebar — uses CSS tokens for mode-aware theming ─────── */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }
    [data-testid="stSidebar"]::before {
        content: '';
        display: block;
        height: 3px;
        background: linear-gradient(90deg, var(--brand), var(--accent-amber));
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        z-index: 1;
    }

    /* Logo — white card so dark logo is visible on any sidebar bg */
    [data-testid="stSidebar"] img {
        background-color: #FFFFFF;
        border-radius: var(--radius-md);
        padding: 8px;
        display: block;
    }

    /* Sidebar text — white on brand/dark surfaces */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] span {
        color: rgba(255, 255, 255, 0.9) !important;
    }
    [data-testid="stSidebar"] strong {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6 {
        color: #FFFFFF !important;
        border-left: none !important;
        padding-left: 0 !important;
    }
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] small {
        color: rgba(255, 255, 255, 0.7) !important;
    }
    [data-testid="stSidebar"] label {
        color: rgba(255, 255, 255, 0.85) !important;
    }

    /* Sidebar dividers */
    [data-testid="stSidebar"] hr {
        margin: 1rem 0;
        border-color: var(--sidebar-border) !important;
        opacity: 0.5;
    }

    /* Sidebar logout button — semi-transparent white style */
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255, 255, 255, 0.12) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.35) !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255, 255, 255, 0.22) !important;
        border-color: rgba(255, 255, 255, 0.55) !important;
    }

    /* Sidebar selectbox / input elements */
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"],
    [data-testid="stSidebar"] .stTextInput input {
        background: rgba(255, 255, 255, 0.08) !important;
        color: #FFFFFF !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
    }

"""

SIDEBAR_IMPROVEMENTS = r"""
    /* ── Sidebar improvements ─────────────────────────────── */
    .sidebar-account-section {
        background: rgba(255, 255, 255, 0.08);
        border-radius: var(--radius-md);
        padding: 0.75rem;
        margin-bottom: 0.5rem;
    }
    .sidebar-account-row {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-bottom: 0.6rem;
    }
    .sidebar-account-section .user-name {
        font-weight: 600;
        color: #fff;
        font-size: 0.9rem;
        line-height: 1.2;
    }
    .sidebar-account-section .role-label {
        font-size: 0.72rem;
        color: rgba(255, 255, 255, 0.75);
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .sidebar-account-section .location-row {
        font-size: 0.78rem;
        color: rgba(255, 255, 255, 0.75);
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }
    .sidebar-account-section .location-pin {
        opacity: 0.6;
    }
    .sidebar-footer {
        margin-top: auto;
        padding-top: 1rem;
        text-align: center;
    }
    [data-testid="stSidebar"] > div:first-child {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
    }
    .sidebar-footer-text {
        font-size: 0.68rem;
        color: rgba(255, 255, 255, 0.55);
        letter-spacing: 0.04em;
    }
    .sidebar-user-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: rgba(255, 255, 255, 0.15);
        border-radius: var(--radius-sm);
        padding: 0.25rem 0.5rem;
        font-size: 0.85rem;
        color: #fff;
    }
    .sidebar-user-initials {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.3);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 600;
    }

"""

SIDEBAR_GRADIENT_REFINEMENT = r"""
    /* ── Sidebar gradient refinement ──────────────────────── */
    /* Light: brand blue gradient; Dark: deep navy (no gradient needed) */
    [data-testid="stSidebar"] {
        background: linear-gradient(
            175deg,
            var(--brand) 0%,
            var(--brand-dark) 60%,
            var(--brand-darker) 100%
        ) !important;
    }
    :root[data-theme="dark"] [data-testid="stSidebar"] {
        background: var(--sidebar-bg) !important;
    }
    @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) [data-testid="stSidebar"] {
            background: var(--sidebar-bg) !important;
        }
    }

"""