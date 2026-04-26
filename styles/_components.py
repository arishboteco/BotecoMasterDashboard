"""Reusable UI components — buttons, metrics, alerts, tables, date nav, WhatsApp, actions, empty state, dividers."""

BUTTON_SYSTEM = r"""    /* ── Button system ──────────────────────────────────────── */
    .stButton > button,
    .stDownloadButton > button,
    .stFormSubmitButton > button {
        font-family: var(--font-body) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: all var(--transition-normal) ease !important;
        min-height: var(--btn-height-md) !important;
        line-height: 1.4 !important;
        padding: var(--btn-padding-y) var(--btn-padding-x) !important;
        background-color: var(--btn-default-bg) !important;
        color: var(--btn-default-fg) !important;
        border: 1px solid var(--btn-default-border) !important;
    }
    .stButton > button:hover {
        background-color: var(--btn-default-hover-bg) !important;
        color: var(--btn-default-hover-fg) !important;
        border-color: var(--btn-default-hover-border) !important;
    }
    .stButton > button:active,
    .stDownloadButton > button:active,
    .stFormSubmitButton > button:active {
        transform: scale(0.98) !important;
        transition: transform var(--transition-fast) ease !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--btn-primary-bg) !important;
        color: var(--btn-primary-fg) !important;
        border: 1px solid var(--btn-primary-border) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--btn-primary-hover-bg) !important;
        color: var(--btn-primary-hover-fg) !important;
        border-color: var(--btn-primary-hover-border) !important;
        box-shadow: var(--shadow-md) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: var(--btn-default-bg) !important;
        color: var(--btn-default-fg) !important;
        border: 1px solid var(--btn-default-border) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: var(--btn-default-hover-bg) !important;
        border-color: var(--btn-default-hover-border) !important;
        color: var(--btn-default-hover-fg) !important;
    }
    .stButton > button:disabled,
    .stDownloadButton > button:disabled,
    .stFormSubmitButton > button:disabled {
        background-color: var(--btn-disabled-bg) !important;
        color: var(--btn-disabled-fg) !important;
        border-color: var(--btn-disabled-border) !important;
        opacity: 1 !important;
        cursor: not-allowed !important;
        box-shadow: none !important;
    }
    .stDownloadButton > button {
        background-color: var(--btn-download-bg) !important;
        color: var(--btn-download-fg) !important;
        border-color: var(--btn-download-border) !important;
    }
    .stDownloadButton > button:hover {
        background-color: var(--btn-download-hover-bg) !important;
        color: var(--btn-download-hover-fg) !important;
        border-color: var(--btn-download-hover-border) !important;
    }
    .stFormSubmitButton > button {
        background-color: var(--btn-form-submit-bg) !important;
        color: var(--btn-form-submit-fg) !important;
        border-color: var(--btn-form-submit-border) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stFormSubmitButton > button:hover {
        background-color: var(--btn-form-submit-hover-bg) !important;
        color: var(--btn-form-submit-hover-fg) !important;
        border-color: var(--btn-form-submit-hover-border) !important;
        box-shadow: var(--shadow-md) !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background-color: var(--btn-sidebar-bg) !important;
        color: var(--btn-sidebar-fg) !important;
        border-color: var(--btn-sidebar-border) !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: var(--btn-sidebar-hover-bg) !important;
        color: var(--btn-sidebar-hover-fg) !important;
        border-color: var(--btn-sidebar-hover-border) !important;
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
"""

KPI_METRIC_VALUES = r"""    /* ── KPI metric values ──────────────────────────────────── */
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

"""

