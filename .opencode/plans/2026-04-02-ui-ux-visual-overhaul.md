# UI/UX Visual Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix text/icon clipping, date navigation bugs, contradictory arrows, and deliver a polished visual overhaul while preserving the warm terracotta brand identity.

**Architecture:** All styling is centralized in `app.py` CSS block + `ui_theme.py` constants + `clipboard_ui.py` inline styles. Changes flow through these files with targeted fixes in tab renderers. No new dependencies — pure CSS/HTML improvements within Streamlit's existing framework.

**Tech Stack:** Python 3.11+, Streamlit, Plotly, CSS custom properties, HTML/JS for clipboard components

---

## File Structure

| File | Responsibility |
|------|---------------|
| `app.py` (lines 32-198) | Central CSS block — all global styles, component overrides, new CSS classes |
| `ui_theme.py` | Color palette constants, Plotly theme defaults, new visual tokens |
| `clipboard_ui.py` | WhatsApp/share button rendering, button styles, icon fixes, height adjustments |
| `tabs/report_tab.py` | Date navigation layout, spacing cleanup, date display fix |
| `.streamlit/config.toml` | Theme color updates to match new palette |
| `tabs/analytics_tab.py` | Minor spacing polish (no structural changes needed) |

---

### Task 1: Enhanced Color Palette & Theme Tokens

**Files:**
- Modify: `ui_theme.py` (entire file)
- Modify: `.streamlit/config.toml` (entire file)

- [ ] **Step 1: Update ui_theme.py with expanded color palette**

Replace the current `ui_theme.py` with an expanded palette that adds depth while preserving the terracotta brand identity:

```python
"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# ── Brand palette ─────────────────────────────────────────────────────────────
BRAND_PRIMARY = "#C2703E"   # Warm terracotta — restaurant editorial
BRAND_DARK    = "#A45A2E"   # Hover / pressed state
BRAND_LIGHT   = "#D4895A"   # Lighter variant for gradients
BRAND_SOFT    = "#F5EAE0"   # Soft background tint
BRAND_SUCCESS = "#5B7F4A"   # Semantic green — positive deltas, good status
BRAND_WARN    = "#C28B2D"   # Semantic amber — caution / warning
BRAND_ERROR   = "#B84233"   # Semantic red  — negative deltas, destructive
BRAND_INFO    = "#3B82F6"   # Semantic blue — info, links

# ── Surface & neutral palette ─────────────────────────────────────────────────
SURFACE_BASE      = "#FAF6F1"   # Main background
SURFACE_ELEVATED  = "#FFF8F0"   # Cards, elevated surfaces
SURFACE_RAISED    = "#FFFFFF"   # Modals, tooltips
TEXT_PRIMARY      = "#3D2B1F"   # Primary text
TEXT_SECONDARY    = "#6B5B4E"   # Secondary text (captions, hints)
TEXT_MUTED        = "#8C7B6B"   # Muted text
BORDER_SUBTLE     = "#E0D5C8"   # Light borders
BORDER_MEDIUM     = "#C8B9A8"   # Medium borders

# ── Shadow system ─────────────────────────────────────────────────────────────
SHADOW_SM = "0 1px 3px rgba(60,40,20,0.06)"
SHADOW_MD = "0 4px 12px rgba(60,40,20,0.08)"
SHADOW_LG = "0 8px 24px rgba(60,40,20,0.12)"

# ── Border radius system ──────────────────────────────────────────────────────
RADIUS_SM = "8px"
RADIUS_MD = "12px"
RADIUS_LG = "16px"

# ── Chart colorway — 8 distinct, colorblind-friendly hues ────────────────────
CHART_COLORWAY = [
    "#C2703E",  # terracotta  (primary)
    "#0369a1",  # steel blue
    "#5B7F4A",  # forest green
    "#7c3aed",  # violet
    "#0891b2",  # cyan / teal
    "#C28B2D",  # warm gold
    "#be185d",  # magenta
    "#475569",  # slate
]

CHART_HEIGHT = 380
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)


def apply_plotly_theme() -> None:
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="DM Sans, sans-serif",
                size=13,
                color=TEXT_PRIMARY,
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(
                bgcolor=SURFACE_ELEVATED,
                font_size=13,
                bordercolor=BORDER_SUBTLE,
                font_family="DM Sans, sans-serif",
            ),
            margin=CHART_MARGIN,
            title=dict(font=dict(size=16), x=0.02, xanchor="left"),
            plot_bgcolor=SURFACE_BASE,
            paper_bgcolor=SURFACE_ELEVATED,
            xaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=0.5,
                zerolinecolor=BORDER_MEDIUM,
            ),
            yaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=0.5,
                zerolinecolor=BORDER_MEDIUM,
            ),
        )
    )
    pio.templates.default = "plotly_white+boteco"
```

