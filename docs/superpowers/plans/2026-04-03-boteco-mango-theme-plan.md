# Boteco Mango Brand Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the coral/slate theme with the Boteco Mango brand palette (deep blue, teal, green, yellow) and swap typography from Sora+DM Sans to Playfair Display+Inter across all UI layers.

**Architecture:** Token-first approach — update `ui_theme.py` (Python constants) and `styles.py` (CSS tokens) first, then update dependent files (`sheet_reports.py`, `clipboard_ui.py`, `analytics_tab.py`) to use the new values. Each file change is self-contained and testable.

**Tech Stack:** Python 3.11+, Streamlit, CSS custom properties, Plotly, matplotlib, pytest

---

### Task 1: Update `ui_theme.py` — Python Constants & Plotly Theme

**Files:**
- Modify: `ui_theme.py` (entire file, 87 lines)

- [ ] **Step 1: Update brand palette constants**

Replace lines 6-14 with new brand values:

```python
# -- Brand palette (Boteco Mango) -----------------------------------------------
BRAND_PRIMARY = "#1F5FA8"  # Deep Royal Blue — primary actions, links
BRAND_DARK = "#174A82"  # Dark blue — hover/pressed
BRAND_LIGHT = "#2A6BB3"  # Lighter blue — gradients
BRAND_SOFT = "#E6F4F3"  # Soft teal tint — backgrounds
BRAND_SECONDARY = "#3FA7A3"  # Teal Blue — secondary actions
BRAND_SECONDARY_DARK = "#2F8C89"  # Dark teal — secondary hover
BRAND_SUCCESS = "#3FA7A3"  # Teal — positive deltas
BRAND_WARN = "#F4B400"  # Golden Mustard — warning
BRAND_ERROR = "#EF4444"  # Red — negative deltas, destructive
BRAND_INFO = "#6366F1"  # Indigo — info
```

- [ ] **Step 2: Update surface palette constants**

Replace lines 16-19:

```python
# -- Surface & neutral palette -------------------------------------------------
SURFACE_BASE = "#F7FAFC"  # Main background — soft off-white
SURFACE_ELEVATED = "#FFFFFF"  # Cards — white
SURFACE_RAISED = "#FFFFFF"  # Modals, tooltips
```

- [ ] **Step 3: Update chart colorway**

Replace lines 36-46:

```python
# -- Chart colorway — Boteco Mango brand, 5-color palette ---------------------
CHART_COLORWAY = [
    "#1F5FA8",  # deep royal blue (primary)
    "#3FA7A3",  # teal blue
    "#6DBE45",  # leaf green
    "#F4B400",  # golden mustard
    "#174A82",  # dark blue
]
```

- [ ] **Step 4: Update Plotly theme font and hoverlabel font**

In `apply_plotly_theme()`, change both font family references from `"DM Sans, sans-serif"` to `"Inter, sans-serif"`:

```python
def apply_plotly_theme() -> None:
    pio.templates["boteco"] = go.layout.Template(
        layout=dict(
            font=dict(
                family="Inter, sans-serif",
                size=13,
                color=TEXT_PRIMARY,
            ),
            colorway=CHART_COLORWAY,
            hoverlabel=dict(
                bgcolor=SURFACE_RAISED,
                font_size=12,
                bordercolor=BORDER_SUBTLE,
                font_family="Inter, sans-serif",
            ),
            ...
```

- [ ] **Step 5: Update module docstring**

