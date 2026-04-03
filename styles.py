"""Centralized CSS token system and style generation for Boteco Dashboard."""

from __future__ import annotations


def get_css() -> str:
    """Return the complete CSS stylesheet for the dashboard."""
    return """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

    /* Force system fonts for Streamlit expander icons */
    section[data-testid="stExpander"] * {
        font-family: inherit !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] button {
        font-family: inherit !important;
    }
    summary {
        font-family: inherit !important;
    }

    /* ── Token system ─────────────────────────────────────────── */
    :root {
        /* Brand palette */
        --brand: #1F5FA8;
        --brand-dark: #174A82;
        --brand-light: #2A6BB3;
        --brand-soft: #E6F4F3;

        /* Surface palette */
        --surface: #F7FAFC;
        --surface-elevated: #FFFFFF;
        --surface-raised: #FFFFFF;
        --sidebar-bg: #1F5FA8;
        --sidebar-border: #2A6BB3;

        /* Text palette */
        --text: #1E293B;
        --text-secondary: #475569;
        --text-muted: #64748B;

        /* Border palette */
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;

        /* Accent colors */
        --accent-coral: #1F5FA8;
        --accent-teal: #3FA7A3;
        --accent-amber: #F4B400;
        --accent-indigo: #6DBE45;
        --accent-slate: #1F5FA8;

        /* Semantic colors */
        --success-bg: #F0FDF4;
        --success-text: #15803D;
        --success-border: #BBF7D0;
        --error-bg: #FEF2F2;
        --error-text: #B91C1C;
        --error-border: #FECACA;
        --info-bg: #EFF6FF;
        --info-text: #4338CA;
        --info-border: #C7D2FE;

        /* Typography */
        --font-display: 'Plus Jakarta Sans', sans-serif;
        --font-body: 'Inter', sans-serif;
        --font-size-xs: 12px;
        --font-size-sm: 14px;
        --font-size-base: 16px;
        --font-size-lg: 18px;

        /* Spacing scale (4px base) */
        --spacing-xs: 4px;
        --spacing-sm: 8px;
        --spacing-md: 16px;
        --spacing-lg: 24px;
        --spacing-xl: 32px;

        /* Shadows */
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.05);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.04);

        /* Border radius */
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;

        /* Button heights */
        --btn-height-sm: 32px;
        --btn-height-md: 40px;
        --btn-height-lg: 48px;
        --btn-padding-x: 1rem;
        --btn-padding-y: 0.5rem;

        /* Icon */
        --icon-size: 18px;

        /* Z-index scale */
        --z-index-dropdown: 10;
        --z-index-modal: 100;
        --z-index-toast: 1000;

        /* Transitions */
        --transition-fast: 150ms;
        --transition-normal: 200ms;
    }

    /* ── Base typography ────────────────────────────────────── */
    .stMarkdown p, .stMarkdown li, .stMarkdown span, .stMarkdown label,
    [data-testid="stText"] p, [data-testid="stText"] li, [data-testid="stText"] span,
    .stTextInput input, .stTextArea textarea, .stSelectbox select,
    .stNumberInput input {
        font-family: var(--font-body) !important;
    }
    h1, h2, h3, h4 {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        margin-bottom: 0.5em !important;
    }
    h1 { font-size: 1.85rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
    h2 { font-size: 1.4rem !important; font-weight: 600 !important; letter-spacing: -0.01em !important; }
    h3 {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        padding-left: 0.75rem !important;
        border-left: 3px solid var(--brand) !important;
    }
    h4 { font-size: 1.05rem !important; font-weight: 600 !important; }
    button[data-baseweb="tab"] {
        font-family: var(--font-body) !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em;
        padding: 0.75rem 1.25rem !important;
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

    /* ── Branded header ─────────────────────────────────────── */
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

    /* ── Button system ──────────────────────────────────────── */
    .stButton > button {
        font-family: var(--font-body) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: all var(--transition-normal) ease !important;
        min-height: var(--btn-height-md) !important;
        line-height: 1.4 !important;
        padding: var(--btn-padding-y) var(--btn-padding-x) !important;
    }
    .stButton > button:active {
        transform: scale(0.98) !important;
        transition: transform var(--transition-fast) ease !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--brand) !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--brand-dark) !important;
        box-shadow: var(--shadow-md) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border-subtle) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: var(--brand-soft) !important;
        border-color: var(--brand) !important;
        color: var(--brand-dark) !important;
    }
    .stButton > button.destructive {
        background-color: transparent !important;
        color: var(--error-text) !important;
        border: 1.5px solid var(--error-border) !important;
    }
    .stButton > button.destructive:hover {
        background-color: var(--error-bg) !important;
        border-color: var(--error-text) !important;
    }
    .stButton > button.destructive:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }

    /* ── KPI metric values ──────────────────────────────────── */
    div[data-testid="stMetricValue"] {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        font-weight: 700 !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
    }
    div[data-testid="stMetricLabel"] {
        font-family: var(--font-body) !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        font-size: 0.75rem !important;
        letter-spacing: 0.03em;
    }
    div[data-testid="stMetricDelta"] {
        font-family: var(--font-body) !important;
        font-weight: 600 !important;
    }

    /* ── Compact KPIs for Report tab ───────────────────────── */
    .kpi-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0.35rem 0.5rem;
        border-radius: var(--radius-sm);
        background: var(--surface);
        border: 1px solid var(--border-subtle);
        text-align: center;
        gap: 0.1rem;
        min-height: 2.8rem;
    }
    .kpi-item.kpi-combined {
        border-left: 3px solid var(--accent-coral);
    }
    .kpi-label {
        font-family: var(--font-body) !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        font-size: 0.55rem !important;
        letter-spacing: 0.04em;
        line-height: 1;
    }
    .kpi-value {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        line-height: 1.1;
        word-break: break-word;
    }
    .kpi-delta {
        font-family: var(--font-body) !important;
        color: var(--text-secondary) !important;
        font-size: 0.55rem !important;
        font-weight: 500 !important;
        line-height: 1;
    }

    /* ── Metric accent classes (replaces fragile nth-child) ── */
    .metric-accent-coral .stMetric,
    [data-testid="stVerticalBlockBorderWrapper"] .metric-accent-coral [data-testid="stMetric"] {
        border-left: 4px solid var(--accent-coral) !important;
    }
    .metric-accent-teal .stMetric,
    [data-testid="stVerticalBlockBorderWrapper"] .metric-accent-teal [data-testid="stMetric"] {
        border-left: 4px solid var(--accent-teal) !important;
    }
    .metric-accent-amber .stMetric,
    [data-testid="stVerticalBlockBorderWrapper"] .metric-accent-amber [data-testid="stMetric"] {
        border-left: 4px solid var(--accent-amber) !important;
    }
    .metric-accent-indigo .stMetric,
    [data-testid="stVerticalBlockBorderWrapper"] .metric-accent-indigo [data-testid="stMetric"] {
        border-left: 4px solid var(--accent-indigo) !important;
    }
    .metric-accent-slate .stMetric,
    [data-testid="stVerticalBlockBorderWrapper"] .metric-accent-slate [data-testid="stMetric"] {
        border-left: 4px solid var(--accent-slate) !important;
    }

    /* ── Metric cards & containers ──────────────────────────── */
    .metric-card {
        background: var(--surface);
        padding: 1rem;
        border-radius: var(--radius-lg);
        border-left: 4px solid var(--brand);
        box-shadow: var(--shadow-sm);
        transition: transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border-color: var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-sm) !important;
        transition: transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: var(--shadow-md) !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--surface);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-subtle);
        border-left: 4px solid var(--accent-coral);
        padding: 0.85rem;
        transition: transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }

    /* ── Alert / status boxes ───────────────────────────────── */
    .success-box {
        background: var(--success-bg);
        color: var(--success-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--success-border);
    }
    .error-box {
        background: var(--error-bg);
        color: var(--error-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--error-border);
    }
    .info-box {
        background: var(--info-bg);
        color: var(--info-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--info-border);
    }

    /* ── Upload zone ────────────────────────────────────────── */
    .upload-zone {
        border: 2px dashed var(--brand);
        border-radius: var(--radius-lg);
        padding: 1rem 1.25rem;
        text-align: left;
        background: var(--surface);
        margin-bottom: 0.75rem;
        transition: border-color var(--transition-normal) ease, background-color var(--transition-normal) ease, box-shadow var(--transition-normal) ease, transform var(--transition-normal) ease;
    }
    .upload-zone:hover {
        border-color: var(--brand-dark);
        background: var(--brand-soft);
        box-shadow: 0 0 0 4px rgba(31,95,168,0.1);
        transform: translateY(-1px);
    }
    .empty-upload-hint {
        color: var(--text-muted);
        font-size: 0.95rem;
        padding: 0.75rem 1rem;
        background: var(--surface);
        border-radius: var(--radius-sm);
        border: 1px dashed var(--border-subtle);
        margin-top: 0.5rem;
    }

    /* ── Data tables ────────────────────────────────────────── */
    [data-testid="stDataFrame"] th {
        font-family: var(--font-body) !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        color: #1F5FA8 !important;
        background-color: #EEF2F7 !important;
        border-bottom: none !important;
    }
    [data-testid="stDataFrame"] {
        border-radius: var(--radius-md) !important;
        overflow: hidden !important;
        border: 1px solid var(--border-subtle) !important;
    }
    [data-testid="stDataFrame"] td {
        font-family: var(--font-body) !important;
        font-size: 0.875rem !important;
    }
    [data-testid="stDataFrame"] tr:nth-child(even) {
        background-color: var(--surface-elevated) !important;
    }
    [data-testid="stDataFrame"] tr:hover {
        background-color: var(--brand-soft) !important;
    }

    /* ── Expander labels ────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        gap: 0.65rem;
        align-items: center;
        padding: 0.5rem 0.75rem;
        border-radius: var(--radius-sm);
        transition: background-color var(--transition-normal) ease;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: var(--brand-soft);
    }
    [data-testid="stExpander"] summary p {
        margin: 0;
        overflow: visible;
        line-height: 1.5;
        font-family: var(--font-body) !important;
    }
    [data-testid="stExpander"] svg {
        flex-shrink: 0;
        margin-right: 0.25rem;
        transition: transform var(--transition-normal) ease;
    }
    [data-testid="stExpander"][open] summary svg {
        transform: rotate(90deg);
    }

    /* ── Sidebar ────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }
    [data-testid="stSidebar"] hr {
        margin: 1rem 0;
        border-color: var(--border-subtle);
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

    /* ── Date navigation ────────────────────────────────────── */
    .date-nav-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
        padding: 0.75rem 0;
    }
    .date-nav-btn {
        min-width: 90px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.4rem;
    }
    .date-display {
        font-family: var(--font-display);
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--text);
        text-align: center;
        min-width: 200px;
        padding: 0.5rem 1.25rem;
        background: var(--surface);
        border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle);
        box-shadow: var(--shadow-sm);
    }

    /* ── WhatsApp share buttons ─────────────────────────────── */
    .whatsapp-btn-container {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        min-height: var(--btn-height-md);
    }
    .whatsapp-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: var(--btn-padding-y) var(--btn-padding-x);
        border-radius: var(--radius-sm);
        font-family: var(--font-body);
        font-weight: 600;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all var(--transition-normal) ease;
        white-space: nowrap;
        line-height: 1.3;
        min-height: var(--btn-height-md);
    }
    .whatsapp-btn-primary {
        background: var(--brand);
        color: #FFFFFF;
        border: none;
        box-shadow: var(--shadow-sm);
    }
    .whatsapp-btn-primary:hover {
        background: var(--brand-dark);
        box-shadow: var(--shadow-md);
    }
    .whatsapp-btn-secondary {
        background: var(--surface);
        color: var(--text);
        border: 1px solid var(--border-subtle);
    }
    .whatsapp-btn-secondary:hover {
        background: var(--brand-soft);
        border-color: var(--brand);
        color: var(--brand-dark);
    }
    .whatsapp-icon {
        width: var(--icon-size);
        height: var(--icon-size);
        flex-shrink: 0;
    }
    .whatsapp-msg {
        font-size: 0.8rem;
        color: var(--success-text);
        margin-left: 0.5rem;
    }

    /* ── Icon-only action buttons ──────────────────────────── */
    .action-btn-row {
        display: inline-flex;
        align-items: center;
        gap: 0;
        background: var(--surface);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-sm);
        padding: var(--spacing-xs);
    }
    .action-btn-row .action-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        padding: 0;
        border-radius: var(--spacing-xs);
        cursor: pointer;
        transition: all var(--transition-normal) ease;
        border: none;
        background: transparent;
        color: var(--text-secondary);
        font-size: 0;
    }
    .action-btn-row .action-btn:hover {
        background: var(--brand-soft);
        color: var(--brand);
    }
    .action-btn-row .action-btn + .action-btn {
        border-left: 1px solid var(--border-subtle);
    }
    .action-btn-row .action-btn svg {
        width: var(--icon-size);
        height: var(--icon-size);
        display: block;
    }

    /* ── Upload zone styling ───────────────────────────────── */
    .upload-zone-container {
        position: relative;
    }
    .upload-zone-container .stFileUploader > div:first-child {
        padding: 0 !important;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"] {
        min-height: 140px;
        border: 2px dashed var(--brand) !important;
        border-radius: var(--radius-lg) !important;
        background: var(--surface) !important;
        transition: all var(--transition-normal) ease;
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--brand-dark) !important;
        background: var(--brand-soft) !important;
        box-shadow: 0 0 0 4px rgba(31,95,168,0.1) !important;
        transform: translateY(-1px);
    }
    .upload-zone-container [data-testid="stFileUploaderDropzone"] label {
        color: var(--text-secondary) !important;
        font-size: 0.95rem !important;
        font-family: var(--font-body) !important;
    }

    /* ── Section dividers ───────────────────────────────────── */
    .section-divider {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, var(--border-subtle), transparent);
        margin: 2rem 0;
    }

    /* ── Layout & spacing ──────────────────────────────────── */
    .main .block-container {
        max-width: 1200px;
        padding: 1.5rem 2rem 2rem !important;
    }

    /* ── Scrollbar styling ──────────────────────────────────── */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--surface);
        border-radius: var(--spacing-xs);
    }
    ::-webkit-scrollbar-thumb {
        background: var(--border-medium);
        border-radius: var(--spacing-xs);
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }

    /* ── Focus rings ───────────────────────────────────────── */
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox [data-baseweb="select"]:focus-within {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(63,167,163,0.25) !important;
    }

    /* ── Responsive breakpoints ────────────────────────────── */
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
</style>
"""


def get_login_css() -> str:
    """Return CSS specific to the login/setup pages. Reuses token system."""
    return """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');
    :root {
        --brand: #1F5FA8;
        --brand-dark: #174A82;
        --login-surface: #FFFFFF;
        --login-border: #E2E8F0;
        --text: #1E293B;
    }
    .stApp {
        background: #FFFFFF !important;
    }
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 2.5rem;
        background: var(--login-surface);
        border-radius: 14px;
        border: 1px solid var(--login-border);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    }
    .stButton > button {
        width: 100%;
        background-color: var(--brand);
        color: #FFFFFF;
        border: none;
        padding: 0.75rem;
        border-radius: 10px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: var(--brand-dark);
        box-shadow: 0 4px 6px rgba(31, 95, 168, 0.2);
    }
    .stTextInput input:focus {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(63, 167, 163, 0.25) !important;
    }
    h1 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: var(--brand) !important;
    }
    h3 {
        font-family: 'Inter', sans-serif !important;
        color: #475569 !important;
        font-weight: 500 !important;
        border-left: none !important;
        padding-left: 0 !important;
    }
</style>
"""
