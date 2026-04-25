"""Base typography, scrollbar, focus, background, section headers, tab bar, form inputs."""

BASE_TYPOGRAPHY = r"""    /* ── Base typography ────────────────────────────────────── */
    .stMarkdown p, .stMarkdown li, .stMarkdown span, .stMarkdown label,
    [data-testid="stText"] p, [data-testid="stText"] li, [data-testid="stText"] span,
    .stTextInput input, .stTextArea textarea, .stSelectbox select,
    .stNumberInput input {
        font-family: var(--font-body) !important;
    }
    h1, h2, h3, h4,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4,
    [data-testid="stMarkdown"] h1, [data-testid="stMarkdown"] h2,
    [data-testid="stMarkdown"] h3, [data-testid="stMarkdown"] h4,
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4 {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        margin-bottom: 0.5em !important;
    }
    h1, .stMarkdown h1, [data-testid="stMarkdownContainer"] h1 { font-size: 1.85rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
    h2, .stMarkdown h2, [data-testid="stMarkdownContainer"] h2 { font-size: 1.4rem !important; font-weight: 600 !important; letter-spacing: -0.01em !important; }
    h3, .stMarkdown h3, [data-testid="stMarkdownContainer"] h3 { font-size: 1.15rem !important; font-weight: 600 !important; }
    /* Accent left-border for section headers (applies to h2 and h3 alike) */
    h2, h3,
    .stMarkdown h2, .stMarkdown h3,
    [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {
        padding-left: 0.75rem !important;
        border-left: 3px solid var(--brand) !important;
    }
    h4, .stMarkdown h4, [data-testid="stMarkdownContainer"] h4 { font-size: 1.05rem !important; font-weight: 600 !important; }
    button[data-baseweb="tab"] {
        font-family: var(--font-body) !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em;
        padding: var(--tab-padding-y) var(--tab-padding-x) !important;
        color: var(--text-muted) !important;
        transition: color var(--transition-normal) ease, background-color var(--transition-normal) ease !important;
    }
    button[data-baseweb="tab"]:hover {
        color: var(--brand) !important;
        background-color: var(--brand-soft) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--brand) !important;
        font-weight: 600 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: var(--brand) !important;
    }
    [data-testid="stTabs"] [role="tablist"] {
        border-bottom: 2px solid var(--border-subtle);
        gap: 0;
    }
    .stCaption, [data-testid="stCaption"], caption {
        color: var(--text-muted) !important;
        font-size: 0.85rem !important;
        font-family: var(--font-body) !important;
    }

"""

BRANDED_HEADER = r"""    /* ── Branded header ─────────────────────────────────────── */
    .boteco-header {
        display: flex;
        align-items: baseline;
        gap: 0.5rem;
        padding-bottom: 0.75rem;
        margin-bottom: 0.25rem;
        border-bottom: 2px solid var(--border-subtle);
    }
    .boteco-header-name {
        font-family: var(--font-display);
        font-weight: 700;
        font-size: 1.5rem;
        color: var(--brand);
        letter-spacing: -0.02em;
    }
    .boteco-header-dot {
        color: var(--brand);
        font-size: 1.5rem;
        line-height: 1;
    }
    .boteco-header-sub {
        font-family: var(--font-body);
        font-weight: 500;
        font-size: 0.9rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

"""

LAYOUT_SPACING = r"""    /* ── Layout & spacing ──────────────────────────────────── */
    :root {
        --space-hero-y: 1.15rem;
        --space-section-y: 1.35rem;
        --space-card-padding: 0.95rem;
        --space-context-band-y: 0.65rem;
        --type-table-header: 0.78rem;
        --type-microtext: 0.74rem;
    }
    .main .block-container {
        max-width: 1200px;
        padding: 1.1rem 1.5rem 1.75rem !important;
    }
    .page-hero {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-lg);
        background: linear-gradient(135deg, var(--surface-elevated), var(--surface-muted));
        padding: var(--space-hero-y) 1.1rem;
        margin-bottom: var(--space-section-y);
        box-shadow: var(--shadow-sm);
    }
    .page-hero-kicker {
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-muted);
        font-size: 0.72rem;
        font-weight: 600;
    }
    .page-hero-title {
        margin: 0.15rem 0;
        font-size: 1.35rem;
        color: var(--text);
        border-left: none !important;
        padding-left: 0 !important;
    }
    .page-hero-subtitle {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.9rem;
    }
    .page-hero-context {
        border: 1px solid var(--border-medium);
        background: var(--surface-elevated);
        border-radius: 999px;
        color: var(--text-secondary);
        font-size: 0.78rem;
        font-weight: 600;
        padding: 0.35rem 0.7rem;
        white-space: nowrap;
    }
    .section-stack {
        margin-top: var(--space-section-y);
    }
    .section-stack:first-child {
        margin-top: 0;
    }

"""