Change line 1 from `"Shared UI constants and Plotly defaults for the dashboard."` to keep it accurate (no change needed, it's still accurate). Update the comment on line 6 from `"# -- Brand palette (Slate & Coral)"` to `"# -- Brand palette (Boteco Mango)"`.

- [ ] **Step 6: Verify no other files import constants that were renamed**

Run: `rg "BRAND_" --type py` to confirm existing imports (`BRAND_PRIMARY`, `BRAND_SUCCESS`, `BRAND_WARN`, `BRAND_ERROR`, `CHART_COLORWAY`, `CHART_HEIGHT`, `CHART_MARGIN`, `SURFACE_BASE`, `SURFACE_ELEVATED`, `SURFACE_RAISED`, `TEXT_PRIMARY`, `TEXT_SECONDARY`, `TEXT_MUTED`, `BORDER_SUBTLE`, `BORDER_MEDIUM`) still exist with same names. The two new constants (`BRAND_SECONDARY`, `BRAND_SECONDARY_DARK`) are additive.

---

### Task 2: Update `styles.py` — CSS Token System

**Files:**
- Modify: `styles.py` (entire file, 774 lines)

- [ ] **Step 1: Update Google Fonts import**

Change line 10 from:
```css
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap');
```
to:
```css
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');
```

- [ ] **Step 2: Update `:root` brand palette tokens**

Replace lines 27-30:
```css
--brand: #1F5FA8;
--brand-dark: #174A82;
--brand-light: #2A6BB3;
--brand-soft: #E6F4F3;
```

- [ ] **Step 3: Update `:root` surface palette tokens**

Replace lines 33-37:
```css
--surface: #F7FAFC;
--surface-elevated: #FFFFFF;
--surface-raised: #FFFFFF;
--sidebar-bg: #1F5FA8;
--sidebar-border: #2A6BB3;
```

- [ ] **Step 4: Update `:root` accent color tokens**

Replace lines 49-53:
```css
--accent-coral: #1F5FA8;
--accent-teal: #3FA7A3;
--accent-amber: #F4B400;
--accent-indigo: #6DBE45;
--accent-slate: #1F5FA8;
```

- [ ] **Step 5: Update `:root` typography tokens**

Replace lines 67-68:
```css
--font-display: 'Playfair Display', sans-serif;
--font-body: 'Inter', sans-serif;
```

- [ ] **Step 6: Update data table header styles**

Replace lines 412-420 (the `[data-testid="stDataFrame"] th` block):
```css
[data-testid="stDataFrame"] th {
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    color: #1F5FA8 !important;
    background-color: #EEF2F7 !important;
    border-bottom: none !important;
}
```

- [ ] **Step 7: Update focus ring styles**

Replace lines 668-673:
```css
.stTextInput input:focus,
.stTextArea textarea:focus,
.stSelectbox [data-baseweb="select"]:focus-within {
    border-color: var(--brand) !important;
    box-shadow: 0 0 0 3px rgba(63,167,163,0.25) !important;
}
```

- [ ] **Step 8: Update upload zone hover shadow**

Replace line 398 (the `box-shadow` in `.upload-zone:hover`):
```css
box-shadow: 0 0 0 4px rgba(31,95,168,0.1);
```

- [ ] **Step 9: Update sidebar gradient bar**

Line 482 already uses `var(--brand)` and `var(--accent-amber)` which now resolve to `#1F5FA8` and `#F4B400` — no code change needed, but verify the gradient reads as blue-to-amber.

- [ ] **Step 10: Update metric card radius**

Change line 329 from `border-radius: var(--radius-md)` to `border-radius: var(--radius-lg)` in the `.metric-card` class.

- [ ] **Step 11: Update login CSS**

Replace the `get_login_css()` function's `:root` block (lines 724-730):
```css
:root {
    --brand: #1F5FA8;
    --brand-dark: #174A82;
    --login-surface: #FFFFFF;
    --login-border: #E2E8F0;
    --text: #1E293B;
}
```

Update the Google Fonts import (line 723):
```css
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');
```

Update the font-family in button styles (line 751):
```css
font-family: 'Inter', sans-serif;
```

Update the h1 font-family (line 763):
```css
font-family: 'Playfair Display', sans-serif !important;
```

Update the h3 font-family (line 767):
```css
font-family: 'Inter', sans-serif !important;
```

Update the hover box-shadow (line 756):
```css
box-shadow: 0 4px 6px rgba(31, 95, 168, 0.2);
```

Update the focus box-shadow (line 760):
```css
box-shadow: 0 0 0 3px rgba(63, 167, 163, 0.25) !important;
```

- [ ] **Step 12: Run the app to visually verify**

Run: `streamlit run app.py` and check:
- Sidebar has deep blue background
- Headers use Playfair Display font
- Tables have light grey headers with blue text
- Primary buttons are deep blue
- Focus rings are teal

---

### Task 3: Update `sheet_reports.py` — Matplotlib PNG Reports

**Files:**
- Modify: `sheet_reports.py` (1530 lines)

- [ ] **Step 1: Update module docstring**

Replace lines 1-20 with updated design language:
```python
"""
Boteco EOD Report — PNG image generator and WhatsApp text formatter.

Design language (Boteco Mango):
  - Brand blue           (#1F5FA8)
  - Brand dark           (#174A82)
  - Banner dark          (#1A3A5C)
  - Table header         (#EEF2F7)
  - Body text            (#1E293B)
  - Muted text           (#94A3B8)
  - Page bg              (#F7FAFC)
  - Card bg              (#FFFFFF)
  - Border               (#E2E8F0)
  - Leaf green           (#6DBE45)
  - Golden mustard       (#F4B400)
  - Red error            (#EF4444)

The composite PNG is built with matplotlib drawing primitives
(patches + text), not tables, so every element can be positioned
and styled independently.
"""
```

- [ ] **Step 2: Update palette constants**

Replace lines 34-49:
```python
# -- Palette (Boteco Mango) ---------------------------------------------------
C_PAGE = "#F7FAFC"  # Main background — soft off-white
C_CARD = "#FFFFFF"  # Card background — white
C_BRAND = "#1F5FA8"  # Deep Royal Blue — primary actions, accent bars
C_BRAND_DARK = "#174A82"  # Dark blue — hover/pressed
C_BANNER = "#1A3A5C"  # Dark blue-green — section banners & totals rows
C_HEADER = "#EEF2F7"  # Light grey — table header row backgrounds
C_NAVY = "#1E293B"  # Slate 800 (body text)
C_SLATE = "#1E293B"  # Slate 800 (body text)
C_MUTED = "#94A3B8"  # Slate 400 (muted text)
C_BORDER = "#E2E8F0"  # Slate 200 (card borders)
C_BAND = "#F7FAFC"  # Soft off-white (alternating rows, matches page)
C_GREEN = "#6DBE45"  # Leaf green — positive/achievement
C_AMBER = "#F4B400"  # Golden mustard — warning
C_RED = "#EF4444"  # Red — negative/discount
C_WHITE = "#FFFFFF"  # White

FONT = "Inter"
DPI = 150
```

- [ ] **Step 3: Update `_table_header_row` default bg and text color**

Change the function signature on line 190:
```python
def _table_header_row(ax, x, y, cols, widths, row_h=0.048, bg=C_HEADER, font_size=None):
```

Update the text color inside the function. Find the `_label` call inside `_table_header_row` (around line 210-219) and change `color=C_WHITE` to `color=C_BRAND`:

```python
        _label(
            ax,
            px,
            y + row_h - 0.010,
            col,
            size=fs,
            color=C_BRAND,
            weight="bold",
            ha=ha,
        )
```

- [ ] **Step 4: Update all banner `_card()` calls from `C_NAVY` to `C_BANNER`**

These are section header banner cards. Change `color=C_NAVY, border=C_NAVY` to `color=C_BANNER, border=C_BANNER` at these lines:
- Line 318: `_section_sales_summary` banner
- Line 581: `_section_category` banner
- Line 722: `_section_service` banner
- Line 830: `_section_footfall` banner
- Line 961: `_section_footfall_metrics` banner

Each change:
```python
# Before:
_card(ax, 0, banner_y, 1.0, banner_h, color=C_NAVY, border=C_NAVY)
# After:
_card(ax, 0, banner_y, 1.0, banner_h, color=C_BANNER, border=C_BANNER)
```

- [ ] **Step 5: Update all totals row `_table_data_row()` calls from `C_NAVY` to `C_BANNER`**

These are summary/total rows with white text. Change `bg=C_NAVY` to `bg=C_BANNER` at these lines:
- Line 482: "EOD Net Total" row in sales summary
- Line 659: Category totals row
- Line 812: Service totals row
- Line 913: Footfall totals row

Each change:
```python
# Before:
_table_data_row(ax, ..., bg=C_NAVY, bold=True, text_color=C_WHITE, ...)
# After:
_table_data_row(ax, ..., bg=C_BANNER, bold=True, text_color=C_WHITE, ...)
```

- [ ] **Step 6: Update date label muted color in banners**

The date label in banners uses `#8C7B6B` (warm brown). Change to a harmonized muted tone `#8BA3BD` (muted blue-grey) at these lines:
- Line 335: `_section_sales_summary` date
- Line 592: `_section_category` date
- Line 733: `_section_service` date
- Line 841: `_section_footfall` location name
- Line 972: `_section_footfall_metrics` location name

Each change:
```python
# Before:
_label(ax, 0.012, banner_top - 0.045, day_lbl, size=9.0, color="#8C7B6B")
# After:
_label(ax, 0.012, banner_top - 0.045, day_lbl, size=9.0, color="#8BA3BD")
```

- [ ] **Step 7: Update composite image background color**

Change line 1407 from:
```python
composite = PILImage.new("RGB", (max_w, total_h), color=(248, 250, 252))
```
to:
```python
composite = PILImage.new("RGB", (max_w, total_h), color=(247, 250, 252))
```
(RGB for `#F7FAFC` is 247, 250, 252 — previously was 248, 250, 252 for `#F8FAFC`)

- [ ] **Step 8: Verify the PNG report renders correctly**

Run a quick test by importing the module:
```bash
python -c "import sheet_reports; print('sheet_reports imports OK')"
```

---

### Task 4: Update `clipboard_ui.py` — Inline Button Styles

**Files:**
- Modify: `clipboard_ui.py` (579 lines)

- [ ] **Step 1: Update focus ring color in `_btn_style()`**

Change line 74:
```python
# Before:
focus_style = "outline:2px solid #2563EB;outline-offset:2px;"
# After:
focus_style = "outline:2px solid #3FA7A3;outline-offset:2px;"
```

- [ ] **Step 2: Update focus ring color in `_icon_btn_style()`**

Change line 97:
```python
# Before:
focus_style = "outline:2px solid #2563EB;outline-offset:2px;"
# After:
focus_style = "outline:2px solid #3FA7A3;outline-offset:2px;"
```

- [ ] **Step 3: Update font family in `_btn_style()`**

Change lines 79 and 88 from `'DM Sans'` to `'Inter'`:
```python
# Line 79 (primary button):
f"font-family:'Inter',sans-serif;"
# Line 88 (secondary button):
"font-family:'Inter',sans-serif;"
```

- [ ] **Step 4: Update `render_image_action_row()` inline styles**

Change the action button container background (line 140):
```css
/* Before: */
background: #F8FAFC;
/* After: */
background: #F7FAFC;
```

Change the hover state (lines 163-164):
```css
/* Before: */
background: #DBEAFE;
color: #2563EB;
/* After: */
background: #E6F4F3;
color: #1F5FA8;
```

Change the success message color (line 175):
```html
<!-- Before: -->
<span id="{uid}_msg" style="font-size:0.75rem;margin-left:0.5rem;color:#166534;"></span>
<!-- After: -->
<span id="{uid}_msg" style="font-size:0.75rem;margin-left:0.5rem;color:#6DBE45;"></span>
```

- [ ] **Step 5: Update `render_share_images_button()` status message colors**

Change all hardcoded status colors in the JavaScript:
- Line 523: `msgEl.style.color = "#5B7F4A";` → `msgEl.style.color = "#6DBE45";`
- Line 530: `msgEl.style.color = "#5B7F4A";` → `msgEl.style.color = "#6DBE45";`
- Line 533: `msgEl.style.color = "#C28B2D";` → `msgEl.style.color = "#F4B400";`
- Line 537: `msgEl.style.color = "#C28B2D";` → `msgEl.style.color = "#F4B400";`
- Line 552: `msgEl.style.color = "#5B7F4A";` → `msgEl.style.color = "#6DBE45";`
- Line 555: `msgEl.style.color = "#C28B2D";` → `msgEl.style.color = "#F4B400";`
- Line 559: `msgEl.style.color = "#C28B2D";` → `msgEl.style.color = "#F4B400";`
- Line 564: `msgEl.style.color = "#B84233";` → `msgEl.style.color = "#EF4444";`

- [ ] **Step 6: Verify imports still work**

```bash
python -c "import clipboard_ui; print('clipboard_ui imports OK')"
```

---

### Task 5: Update `tabs/analytics_tab.py` — Chart Color Maps

**Files:**
- Modify: `tabs/analytics_tab.py` (657 lines)

- [ ] **Step 1: Update payment mode discrete color map**

Replace lines 289-295:
```python
# Before:
color_discrete_map={
    "Cash": ui_theme.BRAND_PRIMARY,
    "GPay": "#0369a1",
    "Zomato": "#be185d",
    "Card": "#7c3aed",
    "Other": "#475569",
},
# After:
color_discrete_map={
    "Cash": ui_theme.BRAND_PRIMARY,       # #1F5FA8 — deep royal blue
    "GPay": ui_theme.BRAND_SECONDARY,     # #3FA7A3 — teal blue
    "Zomato": "#6DBE45",                   # leaf green
    "Card": ui_theme.BRAND_WARN,           # #F4B400 — golden mustard
    "Other": ui_theme.BRAND_DARK,          # #174A82 — dark blue
},
```

- [ ] **Step 2: Update meal period discrete color map (first occurrence)**

Replace lines 421-425:
```python
# Before:
color_discrete_map={
    "Lunch": ui_theme.BRAND_SUCCESS,
    "Dinner": ui_theme.BRAND_PRIMARY,
    "Breakfast": ui_theme.BRAND_WARN,
},
# After:
color_discrete_map={
    "Lunch": ui_theme.BRAND_SECONDARY,    # #3FA7A3 — teal
    "Dinner": ui_theme.BRAND_PRIMARY,     # #1F5FA8 — deep blue
    "Breakfast": ui_theme.BRAND_WARN,     # #F4B400 — golden mustard
},
```

- [ ] **Step 3: Update meal period discrete color map (second occurrence)**

Replace lines 441-445 (same change as Step 2):
```python
color_discrete_map={
    "Lunch": ui_theme.BRAND_SECONDARY,
    "Dinner": ui_theme.BRAND_PRIMARY,
    "Breakfast": ui_theme.BRAND_WARN,
},
```

- [ ] **Step 4: Verify imports**

```bash
python -c "from tabs.analytics_tab import render; print('analytics_tab imports OK')"
```

---

### Task 6: Run Tests & Verify

**Files:**
- No file changes — verification only

- [ ] **Step 1: Run existing tests**

```bash
pytest tests/ -v
```

Expected: All existing tests pass (theme changes should not affect parser logic).

- [ ] **Step 2: Verify all modules import cleanly**

```bash
python -c "
import ui_theme
import styles
import sheet_reports
import clipboard_ui
from tabs.analytics_tab import render
print('All modules import OK')
print(f'BRAND_PRIMARY: {ui_theme.BRAND_PRIMARY}')
print(f'CHART_COLORWAY: {ui_theme.CHART_COLORWAY}')
print(f'BRAND_SECONDARY: {ui_theme.BRAND_SECONDARY}')
"
```

Expected output:
```
All modules import OK
BRAND_PRIMARY: #1F5FA8
CHART_COLORWAY: ['#1F5FA8', '#3FA7A3', '#6DBE45', '#F4B400', '#174A82']
BRAND_SECONDARY: #3FA7A3
```

- [ ] **Step 3: Quick smoke test — generate a sample PNG report**

```bash
python -c "
from sheet_reports import generate_sheet_style_report_image
data = {
    'date': '2026-04-03',
    'gross_total': 50000,
    'net_total': 45000,
    'covers': 120,
    'turns': 3.0,
    'apc': 375,
    'pct_target': 90,
    'target': 50000,
    'cash_sales': 10000,
    'gpay_sales': 15000,
    'zomato_sales': 8000,
    'card_sales': 10000,
    'other_sales': 2000,
    'cgst': 1125,
    'sgst': 1125,
    'service_charge': 0,
    'discount': 0,
    'complimentary': 0,
    'mtd_total_covers': 2400,
    'mtd_net_sales': 900000,
    'mtd_avg_daily': 45000,
    'mtd_pct_target': 85,
    'mtd_target': 1050000,
    'mtd_complimentary': 5000,
    'mtd_discount': 10000,
    'categories': [{'category': 'Food', 'amount': 25000}, {'category': 'Liquor', 'amount': 15000}],
    'services': [{'type': 'Dinner', 'amount': 30000}, {'type': 'Lunch', 'amount': 15000}],
}
result = generate_sheet_style_report_image(data, 'Boteco Bangalore')
print(f'PNG generated: {len(result.getvalue())} bytes')
"
```

Expected: PNG generated without errors, size > 0 bytes.

- [ ] **Step 4: Commit**

```bash
git add ui_theme.py styles.py sheet_reports.py clipboard_ui.py tabs/analytics_tab.py
git commit -m "feat: rebrand theme to Boteco Mango palette (blue/teal/green/yellow) + Playfair Display + Inter fonts"
```
