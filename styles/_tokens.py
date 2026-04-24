"""CSS :root tokens and Material Symbols base class."""

TOKEN_SYSTEM = r"""    /* ── Token system ─────────────────────────────────────────── */
    :root {
        /* Brand palette */
        --brand: #1F5FA8;
        --brand-dark: #174A82;
        --brand-darker: #133F70;
        --brand-light: #2A6BB3;
        --brand-soft: #E6F4F3;

        /* Surface palette */
        --surface: #F7FAFC;
        --surface-elevated: #FFFFFF;
        --surface-raised: #FFFFFF;
        --sidebar-bg: #1F5FA8;
        --sidebar-border: #2A6BB3;
        --table-header-bg: #EEF2F7;

        /* Text palette */
        --text: #1E293B;
        --text-secondary: #475569;
        --text-muted: #475569;

        /* Border palette */
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;

        /* Accent colors */
        --accent-coral: #1F5FA8;
        --accent-teal: #3FA7A3;
        --accent-amber: #F4B400;
        --accent-green: #6DBE45;
        --accent-info: #6366F1;
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

        /* Material Symbols */
        .material-symbols-outlined {
            font-family: 'Material Symbols Outlined';
            font-weight: normal;
            font-style: normal;
            font-size: 24px;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            text-rendering: optimizeLegibility;
            font-feature-settings: 'liga';
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }

        /* Z-index scale */
        --z-index-dropdown: 10;
        --z-index-modal: 100;
        --z-index-toast: 1000;

        /* Transitions */
        --transition-fast: 150ms;
        --transition-normal: 200ms;
    }

"""

