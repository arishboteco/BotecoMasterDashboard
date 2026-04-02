# UI/UX Redesign v2 — Clean White Theme with Blue Accent

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Clean white background, blue accent color, fix text clipping, remove contradictory delta arrows.

**Architecture:** 4 files need coordinated color/brand changes + 1 file needs delta format fix.

---

## Task 1: Update ui_theme.py — New Color Palette

**File:** `ui_theme.py` (entire file)

Replace all color constants with the new blue-accent white theme:

```python
"""Shared UI constants and Plotly defaults for the dashboard."""

import plotly.graph_objects as go
import plotly.io as pio

# ── Brand palette (blue accent) ───────────────────────────────────────────────
BRAND_PRIMARY = "#2563EB"   # Blue — primary actions, links
BRAND_DARK    = "#1D4ED8"   # Darker blue — hover/pressed
BRAND_LIGHT   = "#3B82F6"   # Lighter blue — gradients
BRAND_SOFT    = "#DBEAFE"   # Soft blue tint — backgrounds
BRAND_SUCCESS = "#16A34A"   # Green — positive deltas
BRAND_WARN    = "#D97706"   # Amber — warning
BRAND_ERROR   = "#DC2626"   # Red — negative deltas, destructive
BRAND_INFO    = "#2563EB"   # Blue — info (same as brand)

# ── Surface & neutral palette ─────────────────────────────────────────────────
SURFACE_BASE      = "#FFFFFF"   # Main background — pure white
SURFACE_ELEVATED  = "#F8FAFC"   # Cards — very light blue-gray
SURFACE_RAISED    = "#FFFFFF"   # Modals, tooltips
TEXT_PRIMARY      = "#0F172A"   # Primary text — near-black slate
TEXT_SECONDARY    = "#475569"   # Secondary text
TEXT_MUTED        = "#94A3B8"   # Muted text
BORDER_SUBTLE     = "#E2E8F0"   # Light borders
BORDER_MEDIUM     = "#CBD5E1"   # Medium borders

# ── Shadow system ─────────────────────────────────────────────────────────────
SHADOW_SM = "0 1px 2px rgba(0,0,0,0.05)"
SHADOW_MD = "0 4px 6px rgba(0,0,0,0.07)"
SHADOW_LG = "0 10px 15px rgba(0,0,0,0.1)"

# ── Border radius system ──────────────────────────────────────────────────────
RADIUS_SM = "6px"
RADIUS_MD = "8px"
RADIUS_LG = "12px"

# ── Chart colorway — blue-forward, colorblind-friendly ────────────────────────
CHART_COLORWAY = [
    "#2563EB",  # blue (primary)
    "#16A34A",  # green
    "#D97706",  # amber
    "#7C3AED",  # violet
    "#0891B2",  # cyan
    "#DC2626",  # red
    "#DB2777",  # pink
    "#475569",  # slate
]

CHART_HEIGHT = 380
CHART_MARGIN = dict(l=48, r=28, t=56, b=48)


def apply_plotly_theme() -> None:
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="Inter, DM Sans, sans-serif",
                size=13,
                color=TEXT_PRIMARY,
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(
                bgcolor=SURFACE_RAISED,
                font_size=12,
                bordercolor=BORDER_SUBTLE,
                font_family="Inter, DM Sans, sans-serif",
            ),
            margin=CHART_MARGIN,
            title=dict(font=dict(size=15, color=TEXT_PRIMARY), x=0.02, xanchor="left"),
            plot_bgcolor=SURFACE_BASE,
            paper_bgcolor=SURFACE_BASE,
            xaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=1,
                zerolinecolor=BORDER_MEDIUM,
                title_font=dict(size=12, color=TEXT_SECONDARY),
                tickfont=dict(size=11, color=TEXT_MUTED),
            ),
            yaxis=dict(
                gridcolor=BORDER_SUBTLE,
                gridwidth=1,
                zerolinecolor=BORDER_MEDIUM,
                title_font=dict(size=12, color=TEXT_SECONDARY),
                tickfont=dict(size=11, color=TEXT_MUTED),
            ),
        )
    )
    pio.templates.default = "plotly_white+boteco"
```

---

## Task 2: Update .streamlit/config.toml — White Background

**File:** `.streamlit/config.toml` (entire file)

```toml
[theme]
primaryColor = "#2563EB"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F1F5F9"
textColor = "#0F172A"
font = "sans serif"
```

---

## Task 3: Update app.py CSS — Blue Theme + Fix Text Clipping

**File:** `app.py` (lines 31-430 approximately — the entire CSS block in st.markdown)

