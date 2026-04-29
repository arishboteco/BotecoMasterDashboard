"""Login page CSS — scoped token subset + login card + entrance animation."""

LOGIN_CSS = r"""
<style>
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
    /* Fonts imported by _fonts.FONTS in main stylesheet (applied before auth). */

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
        border-radius: var(--radius-xl);
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
        border-radius: var(--radius-md);
        font-size: var(--font-size-caption);
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
    .login-form-wrap div[data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    .login-footer {
        margin-top: 1.25rem;
        font-family: 'Inter', sans-serif;
        font-size: var(--font-size-caption);
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
        border-radius: var(--radius-lg) !important;
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

    /* ── Hide CookieController visual mount / blank box ────────────────── */
    iframe[title*="cookie"],
    iframe[src*="streamlit_cookies"],
    iframe[src*="cookie"] {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        visibility: hidden !important;
    }

    /* Hide the Streamlit wrapper around the cookie iframe */
    div[data-testid="stElementContainer"]:has(iframe[title*="cookie"]),
    div[data-testid="stElementContainer"]:has(iframe[src*="cookie"]),
    div[data-testid="stVerticalBlock"]:has(iframe[title*="cookie"]),
    div[data-testid="stVerticalBlock"]:has(iframe[src*="cookie"]) {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }

    /* ── Image centering ──────────────────────────────── */
    .login-card [data-testid="stImage"] {
        display: flex;
        justify-content: center;
    }
    .login-card img {
        border-radius: var(--radius-lg);
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