- [ ] **Step 2: Update .streamlit/config.toml with refined theme colors**

```toml
[theme]
primaryColor = "#C2703E"
backgroundColor = "#FAF6F1"
secondaryBackgroundColor = "#F0E8DD"
textColor = "#3D2B1F"
font = "sans serif"
```

(This remains unchanged — the current config.toml values already align with the new palette.)

---

### Task 2: Comprehensive CSS Overhaul

**Files:**
- Modify: `app.py` (lines 32-198 — the entire CSS block)

- [ ] **Step 1: Replace the CSS block in app.py with the comprehensive overhaul**

Replace lines 32-198 in `app.py` with this expanded CSS:

```css
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,300..700&display=swap');

    :root {
        --brand: #C2703E;
        --brand-dark: #A45A2E;
        --brand-light: #D4895A;
        --brand-soft: #F5EAE0;
        --surface: #FAF6F1;
        --surface-elevated: #FFF8F0;
        --surface-raised: #FFFFFF;
        --text: #3D2B1F;
        --text-secondary: #6B5B4E;
        --text-muted: #8C7B6B;
        --border-subtle: #E0D5C8;
        --border-medium: #C8B9A8;
        --success-bg: #EDF2E8;
        --success-text: #3D5A2E;
        --success-border: #D4DFC9;
        --error-bg: #F5E8E6;
        --error-text: #7A2E22;
        --error-border: #E8CFCB;
        --info-bg: #EFF6FF;
        --info-text: #1E40AF;
        --info-border: #BFDBFE;
        --font-display: 'DM Serif Display', serif;
        --font-body: 'DM Sans', sans-serif;
        --shadow-sm: 0 1px 3px rgba(60,40,20,0.06);
        --shadow-md: 0 4px 12px rgba(60,40,20,0.08);
        --shadow-lg: 0 8px 24px rgba(60,40,20,0.12);
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
    }

    /* ── Base typography ────────────────────────────────────── */
    html, body, [class*="st-"], .stMarkdown, p, li, span, label,
    [data-testid="stText"], input, textarea, select {
        font-family: var(--font-body) !important;
    }
    h1, h2, h3, h4, h5, h6,
    .main-header,
    [data-testid="stHeadingWithActionElements"] {
        font-family: var(--font-display) !important;
        color: var(--text) !important;
        letter-spacing: -0.01em;
        margin-bottom: 0.5em !important;
    }
    h1 { font-size: 2rem !important; }
    h2 { font-size: 1.5rem !important; }
    h3 { font-size: 1.25rem !important; }
    h4 { font-size: 1.1rem !important; }
    button[data-baseweb="tab"] {
        font-family: var(--font-display) !important;
        font-size: 1.05rem !important;
        letter-spacing: 0.01em;
    }
    .stCaption, [data-testid="stCaption"], caption {
        color: var(--text-muted) !important;
        font-size: 0.85rem !important;
    }

    /* ── Header ─────────────────────────────────────────────── */
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: var(--brand) !important;
        position: relative;
        padding-bottom: 0.5rem;
    }
    .main-header::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 60px;
        height: 3px;
        background: var(--brand);
        border-radius: 2px;
    }

    /* ── Button system ──────────────────────────────────────── */
    .stButton > button {
        font-family: var(--font-body) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: all 0.15s ease-in-out !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        min-height: 38px !important;
        line-height: 1.4 !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--brand) !important;
        color: var(--surface-elevated) !important;
        border: none !important;
        box-shadow: var(--shadow-sm) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--brand-dark) !important;
        box-shadow: var(--shadow-md) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: var(--surface-elevated) !important;
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

    /* ── KPI metric values ──────────────────────────────────── */
    div[data-testid="stMetricValue"] {
        color: var(--text) !important;
        font-weight: 700 !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
    }
    div[data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
    }
    div[data-testid="stMetricDelta"] {
        font-weight: 600 !important;
    }

    /* ── Metric cards & containers ──────────────────────────── */
    .metric-card {
        background: var(--surface-elevated);
        padding: 1rem;
        border-radius: var(--radius-md);
        border-left: 4px solid var(--brand);
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.15s ease, transform 0.15s ease;
    }
    .metric-card:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface) !important;
        border-color: var(--border-subtle) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
        background: var(--surface-elevated);
        border-radius: var(--radius-sm);
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-subtle);
        padding: 0.75rem;
        transition: box-shadow 0.15s ease, transform 0.15s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"]:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
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
        background: var(--brand-soft);
        margin-bottom: 0.75rem;
        transition: border-color 0.15s ease, background-color 0.15s ease;
    }
    .upload-zone:hover {
        border-color: var(--brand-dark);
        background: #F0DDD0;
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
        font-weight: 600 !important;
        color: var(--text) !important;
        background-color: var(--surface) !important;
        border-bottom: 2px solid var(--border-subtle) !important;
    }
    [data-testid="stDataFrame"] {
        border-radius: var(--radius-sm) !important;
        overflow: hidden !important;
        border: 1px solid var(--border-subtle) !important;
    }
    [data-testid="stDataFrame"] tr:nth-child(even) {
        background-color: var(--brand-soft) !important;
    }
    [data-testid="stDataFrame"] tr:hover {
        background-color: var(--surface) !important;
    }

    /* ── Expander labels ────────────────────────────────────── */
    [data-testid="stExpander"] summary {
        gap: 0.65rem;
        align-items: center;
        padding-left: 0.25rem;
        border-radius: var(--radius-sm);
        transition: background-color 0.15s ease;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: var(--brand-soft);
    }
    [data-testid="stExpander"] summary p {
        margin: 0;
        overflow: visible;
        line-height: 1.5;
    }
    [data-testid="stExpander"] svg {
        flex-shrink: 0;
        margin-right: 0.25rem;
        transition: transform 0.2s ease;
    }
    [data-testid="stExpander"][open] summary svg {
        transform: rotate(90deg);
    }

    /* ── Sidebar ────────────────────────────────────────────── */
    [data-testid="stSidebar"] hr {
        margin: 0.75rem 0;
        border-color: var(--border-subtle);
    }
    [data-testid="stSidebar"] {
        background-color: var(--surface) !important;
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
        font-family: var(--font-display), serif;
        font-size: 1.25rem;
        color: var(--text);
        text-align: center;
        min-width: 200px;
        padding: 0.5rem 1rem;
        background: var(--surface-elevated);
        border-radius: var(--radius-sm);
        border: 1px solid var(--border-subtle);
        box-shadow: var(--shadow-sm);
    }

    /* ── WhatsApp share buttons ─────────────────────────────── */
    .whatsapp-btn-container {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        min-height: 48px;
    }
    .whatsapp-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.5rem 1rem;
        border-radius: var(--radius-sm);
        font-weight: 600;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.15s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1.3;
        min-height: 40px;
    }
    .whatsapp-btn-primary {
        background: var(--brand);
        color: var(--surface-elevated);
        border: none;
        box-shadow: var(--shadow-sm);
    }
    .whatsapp-btn-primary:hover {
        background: var(--brand-dark);
        box-shadow: var(--shadow-md);
    }
    .whatsapp-btn-secondary {
        background: var(--surface-elevated);
        color: var(--text);
        border: 1px solid var(--border-subtle);
    }
    .whatsapp-btn-secondary:hover {
        background: var(--brand-soft);
        border-color: var(--brand);
        color: var(--brand-dark);
    }
    .whatsapp-icon {
        width: 18px;
        height: 18px;
        flex-shrink: 0;
        vertical-align: middle;
    }
    .whatsapp-msg {
        font-size: 0.8rem;
        color: var(--success-text);
        margin-left: 0.5rem;
    }

    /* ── Section dividers ───────────────────────────────────── */
    .section-divider {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, var(--border-subtle), transparent);
        margin: 1.5rem 0;
    }

    /* ── Smooth transitions ─────────────────────────────────── */
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"],
    [data-testid="stVerticalBlockBorderWrapper"] {
        transition: all 0.15s ease;
    }

    /* ── Scrollbar styling ──────────────────────────────────── */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--surface);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb {
        background: var(--border-medium);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }
</style>
```