Replace the entire CSS `:root` variables section with the new color tokens, AND fix the button text clipping:

### 3a: Replace CSS :root variables (lines 37-67)

```css
    :root {
        --brand: #2563EB;
        --brand-dark: #1D4ED8;
        --brand-light: #3B82F6;
        --brand-soft: #DBEAFE;
        --surface: #FFFFFF;
        --surface-elevated: #F8FAFC;
        --surface-raised: #FFFFFF;
        --text: #0F172A;
        --text-secondary: #475569;
        --text-muted: #94A3B8;
        --border-subtle: #E2E8F0;
        --border-medium: #CBD5E1;
        --success-bg: #F0FDF4;
        --success-text: #166534;
        --success-border: #BBF7D0;
        --error-bg: #FEF2F2;
        --error-text: #991B1B;
        --error-border: #FECACA;
        --info-bg: #EFF6FF;
        --info-text: #1E40AF;
        --info-border: #BFDBFE;
        --font-display: 'DM Serif Display', serif;
        --font-body: 'DM Sans', sans-serif;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
        --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;
    }
```

### 3b: Fix button text clipping (lines 115-126)

Change from:
```css
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
```

To:
```css
    .stButton > button {
        font-family: var(--font-body) !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 500 !important;
        transition: all 0.15s ease-in-out !important;
        min-height: 38px !important;
        line-height: 1.4 !important;
        padding: 0.5rem 1rem !important;
    }
```

### 3c: Fix date-display class (search for it in the CSS)

Change the `.date-display` background and border to use white theme colors:

```css
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
    }
```

(Remove the box-shadow from date-display to keep it clean on white background)

---

## Task 4: Update ui_theme.py Plotly backgrounds

The Plotly theme in `ui_theme.py` needs to use white backgrounds:
- `plot_bgcolor=SURFACE_BASE` → `#FFFFFF`
- `paper_bgcolor=SURFACE_BASE` → `#FFFFFF` (not SURFACE_ELEVATED)

---

## Task 5: Fix format_delta — Remove Custom Arrows

**File:** `utils.py` (lines 23-49)

Replace the `format_delta` function to remove the ▲/▼ arrow symbols. Streamlit's `st.metric` with `delta_color="normal"` already provides visual direction via green/red coloring.

Replace lines 23-49 with:

```python
def format_delta(
    current: float, prior: float, is_currency: bool = True, is_percent: bool = False
) -> Optional[str]:
    """Format a delta string with sign prefix for Streamlit color parsing.

    Returns None if prior is None or zero (no comparison possible).
    Always includes sign at start of string so Streamlit parses coloring correctly.
    """
    if prior is None or prior == 0:
        return None
    g = calculate_growth(current, prior)
    change = g["change"]
    pct = g["percentage"]
    if change >= 0:
        sign = "+"
    else:
        sign = "-"
        change = abs(change)
        pct = abs(pct)
    if is_currency:
        return f"{sign}{format_currency(change)} ({sign}{format_percent(pct)})"
    elif is_percent:
        return f"{sign}{format_percent(change)}pp"
    else:
        return f"{sign}{change:,.0f} ({sign}{format_percent(pct)})"
```

---

## Task 6: Update clipboard_ui.py — Blue Buttons

**File:** `clipboard_ui.py`

The `_btn_style` function uses `ui_theme.BRAND_PRIMARY` which will now be blue (#2563EB). No code change needed — it will automatically pick up the new color from ui_theme.py.

However, verify that the inline color values are updated:
- Change `#C2703E` to use the dynamic `c = ui_theme.BRAND_PRIMARY`
- Change `#FFF8F0` to `#FFFFFF` for button text color on primary buttons
- Change `#3D2B1F` to `#0F172A` for secondary button text
- Change `#E0D5C8` to `#E2E8F0` for borders
- Change `rgba(60,40,20,0.08)` to `rgba(0,0,0,0.07)` for box-shadow

---

## Summary of Files to Change

| File | Changes |
|------|---------|
| `ui_theme.py` | New blue palette, white surfaces, slate text colors |
| `.streamlit/config.toml` | Blue primary, white background, slate text |
| `app.py` | CSS :root update, button overflow fix, date-display cleanup |
| `utils.py` | Remove ▲/▼ from format_delta |
| `clipboard_ui.py` | Update inline hex colors to match new palette |

---

## Implementation Order

1. Task 1: ui_theme.py (foundation for all other changes)
2. Task 2: .streamlit/config.toml
3. Task 3: app.py CSS block
4. Task 5: utils.py format_delta
5. Task 6: clipboard_ui.py inline colors
6. Verify: run app, check all tabs
