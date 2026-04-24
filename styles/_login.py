"""Login page CSS — scoped token subset + login card + entrance animation."""

LOGIN_CSS = r"""
<style>
    /* Login token subset. Light values live in :root; the
       :root[data-theme="dark"] block overrides them when data-theme is set
       on <html> (see app.py theme-injection script). The OS-preference
       fallback keeps dark mode working when no attribute is set yet. */
    :root {
        --brand: #1F5FA8;
        --brand-dark: #174A82;
        --brand-light: #2A6BB3;
        --text: #1E293B;
        --text-muted: #475569;
        --login-page-bg: #F7FAFC;
        --login-card-bg: #FFFFFF;
        --login-card-border: #E2E8F0;
        --login-card-shadow: 0 4px 6px -1px rgba(0,0,0,0.07),
                             0 20px 40px -8px rgba(31,95,168,0.12);
        --login-label: #374151;
        --login-footer-text: #94A3B8;
        --login-caps-bg: #FEF3C7;
        --login-caps-text: #92400E;
        --login-caps-border: #FDE68A;
        --login-image-bg: #F1F5F9;
    }
    :root[data-theme="dark"] {
        --brand: #3A7FC9;
        --brand-dark: #2A6BB3;
        --brand-light: #5A97D6;
        --text: #F1F5F9;
        --text-muted: #94A3B8;
        --login-page-bg: #0F172A;
        --login-card-bg: #1E293B;
        --login-card-border: #334155;
        --login-card-shadow: 0 4px 6px -1px rgba(0,0,0,0.45),
                             0 20px 40px -8px rgba(0,0,0,0.5);
        --login-label: #CBD5E1;
        --login-footer-text: #94A3B8;
        --login-caps-bg: #78350F;
        --login-caps-text: #FDE68A;
        --login-caps-border: #92400E;
        --login-image-bg: #334155;
    }
    @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) {
            --brand: #3A7FC9;
            --brand-dark: #2A6BB3;
            --brand-light: #5A97D6;
            --text: #F1F5F9;
            --text-muted: #94A3B8;
            --login-page-bg: #0F172A;
            --login-card-bg: #1E293B;
            --login-card-border: #334155;
            --login-card-shadow: 0 4px 6px -1px rgba(0,0,0,0.45),
                                 0 20px 40px -8px rgba(0,0,0,0.5);
            --login-label: #CBD5E1;
            --login-footer-text: #94A3B8;
            --login-caps-bg: #78350F;
            --login-caps-text: #FDE68A;
            --login-caps-border: #92400E;
            --login-image-bg: #334155;
        }
    }
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

    /* ── Login page background ────────────────────────── */
    .stApp {
        background:
            radial-gradient(ellipse at 20% 50%, rgba(31,95,168,0.06) 0%, transparent 60%),
            radial-gradient(ellipse at 80% 20%, rgba(63,167,163,0.05) 0%, transparent 55%),
            radial-gradient(ellipse at 60% 80%, rgba(244,180,0,0.04) 0%, transparent 50%),
            var(--login-page-bg) !important;
    }

    /* ── Login card ───────────────────────────────────── */
    .login-card {
        background: var(--login-card-bg);
        border-radius: 20px;
        border: 1px solid var(--login-card-border);
        box-shadow: var(--login-card-shadow);
        padding: 2.5rem 2rem 2rem;
        margin-top: 4rem;
        margin-left: auto;
        margin-right: auto;
        max-width: 420px;
        animation: loginFadeUp 0.4s ease-out both;
        text-align: center;
    }
    .login-caps-hint {
        display: none;
        margin-top: 0.35rem;
        padding: 0.35rem 0.55rem;
        background: var(--login-caps-bg);
        color: var(--login-caps-text);
        border-radius: 8px;
        font-size: 0.78rem;
        font-family: 'Inter', sans-serif;
        border: 1px solid var(--login-caps-border);
    }
    .login-caps-hint.active {
        display: block;
        animation: loginFadeUp 0.18s ease-out both;
    }
    @keyframes loginFadeUp {
        from { opacity: 0; transform: translateY(16px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ── Login branding ───────────────────────────────── */
    .login-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.6rem;
        font-weight: 800;
        color: var(--brand);
        letter-spacing: -0.02em;
        margin-top: 1rem;
        margin-bottom: 0.2rem;
    }
    .login-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 0.88rem;
        color: var(--text-muted);
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-bottom: 1.5rem;
    }

    /* ── Login form wrapper ───────────────────────────── */
    .login-form-wrap {
        text-align: left;
    }
    .login-footer {
        margin-top: 1.25rem;
        font-family: 'Inter', sans-serif;
        font-size: 0.73rem;
        color: var(--login-footer-text);
        text-align: center;
        letter-spacing: 0.02em;
    }

    /* ── Override button for login page ──────────────── */
    .stButton > button {
        background-color: var(--brand) !important;
        color: #FFFFFF !important;
        border: none !important;
        padding: 0.7rem !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.01em;
    }
    .stButton > button:hover {
        background-color: var(--brand-dark) !important;
        box-shadow: 0 4px 12px rgba(31, 95, 168, 0.3) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Input focus ──────────────────────────────────── */
    .stTextInput input:focus {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(31, 95, 168, 0.15) !important;
    }
    .stTextInput label {
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        color: var(--login-label) !important;
    }

    /* ── Hide Streamlit chrome on login page ─────────── */
    [data-testid="stHeader"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    /* ── Image centering ──────────────────────────────── */
    .login-card [data-testid="stImage"] {
        display: flex;
        justify-content: center;
    }
    .login-card img {
        border-radius: 12px;
        padding: 6px;
        background: var(--login-image-bg);
    }

    /* ── Responsive ───────────────────────────────────── */
    @media (max-width: 640px) {
        .login-card {
            margin-top: 1.5rem;
            padding: 1.75rem 1.25rem 1.5rem;
        }
    }
</style>
"""
