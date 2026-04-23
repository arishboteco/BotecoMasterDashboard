"""Login page CSS — scoped token subset + login card + entrance animation."""

LOGIN_CSS = r"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');
    :root {
        --brand: #005AAB;
        --brand-dark: #004080;
        --brand-light: #2D7AC9;
        --text: #1E293B;
        --text-muted: #64748B;
    }

    /* ── Login page background ────────────────────────── */
    .stApp {
        background:
            radial-gradient(ellipse at 20% 50%, rgba(0,90,171,0.06) 0%, transparent 60%),
            radial-gradient(ellipse at 80% 20%, rgba(84,197,208,0.05) 0%, transparent 55%),
            radial-gradient(ellipse at 60% 80%, rgba(253,184,19,0.04) 0%, transparent 50%),
            #F7FAFC !important;
    }

    /* ── Login card ───────────────────────────────────── */
    .login-card {
        background: #FFFFFF;
        border-radius: 20px;
        border: 1px solid #E2E8F0;
        box-shadow:
            0 4px 6px -1px rgba(0,0,0,0.07),
            0 20px 40px -8px rgba(31,95,168,0.12);
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
        background: #FEF3C7;
        color: #92400E;
        border-radius: 8px;
        font-size: 0.78rem;
        font-family: 'Inter', sans-serif;
        border: 1px solid #FDE68A;
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
        color: #94A3B8;
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
        box-shadow: 0 4px 12px rgba(0, 90, 171, 0.3) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Input focus ──────────────────────────────────── */
    .stTextInput input:focus {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(0, 90, 171, 0.18) !important;
    }
    .stTextInput label {
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        color: #374151 !important;
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
        background: #F1F5F9;
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
