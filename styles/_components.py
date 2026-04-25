"""Reusable UI components — buttons, metrics, alerts, tables, date nav, WhatsApp, actions, empty state, dividers."""

BUTTON_SYSTEM = r"""    /* ── Button system ──────────────────────────────────────── */
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
        font-size: 0.75rem !important;
        letter-spacing: 0.03em;
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

"""

METRIC_CARDS_CONTAINERS = r"""    /* ── Metric cards & containers ──────────────────────────── */
    /* Shared elevated-surface base (merged from .metric-card + stMetric wrapper) */
    .metric-card,
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--surface);
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
        padding: 1rem;
        border-radius: var(--radius-lg);
        border-left: 4px solid var(--brand);
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
        border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle);
        border-left: 4px solid var(--accent-coral);
        padding: 1rem;
    }

"""

ALERT_STATUS_BOXES = r"""    /* ── Alert / status boxes ───────────────────────────────── */
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
        font-size: 0.8rem !important;
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

"""

EMPTY_STATE = r"""    /* ── Empty state ─────────────────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 2rem;
        background: var(--surface);
        border: 1px dashed var(--border-medium);
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
        color: var(--text-secondary);
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