---

### Task 3: Fix WhatsApp Button Clipping & Add SVG Icons

**Files:**
- Modify: `clipboard_ui.py` (entire file — replace `_btn_style`, `render_share_images_button`, and add SVG icon)

- [ ] **Step 1: Add WhatsApp SVG icon constant and update button styling**

Replace the entire `clipboard_ui.py` file with this updated version:

```python
"""Streamlit HTML/JS helpers for clipboard (text + PNG). Requires HTTPS or localhost."""

import base64
import hashlib
import inspect
import json

import streamlit.components.v1 as components

import ui_theme
from typing import List, Tuple, Optional

# WhatsApp SVG icon (24x24, brand-colored)
WHATSAPP_ICON_SVG = (
    '<svg class="whatsapp-icon" viewBox="0 0 24 24" fill="currentColor" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.151'
    '-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475'
    '-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52'
    '.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207'
    '-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297'
    '-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487'
    '.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413'
    '.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 '
    '9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51'
    '-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 '
    '0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 '
    '0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305'
    '-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 '
    '11.821 0 00-3.48-8.413z"/>'
    '</svg>'
)


def _html(html: str, height: int, component_key: str) -> None:
    """Call components.html with key only if this Streamlit build supports it."""
    params = inspect.signature(components.html).parameters
    if "key" in params:
        components.html(html, height=height, key=component_key)
    else:
        components.html(html, height=height)


def _safe_id(key: str) -> str:
    return "c" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _btn_style(*, primary: bool = True) -> str:
    """Generate inline button styles with proper overflow handling."""
    c = ui_theme.BRAND_PRIMARY
    if primary:
        return (
            f"padding:0.5rem 1rem;cursor:pointer;border-radius:8px;border:none;"
            f"background:{c};color:#FFF8F0;font-weight:600;font-size:0.85rem;"
            f"font-family:'DM Sans',sans-serif;"
            f"box-shadow:0 1px 3px rgba(60,40,20,0.08);"
            f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
            f"display:inline-flex;align-items:center;gap:0.4rem;"
            f"min-height:40px;line-height:1.3;transition:all 0.15s ease;"
        )
    return (
        "padding:0.5rem 1rem;cursor:pointer;border-radius:8px;border:1px solid #E0D5C8;"
        "background:#FFF8F0;color:#3D2B1F;font-weight:500;font-size:0.85rem;"
        "font-family:'DM Sans',sans-serif;"
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
        "display:inline-flex;align-items:center;gap:0.4rem;"
        "min-height:40px;line-height:1.3;transition:all 0.15s ease;"
    )


def render_copy_text_button(
    text: str,
    label: str,
    component_key: str,
    height: int = 56,
    *,
    primary: bool = True,
) -> None:
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    uid = _safe_id(component_key + "t")
    stl = _btn_style(primary=primary)
    html = f"""
<div class="whatsapp-btn-container">
  <button id="{uid}_btn" type="button" style="{stl}">{label}</button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
</div>
<script>
(function() {{
  const b64 = {repr(b64)};
  document.getElementById("{uid}_btn").onclick = async function() {{
    try {{
      const bin = atob(b64);
      const u8 = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const txt = new TextDecoder("utf-8").decode(u8);
      await navigator.clipboard.writeText(txt);
      document.getElementById("{uid}_msg").textContent = "Copied";
    }} catch (e) {{
      alert("Copy failed. Use HTTPS or allow clipboard access. " + e);
    }}
  }};
}})();
</script>
"""
    _html(html, height, component_key)


def render_copy_image_button(
    png_bytes: bytes,
    label: str,
    component_key: str,
    height: int = 56,
    *,
    primary: bool = True,
) -> None:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    uid = _safe_id(component_key + "i")
    stl = _btn_style(primary=primary)
    html = f"""
<div class="whatsapp-btn-container">
  <button id="{uid}_btn" type="button" style="{stl}">{label}</button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
</div>
<script>
(function() {{
  const dataUrl = "data:image/png;base64," + {repr(b64)};
  document.getElementById("{uid}_btn").onclick = async function() {{
    try {{
      const blob = await (await fetch(dataUrl)).blob();
      await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
      document.getElementById("{uid}_msg").textContent = "Copied image";
    }} catch (e) {{
      alert("Image copy failed (try Chrome/Edge over HTTPS). " + e);
    }}
  }};
}})();
</script>
"""
    _html(html, height, component_key)


def render_share_images_button(
    files: List[Tuple[str, bytes]],
    label: str,
    component_key: str,
    height: int = 56,
    *,
    primary: bool = True,
    share_text: str = "Boteco EOD Report",
    fallback_url: Optional[str] = None,
) -> None:
    """Share multiple PNG images via native share API (mobile) or show fallback (desktop)."""
    if not files:
        return

    # Build base64 for each file
    files_b64 = []
    for name, data in files:
        b64 = base64.b64encode(data).decode("ascii")
        files_b64.append((name, b64))

    uid = _safe_id(component_key + "s")
    stl = _btn_style(primary=primary)

    # JSON-safe representation of files array
    files_json = (
        "["
        + ",".join('{{"name":{!r},"b64":{!r}}}'.format(n, b) for n, b in files_b64)
        + "]"
    )
    fallback_url_json = json.dumps(fallback_url)

    html = """<div class="whatsapp-btn-container">
  <button id="{uid}_btn" type="button" style="{stl}">{whatsapp_icon}<span>{label}</span></button>
  <span id="{uid}_msg" class="whatsapp-msg"></span>
</div>
<script>
(function() {{
  const filesData = {files_json};
  const shareText = {share_text_json};
  const fallbackUrl = {fallback_url_json};
  const msgEl = document.getElementById("{uid}_msg");
  const btnEl = document.getElementById("{uid}_btn");

  async function b64ToBlob(b64, mime) {{
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Blob([u8], {{type: mime}});
  }}

  async function canShareFiles() {{
    if (!navigator.canShare) return false;
    try {{
      const testBlob = await b64ToBlob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "image/png");
      return navigator.canShare({{files: [new File([testBlob], "test.png", {{type: "image/png"}})]}});
    }} catch(e) {{
      return false;
    }}
  }}

  btnEl.onclick = async function() {{
    try {{
      const fileObjs = await Promise.all(
        filesData.map(async (f) => {{
          const blob = await b64ToBlob(f.b64, "image/png");
          return new File([blob], f.name, {{type: "image/png"}});
        }})
      );

      const canShare = await canShareFiles();
      if (canShare) {{
        await navigator.share({{
          files: fileObjs,
          text: shareText
        }});
        msgEl.textContent = "Shared!";
        msgEl.style.color = "#5B7F4A";
      }} else {{
        if (fallbackUrl) {{
          try {{
            const blob = await b64ToBlob(filesData[0].b64, "image/png");
            await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
            msgEl.textContent = "Image copied — paste in WhatsApp";
            msgEl.style.color = "#5B7F4A";
          }} catch (clipErr) {{
            msgEl.textContent = "Open WhatsApp — attach image manually";
            msgEl.style.color = "#C28B2D";
          }}
          window.open(fallbackUrl, "_blank");
        }} else {{
          msgEl.textContent = "Use download (ZIP/PNG)";
          msgEl.style.color = "#C28B2D";
        }}
      }}
    }} catch (e) {{
      console.error("Share error:", e);
      if (e.name === "AbortError") {{
        return;
      }}
      if (e.message && e.message.includes("not supported")) {{
        if (fallbackUrl) {{
          try {{
            const blob = await b64ToBlob(filesData[0].b64, "image/png");
            await navigator.clipboard.write([new ClipboardItem({{"image/png": blob}})]);
            msgEl.textContent = "Image copied — paste in WhatsApp";
            msgEl.style.color = "#5B7F4A";
          }} catch (clipErr) {{
            msgEl.textContent = "Open WhatsApp — attach image manually";
            msgEl.style.color = "#C28B2D";
          }}
          window.open(fallbackUrl, "_blank");
        }} else {{
          msgEl.textContent = "Use download (ZIP/PNG)";
          msgEl.style.color = "#C28B2D";
        }}
      }} else {{
        msgEl.textContent = "Share failed";
        msgEl.style.color = "#B84233";
      }}
    }}
  }};
}})();
</script>
""".format(
        uid=uid,
        stl=stl,
        label=label,
        whatsapp_icon=WHATSAPP_ICON_SVG,
        files_json=files_json,
        share_text_json=json.dumps(share_text),
        fallback_url_json=fallback_url_json,
    )
    _html(html, height, component_key)
```

