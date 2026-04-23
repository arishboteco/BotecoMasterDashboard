"""CSS :root tokens and Material Symbols base class — logo-derived palette.

Public exports:
  TOKEN_SYSTEM — full token block (light + dark + system-preference fallback).
"""

from __future__ import annotations

# ── Logo color palette ─────────────────────────────────────────────────────────
# Extracted from logo.png dominant non-white pixels.
# Primary:   #005AAB — Royal Blue (brand)
# Secondary: #A2D06E — Lime Green (success/positive)
# Accent:    #FDB813 — Golden Yellow (accent/warning)
# Tertiary:  #54C5D0 — Sky Teal (secondary accent)

TOKEN_SYSTEM = r"""
    /* ── Light mode tokens (default) ─────────────────────────── */
    :root {
        /* Brand palette — logo-derived */
        --brand: #005AAB;
        --brand-dark: #004080;
        --brand-darker: #003366;
        --brand-light: #2D7AC9;
        --brand-soft: #EBF4FF;

        /* Surface palette */
        --surface: #F7FAFC;
        --surface-elevated: #FFFFFF;
        --surface-raised: #FFFFFF;
        --sidebar-bg: #005AAB;
        --sidebar-border: #004080;
        --table-header-bg: #EEF2F7;

        /* Text palette */
        --text: #1E293B;
        --text-secondary: #475569;
        --text-muted: #64748B;

        /* Border palette */
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;

        /* Accent colors — logo palette */
        --accent-coral: #005AAB;
        --accent-teal: #54C5D0;
        --accent-amber: #FDB813;
        --accent-green: #A2D06E;
        --accent-slate: #005AAB;

        /* Semantic colors */
        --success-bg: #F0FDF4;
        --success-text: #15803D;
        --success-border: #BBF7D0;
        --error-bg: #FEF2F2;
        --error-text: #B91C1C;
        --error-border: #FECACA;
        --info-bg: #EFF6FF;
        --info-text: #1D4ED8;
        --info-border: #BFDBFE;

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

    /* ── Dark mode tokens — activated via data-theme="dark" on <html> ──── */
    :root[data-theme="dark"] {
        /* Brand palette — brightened for dark surface contrast */
        --brand: #2D7AC9;
        --brand-dark: #1F5FA8;
        --brand-darker: #005AAB;
        --brand-light: #5A97D6;
        --brand-soft: #1E3A5F;

        /* Surface palette */
        --surface: #0F172A;
        --surface-elevated: #1E293B;
        --surface-raised: #334155;
        --sidebar-bg: #0F172A;
        --sidebar-border: #1E293B;
        --table-header-bg: #1E293B;

        /* Text palette */
        --text: #F1F5F9;
        --text-secondary: #CBD5E1;
        --text-muted: #94A3B8;

        /* Border palette */
        --border-subtle: #334155;
        --border-medium: #475569;

        /* Accent colors — slight brightening */
        --accent-coral: #2D7AC9;
        --accent-teal: #7DD3E0;
        --accent-amber: #FBBF24;
        --accent-green: #A2D06E;
        --accent-slate: #2D7AC9;

        /* Semantic colors — dark variants */
        --success-bg: #052E16;
        --success-text: #86EFAC;
        --success-border: #166534;
        --error-bg: #450A0A;
        --error-text: #FCA5A5;
        --error-border: #7F1D1D;
        --info-bg: #1E1B4B;
        --info-text: #A5B4FC;
        --info-border: #3730A3;

        /* Shadows deepen on dark backgrounds */
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.45), 0 4px 6px -4px rgba(0,0,0,0.3);
    }

    /* ── System-preference fallback (no explicit data-theme override) ──── */
    @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) {
            --brand: #2D7AC9;
            --brand-dark: #1F5FA8;
            --brand-darker: #005AAB;
            --brand-light: #5A97D6;
            --brand-soft: #1E3A5F;
            --surface: #0F172A;
            --surface-elevated: #1E293B;
            --surface-raised: #334155;
            --sidebar-bg: #0F172A;
            --sidebar-border: #1E293B;
            --table-header-bg: #1E293B;
            --text: #F1F5F9;
            --text-secondary: #CBD5E1;
            --text-muted: #94A3B8;
            --border-subtle: #334155;
            --border-medium: #475569;
            --accent-coral: #2D7AC9;
            --accent-teal: #7DD3E0;
            --accent-amber: #FBBF24;
            --accent-green: #A2D06E;
            --accent-slate: #2D7AC9;
            --success-bg: #052E16;
            --success-text: #86EFAC;
            --success-border: #166534;
            --error-bg: #450A0A;
            --error-text: #FCA5A5;
            --error-border: #7F1D1D;
            --info-bg: #1E1B4B;
            --info-text: #A5B4FC;
            --info-border: #3730A3;
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -2px rgba(0,0,0,0.3);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.45), 0 4px 6px -4px rgba(0,0,0,0.3);
        }
    }

"""