COMPACT_KPIS_FOR_REPORT_TAB = r"""    /* ── Compact KPIs for Report tab ───────────────────────── */
    .kpi-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 0.35rem 0.5rem;
        border-radius: var(--radius-sm);
        background: var(--card-surface-normal);
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
        color: var(--kpi-label-fg) !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        font-size: 0.75rem !important;
        letter-spacing: 0.03em;
        line-height: 1;
    }
    .kpi-value {
        font-family: var(--font-display) !important;
        color: var(--kpi-value-fg) !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        line-height: 1.1;
        word-break: break-word;
    }
    .kpi-delta {
        font-family: var(--font-body) !important;
        color: var(--kpi-delta-neutral-fg) !important;
        font-size: 0.55rem !important;
        font-weight: 500 !important;
        line-height: 1;
    }
    .kpi-delta.is-positive { color: var(--kpi-delta-positive-fg) !important; }
    .kpi-delta.is-negative { color: var(--kpi-delta-negative-fg) !important; }

"""

METRIC_CARDS_CONTAINERS = r"""    /* ── Metric cards & containers ──────────────────────────── */
    /* Shared elevated-surface base (merged from .metric-card + stMetric wrapper) */
    .metric-card,
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--card-surface-elevated);
        box-shadow: var(--shadow-sm);
        transition: transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
    }
    .metric-card:hover,
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    /* Selector-specific overrides */
    .metric-card {
        padding: var(--space-card-padding);
        border-radius: var(--radius-lg);
        border-left: 4px solid var(--brand);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--card-surface-normal) !important;
        border-color: var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-sm) !important;
        transition: transform var(--transition-normal) ease, box-shadow var(--transition-normal) ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: var(--shadow-md) !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle);
        border-left: 4px solid var(--accent-coral);
        padding: var(--space-card-padding);
    }
    .kpi-primary-card {
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-lg);
        background: var(--card-surface-kpi-primary);
        box-shadow: var(--shadow-sm);
        padding: var(--space-card-padding);
        margin-bottom: var(--space-section-y);
    }
    .kpi-secondary-card,
    .report-section-card {
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        background: var(--card-surface-report-section);
        padding: calc(var(--space-card-padding) * 0.9);
        margin-top: 0.4rem;
        margin-bottom: var(--space-section-y);
    }

"""

ALERT_STATUS_BOXES = r"""    /* ── Alert / status boxes ───────────────────────────────── */
    .success-box {
        background: var(--alert-success-bg);
        color: var(--alert-success-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--alert-success-border);
    }
    .error-box {
        background: var(--alert-error-bg);
        color: var(--alert-error-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--alert-error-border);
    }
    .warning-box {
        background: var(--alert-warning-bg);
        color: var(--alert-warning-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--alert-warning-border);
    }
    .info-box {
        background: var(--alert-info-bg);
        color: var(--alert-info-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--alert-info-border);
    }
    .neutral-box {
        background: var(--alert-neutral-bg);
        color: var(--alert-neutral-text);
        padding: 1rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--alert-neutral-border);
    }

"""

UPLOAD_ZONE = r"""    /* ── Upload zone ────────────────────────────────────────── */
    .upload-zone {
        border: 2px dashed var(--brand);
        border-radius: var(--radius-lg);
        padding: 1rem;
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

"""

DATA_TABLES = r"""    /* ── Data tables ────────────────────────────────────────── */
    [data-testid="stDataFrame"] th {
        font-family: var(--font-body) !important;
        font-weight: 600 !important;
        font-size: var(--type-table-header) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        color: var(--text-secondary) !important;
        background-color: var(--table-header-bg) !important;
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

"""

EXPANDER_LABELS = r"""    /* ── Expander labels ────────────────────────────────────── */
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

"""

DATE_NAVIGATION = r"""    /* ── Date navigation ────────────────────────────────────── */
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

"""

WHATSAPP_SHARE_BUTTONS = r"""    /* ── WhatsApp share buttons ─────────────────────────────── */
    .whatsapp-btn-container {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        min-height: var(--btn-height-md);
    }
    .whatsapp-btn-container button:focus {
        outline: 2px solid var(--brand-light);
        outline-offset: 2px;
    }
    .whatsapp-btn-container button:focus:not(:focus-visible) {
        outline: none;
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

"""