Key changes:
- Added `WHATSAPP_ICON_SVG` constant with inline SVG
- Increased default `height` from `52` to `56` across all functions
- Added `white-space:nowrap;overflow:hidden;text-overflow:ellipsis` to `_btn_style`
- Added `display:inline-flex;align-items:center;gap:0.4rem` for proper icon+text alignment
- Wrapped button content in `.whatsapp-btn-container` div with proper flex layout
- Added `.whatsapp-msg` class for consistent message styling

---

### Task 4: Fix Date Navigation — Arrow Contradiction & Date Display

**Files:**
- Modify: `tabs/report_tab.py` (lines 30-62 — date navigation section)

- [ ] **Step 1: Replace date navigation with custom display**

Replace lines 30-62 in `tabs/report_tab.py` with this improved date navigation:

```python
    # Date selector with Prev/Next navigation
    if "report_date" not in st.session_state:
        most_recent_date = database.get_most_recent_date_with_data(ctx.report_loc_ids)
        if most_recent_date:
            st.session_state["report_date"] = datetime.strptime(
                most_recent_date, "%Y-%m-%d"
            ).date()
        else:
            st.session_state["report_date"] = datetime.now().date()

    selected_date = st.session_state["report_date"]
    date_display = selected_date.strftime("%a, %d %b %Y")

    nav_col1, nav_col2, nav_col3 = st.columns([1, 4, 1])
    with nav_col1:
        st.write("")
        if st.button("← Prev", key="report_prev_day", use_container_width=True):
            st.session_state["report_date"] -= timedelta(days=1)
            st.rerun()
    with nav_col2:
        st.markdown(
            f'<div class="date-display" style="text-align:center;">{date_display}</div>',
            unsafe_allow_html=True,
        )
        # Hidden date picker for calendar access
        picked = st.date_input(
            "Select Date",
            value=selected_date,
            key=f"report_date_picker_{selected_date.isoformat()}",
            label_visibility="collapsed",
        )
        if picked != selected_date:
            st.session_state["report_date"] = picked
            st.rerun()
    with nav_col3:
        st.write("")
        if st.button("Next →", key="report_next_day", use_container_width=True):
            st.session_state["report_date"] += timedelta(days=1)
            st.rerun()

    date_str = selected_date.strftime("%Y-%m-%d")
```

