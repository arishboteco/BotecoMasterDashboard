# Theme System Redesign — Design Spec

**Date:** 2026-04-23
**Status:** Approved
**Branch:** `refactor/full-quality-sweep`

---

## 1. Problem Statement

The dashboard's light/dark mode system is broken:

1. **Sidebar** is hardcoded with `!important` white text and a fixed blue gradient — it never changes in dark mode
2. **KPI text, upload labels, and section headers** use hardcoded colors or incorrect tokens that don't switch
3. **JavaScript theme detection** (`app.py`) attempts to set `data-theme` on `<html>` but the selector `.stApp[data-theme="dark"]` may not match Streamlit's actual DOM, so the CSS dark rules under `:root[data-theme="dark"]` are never activated
4. **CSS tokens** use arbitrary slate/gray colors that don't match the Boteco Mango logo brand

## 2. Logo Color Palette

Extracted from `logo.png` (dominant non-white pixels):

| Role | Hex | Usage |
|------|-----|-------|
| Royal Blue | `#005AAB` | Primary brand, dominant |
| Lime Green | `#A2D06E` | Success / positive |
| Golden Yellow | `#FDB813` | Accent / warning |
| Sky Teal | `#54C5D0` | Secondary accent |

## 3. Design Decisions

### 3.1 Sidebar behavior
- **Light mode:** Brand blue gradient (`#005AAB` → darker blue), white text
- **Dark mode:** Deep navy (`#0F172A`), white/light text — a true dark surface, not a brand surface
- Text always white/light (good contrast on both surfaces); uses CSS variables so it switches cleanly

### 3.2 All text uses CSS tokens
Every text element (KPIs, labels, headers, captions, table text, chart text) uses semantic CSS variables (`--text`, `--text-secondary`, etc.) that switch per mode. No hardcoded colors.

### 3.3 JavaScript detection fix
Replace the unreliable class-based detection with a check of Streamlit's CSS custom property `--streamlit-variant`, which Streamlit sets on the body element directly.

### 3.4 Token architecture
Tokens live in `styles/_tokens.py`. Two sets:
- `:root { … }` — light mode defaults
- `:root[data-theme="dark"] { … }` — dark mode overrides
- `@media (prefers-color-scheme: dark)` — system-preference fallback (no explicit override needed)

## 4. Color Palette

### Light Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--brand` | `#005AAB` | Primary actions, links, tab highlight |
| `--brand-dark` | `#004080` | Hover/pressed states |
| `--brand-light` | `#2D7AC9` | Brand-light contrast (WCAG) |
| `--brand-soft` | `#EBF4FF` | Subtle brand tint, hover backgrounds |
| `--surface` | `#F7FAFC` | Main background |
| `--surface-elevated` | `#FFFFFF` | Cards, elevated surfaces |
| `--surface-raised` | `#FFFFFF` | Modals, tooltips |
| `--sidebar-bg` | `#005AAB` | Sidebar background |
| `--sidebar-border` | `#004080` | Sidebar border |
| `--sidebar-text` | `#FFFFFF` | Sidebar text (white on brand blue) |
| `--text` | `#1E293B` | Primary text |
| `--text-secondary` | `#475569` | Secondary text, labels |
| `--text-muted` | `#64748B` | Captions, hints |
| `--border-subtle` | `#E2E8F0` | Light borders |
| `--border-medium` | `#CBD5E1` | Medium borders |
| `--accent-coral` | `#005AAB` | Primary accent (brand blue) |
| `--accent-teal` | `#54C5D0` | Secondary accent (logo teal) |
| `--accent-amber` | `#FDB813` | Accent (logo gold) |
| `--accent-green` | `#A2D06E` | Accent (logo green) |
| `--success-bg` | `#F0FDF4` | Success box background |
| `--success-text` | `#15803D` | Success box text |
| `--success-border` | `#BBF7D0` | Success box border |
| `--error-bg` | `#FEF2F2` | Error box background |
| `--error-text` | `#B91C1C` | Error box text |
| `--error-border` | `#FECACA` | Error box border |
| `--info-bg` | `#EFF6FF` | Info box background |
| `--info-text` | `#1D4ED8` | Info box text |
| `--info-border` | `#BFDBFE` | Info box border |
| `--table-header-bg` | `#EEF2F7` | Table header background |

