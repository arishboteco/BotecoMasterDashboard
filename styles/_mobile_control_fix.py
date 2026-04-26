"""Mobile and BaseWeb control consistency fixes.

Targets the specific Streamlit controls that can keep dark-mode styling on
mobile even after the app shell is forced to a light brand theme.
"""

MOBILE_CONTROL_FIX = r"""    /* ── Mobile/control consistency layer ─────────────────── */

    /* Mobile browser + Streamlit chrome can leave a dark header behind; keep
       only the embedded Streamlit management bar dark, not app controls. */
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > section,
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .main,
    .main .block-container {
        background: #FFFFFF !important;
        color: var(--text) !important;
    }

    /* Icon wrappers use a glyph plus safe fallback. The fallback is hidden when
       Material Symbols loads; if it does not, CSS keeps raw ligature text from
       expanding into headings such as `upload_file Step 1`. */
    .section-block-icon,
    .info-banner-icon,
    .filter-strip-icon {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        flex: 0 0 1.35rem !important;
        width: 1.35rem !important;
        height: 1.35rem !important;
        color: var(--brand) !important;
        line-height: 1 !important;
        overflow: hidden !important;
    }
    .section-block-icon__glyph,
    .info-banner-icon__glyph,
    .filter-strip-icon__glyph {
        font-family: 'Material Symbols Outlined' !important;
        font-size: 1.15rem !important;
        line-height: 1 !important;
        color: var(--brand) !important;
        max-width: 1.35rem !important;
        overflow: hidden !important;
        white-space: nowrap !important;
    }
    .section-block-icon__fallback,
    .info-banner-icon__fallback,
    .filter-strip-icon__fallback {
        display: none !important;
        color: var(--brand) !important;
        font-family: var(--font-body) !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        line-height: 1 !important;
    }
    .section-block-title {
        color: var(--text) !important;
        gap: 0.55rem !important;
    }
    .section-block-title > span:not(.section-block-icon),
    .section-block-title p {
        color: var(--text) !important;
    }

    @supports not (font-variation-settings: 'FILL' 0) {
        .section-block-icon__glyph,
        .info-banner-icon__glyph,
        .filter-strip-icon__glyph {
            display: none !important;
        }
        .section-block-icon__fallback,
        .info-banner-icon__fallback,
        .filter-strip-icon__fallback {
            display: inline-flex !important;
        }
    }

    /* Selectbox: BaseWeb uses several nested layers. Force light theme for
       the closed control, placeholder, selected value, arrow and menu. */
    .stSelectbox,
    .stMultiSelect {
        color: var(--text) !important;
    }
    .stSelectbox [data-baseweb="select"],
    .stMultiSelect [data-baseweb="select"] {
        background: #FFFFFF !important;
        border: 1px solid var(--border-medium) !important;
        border-radius: var(--radius-md) !important;
        box-shadow: var(--shadow-sm) !important;
        min-height: 42px !important;
    }
    .stSelectbox [data-baseweb="select"] *,
    .stMultiSelect [data-baseweb="select"] * {
        color: var(--text) !important;
        opacity: 1 !important;
        -webkit-text-fill-color: var(--text) !important;
    }
    .stSelectbox [data-baseweb="select"] input,
    .stMultiSelect [data-baseweb="select"] input {
        border: 0 !important;
        outline: 0 !important;
        box-shadow: none !important;
        background: transparent !important;
        padding: 0 !important;
        min-height: 0 !important;
        caret-color: transparent !important;
    }
    .stSelectbox [data-baseweb="select"] input:focus,
    .stSelectbox [data-baseweb="select"] input:focus-visible,
    .stMultiSelect [data-baseweb="select"] input:focus,
    .stMultiSelect [data-baseweb="select"] input:focus-visible {
        border: 0 !important;
        outline: 0 !important;
        box-shadow: none !important;
    }
    .stSelectbox [data-baseweb="select"] svg,
    .stMultiSelect [data-baseweb="select"] svg {
        color: var(--text-muted) !important;
        fill: var(--text-muted) !important;
    }
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"],
    [role="listbox"] {
        background: #FFFFFF !important;
        color: var(--text) !important;
        border-color: var(--border-subtle) !important;
    }
    [data-baseweb="menu"] li,
    [role="option"],
    [role="option"] * {
        color: var(--text) !important;
        background: #FFFFFF !important;
        opacity: 1 !important;
        font-weight: 500 !important;
        -webkit-text-fill-color: var(--text) !important;
    }
    [data-baseweb="menu"] li:hover,
    [role="option"]:hover,
    [aria-selected="true"][role="option"] {
        background: var(--brand-soft) !important;
        color: var(--brand-dark) !important;
        -webkit-text-fill-color: var(--brand-dark) !important;
    }

    /* Sidebar selectbox had dark background with almost invisible text in the
       screenshot. Make it match the light sidebar. */
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"],
    [data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"] {
        background: #FFFFFF !important;
        border: 1px solid var(--border-medium) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    [data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] *,
    [data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"] * {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        opacity: 1 !important;
    }

    /* File uploader: avoid the dark mobile uploader block. */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploaderDropzone"],
    .upload-zone-container [data-testid="stFileUploaderDropzone"] {
        background: #FFFFFF !important;
        color: var(--text) !important;
        border-color: rgba(0, 90, 171, 0.38) !important;
    }
    [data-testid="stFileUploaderDropzone"] *,
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] p {
        color: var(--text-secondary) !important;
        -webkit-text-fill-color: var(--text-secondary) !important;
        opacity: 1 !important;
    }
    [data-testid="stFileUploaderDropzone"] button,
    [data-testid="stFileUploaderDropzone"] [role="button"] {
        background: #FFFFFF !important;
        color: var(--brand-dark) !important;
        border: 1px solid rgba(0, 90, 171, 0.24) !important;
        border-radius: var(--radius-md) !important;
    }
    [data-testid="stFileUploaderDropzone"] button *,
    [data-testid="stFileUploaderDropzone"] [role="button"] * {
        color: var(--brand-dark) !important;
        -webkit-text-fill-color: var(--brand-dark) !important;
    }
    [data-testid="stFileUploaderDropzone"] svg {
        color: var(--brand) !important;
        fill: var(--brand) !important;
    }

    /* Expander rows: keep icon and label in one readable row. */
    [data-testid="stExpander"] {
        background: #FFFFFF !important;
        color: var(--text) !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: var(--brand-soft) !important;
    }

    /* Tabs on mobile: remove faint/low-contrast active label from the first
       screenshot and make the selected tab obvious but not heavy. */
    [data-testid="stTabs"] [role="tablist"] {
        background: #FFFFFF !important;
        border: 1px solid var(--border-subtle) !important;
        box-shadow: var(--shadow-card) !important;
    }
    button[data-baseweb="tab"] {
        background: transparent !important;
        color: var(--text-secondary) !important;
        opacity: 1 !important;
    }
    button[data-baseweb="tab"] p,
    button[data-baseweb="tab"] span {
        color: inherit !important;
        -webkit-text-fill-color: currentColor !important;
        opacity: 1 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: var(--brand) !important;
        color: #FFFFFF !important;
        box-shadow: inset 0 -3px 0 var(--accent-amber) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p,
    button[data-baseweb="tab"][aria-selected="true"] span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* Mobile sidebar overlay: keep full-width drawer white and avoid a harsh
       split between drawer and page. */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] {
        background: #FFFFFF !important;
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid var(--border-subtle) !important;
        box-shadow: 12px 0 32px rgba(15, 23, 42, 0.10) !important;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: var(--text-secondary) !important;
        -webkit-text-fill-color: currentColor !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] .sidebar-account-section {
        background: var(--brand-soft) !important;
        border-color: rgba(0, 90, 171, 0.18) !important;
    }
    [data-testid="stSidebar"] .sidebar-account-section .user-name,
    [data-testid="stSidebar"] .sidebar-account-section strong {
        color: var(--brand-dark) !important;
        -webkit-text-fill-color: var(--brand-dark) !important;
    }
    [data-testid="stSidebar"] .sidebar-user-initials,
    [data-testid="stSidebar"] .sidebar-user-initials * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .page-hero {
            margin-top: 0.8rem !important;
            padding: 1rem !important;
            border-radius: 16px !important;
        }
        .page-hero-title {
            font-size: 1.35rem !important;
        }
        .page-hero-subtitle {
            font-size: 0.98rem !important;
            line-height: 1.5 !important;
        }
        .page-hero-context {
            width: 100% !important;
            justify-content: center !important;
            text-align: center !important;
        }
        [data-testid="stTabs"] [role="tablist"] {
            border-radius: 14px !important;
            padding: 0.25rem !important;
            gap: 0.2rem !important;
        }
        button[data-baseweb="tab"] {
            min-width: max-content !important;
            padding: 0.55rem 0.85rem !important;
        }
        [data-testid="stFileUploaderDropzone"] {
            min-height: 132px !important;
            border-radius: 14px !important;
        }
        [data-testid="stSidebar"] img {
            max-width: 100% !important;
            height: auto !important;
        }
    }

"""