Key changes:
- Added prominent date display in center column with `.date-display` class
- Changed column ratio from `[1, 3, 1]` to `[1, 4, 1]` to give more space to date display
- Added `label_visibility="collapsed"` to date picker so it doesn't show a redundant label
- Made the date picker key dynamic (`f"report_date_picker_{selected_date.isoformat()}"`) to force re-render when date changes via buttons, fixing the sync issue
- Removed the duplicate `date_str` assignment that was after the nav block
- The date picker is now a secondary access method — the primary display is the styled text

---

### Task 5: Update Report Tab WhatsApp Button Heights

**Files:**
- Modify: `tabs/report_tab.py` (lines 470-513 — WhatsApp button calls)

- [ ] **Step 1: Update all clipboard_ui calls to use new height=56**

Find and replace all `height=44` calls in `tabs/report_tab.py` with `height=56`:

Line 474: Change `height=44,` to `height=56,`
Line 492: Change `height=44,` to `height=56,`
Line 501: Change `height=44,` to `height=56,`

Also update the button labels to remove the emoji since we now have SVG icons:

Line 472: Change `"📱 WhatsApp (5 PNGs)"` to `"WhatsApp (5 PNGs)"`
Line 499: Change `f"📱 WhatsApp ({title})"` to `f"WhatsApp ({title})"`

