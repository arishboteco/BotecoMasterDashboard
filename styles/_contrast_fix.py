"""High-priority contrast fixes for Streamlit-rendered labels and controls.

Streamlit often wraps visible control labels in nested `p` and `span` nodes.
This file is loaded after the visual polish layer so button, tab, sidebar and
form text inherits the intended foreground color in every state.
"""

CONTRAST_FIX = r"""    /* ── Contrast safety layer ─────────────────────────────── */

    :root,
    .stApp,
    .stApp.stAppDark,
    .stApp.stAppDarkTheme {
        --brand: #005AAB;
        --brand-dark: #004080;
        --brand-light: #2D7AC9;
        --brand-soft: #EBF4FF;
        --surface: #FFFFFF;
        --surface-elevated: #FFFFFF;
        --surface-muted: #F6FAFE;
        --text: #1E293B;
        --text-secondary: #475569;
        --text-muted: #64748B;
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;
    }

    .stApp,
    .main,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stHeader"] {
        background: #FFFFFF !important;
        color: var(--text) !important;
    }

    /* Base text: keep body copy dark enough on white cards. */
    .stMarkdown,
    .stMarkdown p,
    .stMarkdown li,
    .stMarkdown span,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stText"],
    [data-testid="stText"] p,
    [data-testid="stText"] span {
        color: var(--text) !important;
    }
    .stCaption,
    [data-testid="stCaption"],
    [data-testid="stCaptionContainer"],
    .microtext,
    .page-hero-subtitle,
    .section-block-subtitle,
    .ux-panel-subtitle,
    .info-banner-text {
        color: var(--text-secondary) !important;
    }
    a,
    .stMarkdown a,
    [data-testid="stMarkdownContainer"] a {
        color: var(--brand-dark) !important;
        font-weight: 600;
    }

    /* Buttons: force nested Streamlit labels to inherit the button foreground. */
    .stButton > button,
    .stDownloadButton > button,
    .stFormSubmitButton > button {
        background: #FFFFFF !important;
        color: var(--text) !important;
        border: 1px solid var(--border-medium) !important;
    }
    .stButton > button p,
    .stButton > button span,
    .stDownloadButton > button p,
    .stDownloadButton > button span,
    .stFormSubmitButton > button p,
    .stFormSubmitButton > button span {
        color: inherit !important;
    }
    .stButton > button:hover,
    .stDownloadButton > button:hover,
    .stFormSubmitButton > button:hover {
        background: var(--brand-soft) !important;
        color: var(--brand-dark) !important;
        border-color: var(--brand-light) !important;
    }
    .stButton > button[kind="primary"],
    .stDownloadButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: var(--brand) !important;
        color: #FFFFFF !important;
        border-color: var(--brand) !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stDownloadButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {
        background: var(--brand-dark) !important;
        color: #FFFFFF !important;
        border-color: var(--brand-dark) !important;
    }
    .stButton > button:disabled,
    .stDownloadButton > button:disabled,
    .stFormSubmitButton > button:disabled {
        background: #F1F5F9 !important;
        color: #64748B !important;
        border-color: #CBD5E1 !important;
        box-shadow: none !important;
    }

    /* Tabs: active labels must stay white; inactive labels must stay readable. */
    button[data-baseweb="tab"],
    button[data-baseweb="tab"] p,
    button[data-baseweb="tab"] span {
        color: var(--text-secondary) !important;
    }
    button[data-baseweb="tab"]:hover,
    button[data-baseweb="tab"]:hover p,
    button[data-baseweb="tab"]:hover span {
        color: var(--brand-dark) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"],
    button[data-baseweb="tab"][aria-selected="true"] p,
    button[data-baseweb="tab"][aria-selected="true"] span {
        color: #FFFFFF !important;
    }

    /* Forms and BaseWeb controls: prevent dark-mode inherited text. */
    label,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span {
        color: var(--text-secondary) !important;
    }
    input,
    textarea,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea,
    [data-baseweb="select"],
    [data-baseweb="select"] div,
    [data-baseweb="select"] span {
        color: var(--text) !important;
    }
    input::placeholder,
    textarea::placeholder {
        color: var(--text-muted) !important;
        opacity: 1 !important;
    }

    /* Sidebar: light sidebar with readable text, but preserve white text on blue avatar. */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background: #FFFFFF !important;
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span {
        color: var(--text-secondary) !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6,
    [data-testid="stSidebar"] strong,
    .sidebar-account-section .user-name {
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] .sidebar-user-initials,
    [data-testid="stSidebar"] .sidebar-user-initials span {
        background: var(--brand) !important;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] .stButton > button p,
    [data-testid="stSidebar"] .stButton > button span {
        color: var(--brand-dark) !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover,
    [data-testid="stSidebar"] .stButton > button:hover p,
    [data-testid="stSidebar"] .stButton > button:hover span {
        color: var(--brand-dark) !important;
    }

    /* Status surfaces: keep semantic text readable. */
    .success-box,
    .success-box * {
        color: var(--success-text) !important;
    }
    .error-box,
    .error-box * {
        color: var(--error-text) !important;
    }
    .info-box,
    .info-box * {
        color: var(--info-text) !important;
    }

    /* Data tables: clear contrast for headers and cells. */
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] th * {
        color: var(--brand-dark) !important;
    }
    [data-testid="stDataFrame"] td,
    [data-testid="stDataFrame"] td * {
        color: var(--text) !important;
    }

"""