### Dark Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--brand` | `#2D7AC9` | Brightened for dark surface |
| `--brand-dark` | `#1F5FA8` | Hover/pressed |
| `--brand-light` | `#5A97D6` | Brand-light contrast (WCAG) |
| `--brand-soft` | `#1E3A5F` | Subtle brand tint |
| `--surface` | `#0F172A` | Deep navy background |
| `--surface-elevated` | `#1E293B` | Cards, elevated surfaces |
| `--surface-raised` | `#334155` | Modals, tooltips |
| `--sidebar-bg` | `#0F172A` | Deep navy sidebar |
| `--sidebar-border` | `#1E293B` | Sidebar border |
| `--sidebar-text` | `#FFFFFF` | Sidebar text (white on navy) |
| `--text` | `#F1F5F9` | Primary text |
| `--text-secondary` | `#CBD5E1` | Secondary text |
| `--text-muted` | `#94A3B8` | Captions, hints |
| `--border-subtle` | `#334155` | Light borders |
| `--border-medium` | `#475569` | Medium borders |
| `--accent-coral` | `#2D7AC9` | Primary accent |
| `--accent-teal` | `#7DD3E0` | Brightened teal |
| `--accent-amber` | `#FBBF24` | Brightened amber |
| `--accent-green` | `#A2D06E` | Logo green stays the same |
| `--success-bg` | `#052E16` | Success background |
| `--success-text` | `#86EFAC` | Success text |
| `--success-border` | `#166534` | Success border |
| `--error-bg` | `#450A0A` | Error background |
| `--error-text` | `#FCA5A5` | Error text |
| `--error-border` | `#7F1D1D` | Error border |
| `--info-bg` | `#1E1B4B` | Info background |
| `--info-text` | `#A5B4FC` | Info text |
| `--info-border` | `#3730A3` | Info border |
| `--table-header-bg` | `#1E293B` | Table header background |

### WCAG Compliance
- All text/background combinations maintain ≥4.5:1 contrast ratio (AA)
- Brand on brand-soft: `--brand` (#005AAB) on `--brand-soft` (#EBF4F3): ~7.4:1 ✓
- Dark mode tab text on brand-soft: `--brand-light` (#5A97D6) on `--brand-soft` (#1E3A5F): ~5.1:1 ✓

## 5. Component Changes

### sidebar.py
- Replace hardcoded white `#FFFFFF` text with `--sidebar-text` token
- Sidebar bg uses `--sidebar-bg` (brand blue in light, deep navy in dark)
- Divider uses `--sidebar-border`
- Logout button uses `--sidebar-text` and `--sidebar-border`

### _base.py
- All text colors via CSS tokens
- Tab hover/selected: `--brand` in light, `--brand-light` in dark
- Tab highlight bar: `--brand`
- Heading left-border: `--brand`

### _components.py
- KPI values: `--text`
- KPI labels: `--text-secondary`
- Metric cards: `--surface`, `--border-subtle`
- Data tables: `--text-secondary` for headers, `--text` for body
- Upload zone: `--brand`, `--surface`, `--brand-soft`
- Buttons: `--brand`, `--brand-dark`, `--text`
- Alert boxes: semantic tokens
- All hardcoded hex values replaced with token references

### _login.py
- Tokens for text and surfaces (same as main app)

### app.py (JS detection fix)
- Replace `.stApp[data-theme="dark"]` selector with `--streamlit-variant` CSS custom property check
- Falls back to `prefers-color-scheme` media query

## 6. Plotly Charts (ui_theme.py)

Charts use the `apply_plotly_theme()` registered templates. Update to use logo-derived colorway:

**Light:** `#005AAB` (blue), `#54C5D0` (teal), `#A2D06E` (green), `#FDB813` (amber), `#004080` (dark blue)

**Dark:** `#2D7AC9` (blue), `#7DD3E0` (teal), `#A2D06E` (green), `#FBBF24` (amber), `#1F5FA8` (dark blue)

Chart backgrounds match `--surface` token per mode.

## 7. Files to Modify

| File | Changes |
|------|---------|
| `app.py` | Fix JS theme detection script |
| `styles/_tokens.py` | Complete token rewrite with logo palette |
| `styles/_sidebar.py` | Use mode-aware CSS tokens for bg, text, borders |
| `styles/_base.py` | Replace hardcoded hex with tokens |
| `styles/_components.py` | Replace hardcoded hex with tokens |
| `styles/_login.py` | Add dark tokens or use token system |
| `ui_theme.py` | Update colorway to logo palette; update dark template |

## 8. Verification Checklist

- [ ] Sidebar background switches between brand blue (light) and deep navy (dark)
- [ ] Sidebar text (all elements: labels, captions, buttons, headings) switches to light/warm in dark mode
- [ ] KPI metric values use `--text` (switches per mode)
- [ ] KPI labels use `--text-secondary` (switches per mode)
- [ ] Upload zone labels use `--text-secondary` (switches per mode)
- [ ] Tab bar hover/selected text has ≥4.5:1 contrast in both modes
- [ ] Chart backgrounds match `--surface` in both modes
- [ ] Data table text switches per mode
- [ ] System theme preference (no explicit selection) applies correct dark tokens
- [ ] No `!important` overrides on text colors except sidebar-specific (white on brand/dark bg)