---

### Task 6: Polish Analytics Tab Spacing & Layout

**Files:**
- Modify: `tabs/analytics_tab.py` (lines 80-84 — period display)

- [ ] **Step 1: Improve period date range display styling**

Replace lines 80-84 with styled display:

```python
        with col_per2:
            st.markdown(
                f'<div style="padding:0.5rem 0;font-size:0.95rem;color:var(--text-secondary);">'
                f'<strong>From:</strong> {start_date.strftime("%d %b")} '
                f'<strong>to</strong> {end_date.strftime("%d %b %Y")}'
                f'</div>',
                unsafe_allow_html=True,
            )
```

- [ ] **Step 2: Replace all `st.markdown("---")` with styled dividers**

Find all instances of `st.markdown("---")` in `tabs/analytics_tab.py` and replace with:

```python
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
```

These occur at lines: 176, 260, 300, 345, 400, 458, 523

---

### Task 7: Polish Report Tab Spacing & Dividers

**Files:**
- Modify: `tabs/report_tab.py` (all divider and spacing instances)

- [ ] **Step 1: Replace dividers and clean up spacing**

Replace all `st.markdown("---")` with styled dividers:

Line 207: `st.markdown("---")` → `st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)`
Line 327: `st.markdown("---")` → `st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)`
Line 516: `st.markdown("---")` → `st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)`