ICON_ONLY_ACTION_BUTTONS = r"""    /* ── Icon-only action buttons ──────────────────────────── */
    .action-btn-container button:focus {
        outline: 2px solid var(--brand-light);
        outline-offset: 2px;
    }
    .action-btn-container button:focus:not(:focus-visible) {
        outline: none;
    }
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
        border-radius: var(--radius-sm);
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

"""

UPLOAD_ZONE_STYLING = r"""    /* ── Upload zone styling ───────────────────────────────── */
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

"""

SECTION_DIVIDERS = r"""    /* ── Section dividers ───────────────────────────────────── */
    .section-divider {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, var(--border-subtle), transparent);
        margin: var(--spacing-xl) 0;
    }

"""

SECTION_LABELS = r"""    /* ── Section labels ───────────────────────────────────── */
    .section-label {
        font-family: var(--font-display);
        font-size: 1rem;
        font-weight: 600;
        color: var(--text);
        padding-bottom: 0.5rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-subtle);
    }

"""

WORKFLOW_AND_SURFACES = r"""    /* ── Workflow and surface polish ─────────────────────── */
    .workflow-steps {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 0.25rem 0 0.9rem;
    }
    .workflow-step {
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--border-medium);
        border-radius: 999px;
        padding: 0.28rem 0.7rem;
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--text-secondary);
        background: var(--surface-elevated);
    }
    .workflow-step.active {
        color: #FFFFFF;
        border-color: var(--brand);
        background: var(--brand);
    }
    .ux-panel-title {
        font-family: var(--font-display);
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--text);
        margin-bottom: 0.35rem;
    }
    .ux-panel-subtitle {
        margin: 0;
        color: var(--text-secondary);
        font-size: 0.84rem;
    }
    .pill-info {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--info-text);
        background: var(--info-bg);
        border: 1px solid var(--info-border);
    }
    .section-block {
        margin: 0.2rem 0 0.7rem;
    }
    .section-block-title {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-family: var(--font-display);
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--text);
    }
    .section-block-icon {
        font-size: 1.05rem !important;
        color: var(--brand);
    }
    .section-block-subtitle {
        margin: 0.12rem 0 0;
        color: var(--text-secondary);
        font-size: 0.84rem;
    }
    .info-banner {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.55rem 0.7rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--border-subtle);
        background: var(--surface);
        margin: 0.35rem 0 0.55rem;
    }
    .info-banner-icon {
        font-size: 1rem !important;
        line-height: 1;
    }
    .info-banner-text {
        font-size: 0.85rem;
        color: var(--text-secondary);
    }
    .info-banner--info {
        background: var(--alert-info-bg);
        border-color: var(--alert-info-border);
    }
    .info-banner--info .info-banner-icon,
    .info-banner--info .info-banner-text {
        color: var(--alert-info-text);
    }
    .info-banner--success {
        background: var(--alert-success-bg);
        border-color: var(--alert-success-border);
    }
    .info-banner--success .info-banner-icon,
    .info-banner--success .info-banner-text {
        color: var(--alert-success-text);
    }
    .info-banner--warning {
        background: var(--alert-warning-bg);
        border-color: var(--alert-warning-border);
    }
    .info-banner--warning .info-banner-icon,
    .info-banner--warning .info-banner-text {
        color: var(--alert-warning-text);
    }
    .info-banner--error {
        background: var(--alert-error-bg);
        border-color: var(--alert-error-border);
    }
    .info-banner--error .info-banner-icon,
    .info-banner--error .info-banner-text {
        color: var(--alert-error-text);
    }
    .filter-strip {
        display: inline-flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin: 0.05rem 0 0.5rem;
        padding: 0.32rem 0.58rem;
        border-radius: 999px;
        border: 1px solid var(--border-subtle);
        background: var(--surface-elevated);
    }
    .filter-strip-icon {
        font-size: 1rem !important;
        color: var(--brand);
    }
    .filter-strip-title {
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--text);
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .filter-strip-subtitle {
        font-size: 0.76rem;
        color: var(--text-muted);
    }

"""