SCROLLBAR_STYLING = r"""    /* ── Scrollbar styling ──────────────────────────────────── */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--surface);
        border-radius: var(--radius-sm);
    }
    ::-webkit-scrollbar-thumb {
        background: var(--border-medium);
        border-radius: var(--radius-sm);
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }

"""

FOCUS_RINGS = r"""    /* ── Focus rings ───────────────────────────────────────── */
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox [data-baseweb="select"]:focus-within {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(63,167,163,0.25) !important;
    }

"""

SUBTLE_BACKGROUND_TEXTURE = r"""    /* ── Subtle background texture ────────────────────────── */
    .main {
        background:
            radial-gradient(ellipse at 0% 0%, rgba(31,95,168,0.03) 0%, transparent 50%),
            radial-gradient(ellipse at 100% 100%, rgba(63,167,163,0.03) 0%, transparent 50%),
            var(--surface-elevated);
    }

"""

SECTION_HEADERS_REFINED_STYLING = r"""    /* ── Section headers — refined styling (h2, h3) ─────── */
    h2, h3,
    .stMarkdown h2, .stMarkdown h3,
    [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding-left: 0.75rem !important;
        border-left: 3px solid var(--brand) !important;
        margin-top: 1.25rem !important;
    }

"""

TAB_BAR_REFINEMENT = r"""    /* ── Tab bar refinement ────────────────────────────────── */
    button[data-baseweb="tab"] {
        letter-spacing: 0.01em !important;
        min-height: 44px !important;
    }
    [data-testid="stTabs"] [role="tablist"] {
        border-bottom: 2px solid var(--border-subtle) !important;
        padding-bottom: 0 !important;
        margin-bottom: 1rem;
        gap: 0.25rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--brand-soft) !important;
        border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    }
    [data-testid="stTabs"] [role="tab"] p {
        font-weight: 600 !important;
    }
    /* Dark mode: brighten tab hover/selected foreground for WCAG AA */
    :root[data-theme="dark"] button[data-baseweb="tab"]:hover,
    :root[data-theme="dark"] button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--brand-light) !important;
    }
    @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) button[data-baseweb="tab"]:hover,
        :root:not([data-theme="light"]) button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--brand-light) !important;
        }
    }

"""

COMPREHENSIVE_FOCUS_INDICATORS = r"""    /* ── Comprehensive focus indicators (WCAG 2.1 AA) ──── */
    a:focus-visible,
    button:focus-visible,
    input:focus-visible,
    select:focus-visible,
    textarea:focus-visible,
    [role="button"]:focus-visible,
    [role="link"]:focus-visible,
    [role="checkbox"]:focus-visible,
    [role="switch"]:focus-visible,
    [role="tab"]:focus-visible,
    [role="menuitem"]:focus-visible,
    [role="listbox"]:focus-visible,
    [role="combobox"]:focus-visible,
    [tabindex]:focus-visible {
        outline: 2px solid var(--brand) !important;
        outline-offset: 2px !important;
        border-radius: var(--radius-sm) !important;
    }
    .stButton > button:focus-visible {
        outline: 2px solid var(--brand) !important;
        outline-offset: 3px !important;
    }
    /* Remove default browser outline but keep :focus-visible (keyboard) */
    button:focus:not(:focus-visible),
    a:focus:not(:focus-visible),
    [tabindex]:focus:not(:focus-visible) {
        outline: none;
    }
"""

INLINE_HTML_UTILITIES = r"""    /* ── Inline HTML replacement utility classes ─────────────── */
    .delta-chip {
        font-size: 0.8rem;
        font-weight: 600;
    }
    .delta-chip--positive {
        color: var(--success-text);
    }
    .delta-chip--negative {
        color: var(--error-text);
    }
    .microtext {
        font-size: var(--type-microtext);
        color: var(--text-muted);
        letter-spacing: 0.01em;
    }
    .context-band {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem 1.2rem;
        align-items: center;
        background: var(--surface-muted);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: var(--space-context-band-y) var(--space-card-padding);
        margin: 0.35rem 0 var(--space-section-y) 0;
        color: var(--text-secondary);
        font-size: 0.84rem;
    }
    .context-band strong {
        color: var(--text);
        font-weight: 600;
    }
    .context-band--muted {
        opacity: 0.95;
    }
    .context-band-item {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .report-comparison-bar {
        display: inline-flex;
        flex-wrap: wrap;
        gap: 0.6rem;
        color: var(--text-secondary);
        font-size: 0.84rem;
    }

"""