Remove the `st.write("")` padding hacks in the date navigation (lines 42 and 56) since the CSS now handles spacing properly.

---

### Task 8: Verify & Test

**Files:**
- All modified files

- [ ] **Step 1: Run the application to verify changes**

Run: `streamlit run app.py`

Verify:
1. No text clipping on any buttons (WhatsApp, Copy, PNG, navigation)
2. Date navigation shows formatted date prominently in center
3. Prev/Next buttons work and date display updates immediately
4. Date picker calendar still accessible (collapsed label, below the display)
5. WhatsApp SVG icons render correctly and are not clipped
6. All dividers show gradient style instead of plain lines
7. Cards have hover animations
8. Tables show zebra striping
9. Expanders have smooth arrow rotation
10. Color scheme is consistent across all tabs

- [ ] **Step 2: Run existing tests to ensure no regressions**

Run: `pytest tests/test_pos_parser.py -v`

Expected: All tests pass (no changes to parsing logic)

- [ ] **Step 3: Cross-browser check**

Test in Chrome and Edge to verify:
- SVG icons render correctly
- CSS custom properties are supported
- Clipboard API works for copy buttons
- Web Share API fallback works

---

## Implementation Order

Tasks should be executed in this order:
1. **Task 1** — Color palette (foundation for all other changes)
2. **Task 2** — CSS overhaul (depends on Task 1 tokens)
3. **Task 3** — WhatsApp button fixes (depends on Task 2 CSS classes)
4. **Task 4** — Date navigation fix (depends on Task 2 CSS classes)
5. **Task 5** — Report tab button height updates (depends on Task 3)
6. **Task 6** — Analytics tab polish (depends on Task 2)
7. **Task 7** — Report tab polish (depends on Task 2)
8. **Task 8** — Verification & testing

Each task produces independently testable UI improvements. Tasks 1-2 should be committed together as "style: overhaul CSS and color palette". Tasks 3-5 as "fix: WhatsApp button clipping and date navigation". Tasks 6-7 as "polish: spacing and dividers across tabs".

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| SVG icon may not render in older browsers | Fallback to emoji via CSS `::before` content if needed |
| CSS custom properties not supported in very old browsers | All target browsers (Chrome, Edge, Safari 15+) support CSS variables |
| Streamlit may override some styles | Use `!important` sparingly, only where Streamlit forces inline styles |
| `label_visibility="collapsed"` requires Streamlit >= 1.21 | Already in use in codebase, safe to use |
| Dynamic date picker key may cause brief re-mount | Acceptable tradeoff for correct state sync |