EMPTY_STATE = r"""    /* ── Empty state ─────────────────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 2rem;
        background: var(--alert-neutral-bg);
        border: 1px dashed var(--alert-neutral-border);
        border-radius: var(--radius-md);
    }
    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.5;
        font-family: 'Material Symbols Outlined';
        font-weight: normal;
        font-style: normal;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-block;
        white-space: nowrap;
        word-wrap: normal;
        direction: rtl;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeLegibility;
        font-feature-settings: 'liga';
    }
    .empty-state-title {
        font-family: var(--font-display);
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text);
        margin-bottom: 0.5rem;
    }
    .empty-state-desc {
        color: var(--alert-neutral-text);
        font-size: 0.9rem;
        line-height: 1.5;
    }

"""

TABLE_COMPACT_STYLING = r"""    /* ── Table compact styling ────────────────────────────── */
    .compact-table {
        font-size: 0.8rem !important;
    }
    .compact-table th {
        padding: 0.4rem 0.5rem !important;
    }
    .compact-table td {
        padding: 0.35rem 0.5rem !important;
    }

"""

REDUCE_VERTICAL_WHITESPACE_FOR_REPORT_TAB = r"""    /* ── Reduce vertical whitespace for Report tab ───────── */
    .reduce-whitespace {
        padding-top: 0.25rem !important;
    }
    .reduce-whitespace > div {
        margin-bottom: 0.25rem !important;
    }

"""

IMPROVED_FORM_INPUTS = r"""    /* ── Improved form inputs ──────────────────────────────── */
    .stTextInput input,
    .stNumberInput input,
    .stSelectbox [data-baseweb="select"] {
        border-radius: var(--radius-sm) !important;
        border-color: var(--border-medium) !important;
        transition: border-color var(--transition-normal) ease,
                    box-shadow var(--transition-normal) ease !important;
    }
    .stTextInput input:hover,
    .stNumberInput input:hover {
        border-color: var(--brand-light) !important;
    }

"""

DATAFRAME_REFINEMENT = r"""    /* ── Dataframe refinement ─────────────────────────────── */
    [data-testid="stDataFrame"] {
        box-shadow: var(--shadow-sm) !important;
    }

"""

DANGER_BUTTON_STYLING = r"""    /* ── Danger button styling ────────────────────────────── */
    .stButton > button.dangerous {
        background-color: var(--error-bg) !important;
        color: var(--error-text) !important;
        border: 1.5px solid var(--error-border) !important;
    }
    .stButton > button.dangerous:hover {
        background-color: var(--error-text) !important;
        color: #fff !important;
        border-color: var(--error-text) !important;
    }

"""

CRITICAL_ALERT = r"""    /* ── Critical alert (first-run password, etc.) ───────── */
    .critical-alert {
        position: relative;
        background: var(--error-bg);
        color: var(--error-text);
        border-left: 4px solid var(--error-border);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-lg);
        padding: 1.1rem 1.25rem 1.1rem 1.4rem;
        margin: 0.5rem 0 1.25rem;
        font-family: var(--font-body);
    }
    .critical-alert-title {
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 0.4rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .critical-alert-body {
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .critical-alert code {
        display: inline-block;
        background: rgba(239, 68, 68, 0.12);
        color: var(--error-text);
        padding: 0.18rem 0.5rem;
        border-radius: var(--radius-sm);
        font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
        font-weight: 600;
        font-size: 0.92rem;
        user-select: all;
    }
    .critical-alert-actions {
        margin-top: 0.75rem;
    }
    .critical-alert-copy {
        background: var(--error-text);
        color: #fff;
        border: none;
        border-radius: var(--radius-sm);
        padding: 0.35rem 0.8rem;
        font-size: 0.82rem;
        font-weight: 600;
        cursor: pointer;
        font-family: var(--font-body);
        transition: opacity var(--transition-normal) ease;
    }
    .critical-alert-copy:hover {
        opacity: 0.85;
    }
    .critical-alert-copy:active {
        transform: scale(0.97);
    }

"""
