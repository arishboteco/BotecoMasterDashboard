"""Sidebar styling — token-driven shell and account components."""

SIDEBAR = r"""    /* ── Sidebar ────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-surface) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }

    /* Logo area */
    [data-testid="stSidebar"] img {
        border: 0;
        border-radius: 0;
        padding: 0;
        display: block;
        margin: 0 auto 0.5rem auto;
    }

    /* Sidebar text */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] span {
        color: var(--sidebar-text) !important;
    }
    [data-testid="stSidebar"] strong {
        color: var(--sidebar-text) !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6 {
        color: var(--sidebar-text) !important;
        border-left: none !important;
        padding-left: 0 !important;
    }
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] label {
        color: var(--sidebar-muted) !important;
    }

    [data-testid="stSidebar"] hr {
        margin: 1rem 0;
        border-color: var(--sidebar-active-border) !important;
    }

    /* Sidebar button: active/selected tokenized style */
    [data-testid="stSidebar"] .stButton > button {
        background: var(--btn-sidebar-bg) !important;
        color: var(--btn-sidebar-fg) !important;
        border: 1px solid var(--btn-sidebar-border) !important;
        min-height: 42px !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: var(--btn-sidebar-hover-bg) !important;
        color: var(--btn-sidebar-hover-fg) !important;
        border-color: var(--btn-sidebar-hover-border) !important;
    }
    [data-testid="stSidebar"] .stButton > button:focus,
    [data-testid="stSidebar"] .stButton > button:focus-visible,
    [data-testid="stSidebar"] .stButton > button:active {
        background: var(--btn-sidebar-active-bg) !important;
        color: var(--btn-sidebar-fg) !important;
        border-color: var(--btn-sidebar-active-border) !important;
    }
    [data-testid="stSidebar"] .stButton > button:disabled {
        background: var(--btn-sidebar-disabled-bg) !important;
        color: var(--btn-sidebar-disabled-fg) !important;
        border-color: var(--btn-sidebar-disabled-border) !important;
    }
    [data-testid="stSidebar"] .stButton > button::selection {
        color: var(--btn-sidebar-fg) !important;
        background: rgba(59, 130, 246, 0.2);
    }
"""

SIDEBAR_IMPROVEMENTS = r"""    /* ── Sidebar improvements ─────────────────────────────── */
    .sidebar-account-section {
        background: var(--sidebar-account-bg);
        border-radius: var(--radius-md);
        border: 1px solid var(--sidebar-account-border);
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
        color: var(--sidebar-text);
        font-size: 0.9rem;
        line-height: 1.2;
    }
    .sidebar-account-section .role-label {
        font-size: var(--font-size-caption);
        color: var(--sidebar-muted);
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .sidebar-account-section .location-row {
        font-size: var(--font-size-caption);
        color: var(--sidebar-muted);
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }
    .sidebar-account-section .location-pin {
        opacity: 0.7;
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
        color: var(--sidebar-muted);
        letter-spacing: 0.04em;
    }
    .sidebar-user-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: var(--sidebar-account-bg);
        border: 1px solid var(--sidebar-account-border);
        border-radius: var(--radius-sm);
        padding: 0.25rem 0.5rem;
        font-size: 0.85rem;
        color: var(--sidebar-text);
    }
    .sidebar-user-initials {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: var(--sidebar-avatar-bg);
        color: var(--sidebar-avatar-fg);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: var(--font-size-caption);
        font-weight: 600;
    }

    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        background: var(--sidebar-account-bg) !important;
        border-color: var(--sidebar-active-border) !important;
    }
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] * {
        color: var(--sidebar-text) !important;
    }
"""

SIDEBAR_GRADIENT_REFINEMENT = ""
