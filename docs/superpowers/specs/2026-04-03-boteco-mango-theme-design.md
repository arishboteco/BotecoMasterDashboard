# Boteco Mango Brand Theme Redesign

**Date:** 2026-04-03
**Status:** Approved
**Type:** Full brand refresh (Option B)

## Overview

Replace the current coral/slate theme with the Boteco Mango brand palette (deep blue, teal, green, yellow) across all UI layers: CSS tokens, Python constants, Plotly charts, matplotlib PNG reports, and inline styles. Swap typography from Sora+DM Sans to Playfair Display+Inter.

## Design Direction

- **Style:** Modern hospitality + tropical minimalism
- **Mood:** Clean, slightly premium, approachable
- **Use case:** Restaurant ops dashboards, inventory, sales analytics

## Color Palette

### Primary Colors
| Name | Hex | Usage |
|---|---|---|
| Deep Royal Blue | `#1F5FA8` | Primary actions, links, brand identity |
| Teal Blue | `#3FA7A3` | Secondary actions, fresh accents |

### Secondary Colors
| Name | Hex | Usage |
|---|---|---|
| Leaf Green | `#6DBE45` | Positive indicators, freshness |
| Warm Yellow / Golden Mustard | `#F4B400` | Warnings, attention |

### Derived Colors
| Name | Hex | Usage |
|---|---|---|
| Brand Dark | `#174A82` | Hover/pressed states |
| Brand Light | `#2A6BB3` | Lighter variant, gradients |
| Brand Secondary Dark | `#2F8C89` | Secondary hover |
| Brand Soft | `#E6F4F3` | Soft backgrounds, row hover |
| Banner Dark | `#1A3A5C` | PNG report banners & totals |
| Table Header | `#EEF2F7` | Table header row background |

### Neutrals
| Name | Hex | Usage |
|---|---|---|
| Main Background | `#F7FAFC` | Soft off-white page bg |
| Card Background | `#FFFFFF` | Card surfaces |
| Text Primary | `#1E293B` | Body text (kept from slate) |
| Text Secondary | `#475569` | Secondary text |
| Text Muted | `#94A3B8` | Muted text |

### Semantic (unchanged)
| Name | Hex | Usage |
|---|---|---|
| Error | `#EF4444` | Negative deltas, destructive |
| Error BG | `#FEF2F2` | Error container background |
| Error Border | `#FECACA` | Error container border |
| Info | `#6366F1` | Info indicators |
| Info BG | `#EFF6FF` | Info container background |
| Info Border | `#C7D2FE` | Info container border |

## Typography

| Role | Font | Current |
|---|---|---|
| Display (headers, KPI values) | Playfair Display | Sora |
| Body (UI text, buttons, tables) | Inter | DM Sans |

Google Fonts import: `Playfair Display:wght@400;500;600;700` + `Inter:wght@400;500;600`

## Files Changed

### 1. `styles.py` — CSS Token System
- Update all `:root` color tokens per palette above
- Add `--brand-secondary` and `--brand-secondary-dark` tokens
- Change `--surface` to `#F7FAFC`, `--surface-elevated` to `#FFFFFF`
- Change `--sidebar-bg` to `#1F5FA8`, `--sidebar-border` to `#2A6BB3`
- Change `--font-display` to `'Playfair Display'`, `--font-body` to `'Inter'`
- Update table header styles: bg `#EEF2F7`, text `#1F5FA8` (was `#334155` bg, white text)
- Update focus rings: `#3FA7A3` outline (was coral `rgba(232,115,74,0.15)`)
- Update row hover: `#E6F4F3` (was `--brand-soft` coral tint)
- Update metric card radius to `--radius-lg` (12px)
- Update Google Fonts import
- Update login CSS tokens to match new palette

### 2. `ui_theme.py` — Python Constants & Plotly Theme
- Update all brand constants to new hex values
- Add `BRAND_SECONDARY = "#3FA7A3"` and `BRAND_SECONDARY_DARK = "#2F8C89"`
- Update `SURFACE_BASE` to `#F7FAFC`, `SURFACE_ELEVATED` to `#FFFFFF`
- Update `BRAND_SUCCESS` to `#3FA7A3`, `BRAND_WARN` to `#F4B400`
- Update `CHART_COLORWAY` to 5-color palette: `["#1F5FA8", "#3FA7A3", "#6DBE45", "#F4B400", "#174A82"]`
- Update Plotly theme font to `"Inter, sans-serif"`

### 3. `sheet_reports.py` — Matplotlib PNG Reports
- Update `C_BRAND` to `#1F5FA8`, `C_BRAND_DARK` to `#174A82`
- Add `C_BANNER = "#1A3A5C"` for section banners and totals rows
- Add `C_HEADER = "#EEF2F7"` for table header row backgrounds
- Update `C_GREEN` to `#6DBE45`, `C_AMBER` to `#F4B400`
- Update `C_PAGE` to `#F7FAFC`
- Change `FONT` to `"Inter"`
- Update `_table_header_row()` to use `C_HEADER` bg with `#1F5FA8` text (instead of `C_NAVY` bg with white text)
- Update section banner `_card()` calls to use `C_BANNER` instead of `C_NAVY`
- Update totals row `_table_data_row()` calls to use `C_BANNER` instead of `C_NAVY`
- Update date label color from `#8C7B6B` to a harmonized muted tone

### 4. `clipboard_ui.py` — Inline Button Styles
- `_btn_style()` focus ring: `outline:2px solid #3FA7A3` (was `#2563EB`)
- `render_image_action_row()` hover: bg `#E6F4F3`, text `#1F5FA8` (was `#DBEAFE`/`#2563EB`)
- `render_image_action_row()` container bg: `#F7FAFC` (was `#F8FAFC`)
- Status message colors: success `#6DBE45`, warning `#F4B400`, error `#EF4444` (was `#5B7F4A`/`#C28B2D`/`#B84233`)

### 5. `tabs/analytics_tab.py` — Chart Color Maps
- Payment mode discrete map: Cash=`#1F5FA8`, GPay=`#3FA7A3`, Zomato=`#6DBE45`, Card=`#F4B400`, Other=`#174A82`
- Meal period discrete map: Lunch=`#3FA7A3`, Dinner=`#1F5FA8`, Breakfast=`#F4B400`
- All `ui_theme.BRAND_PRIMARY` and `ui_theme.BRAND_SUCCESS` references auto-update via token changes
- Weekday analysis target line color: keep gray or shift to `#94A3B8`

## Component Styling

### Sidebar
- Background: `#1F5FA8` (deep blue)
- Right border: `#2A6BB3`
- Top gradient bar: brand blue to amber (`#1F5FA8` → `#F4B400`)
- Icons/text: white (Streamlit default on dark bg)

### Cards / Widgets
- White background (`#FFFFFF`)
- Border radius: 12px
- Shadow: subtle (existing `--shadow-sm`)
- Header text: `#1F5FA8` (deep blue)
- KPI accent left border: `#1F5FA8`

### Tables (web)
- Header row: `#EEF2F7` background, `#1F5FA8` text, uppercase, bold
- Row hover: `#E6F4F3` (light teal tint)
- Borders: `#E2E8F0`

### Tables (PNG reports)
- Header row: `#EEF2F7` background, `#1F5FA8` text, bold
- Data rows: alternating `#FFFFFF` / `#F7FAFC`
- Totals row: `#1A3A5C` background, white text
- Section banners: `#1A3A5C` background, white text, `#1F5FA8` accent bar

### Charts
- Colorway: 5 colors max — Deep Blue, Teal, Green, Yellow, Dark Blue
- Revenue: Deep Blue (`#1F5FA8`)
- Costs/Secondary: Teal (`#3FA7A3`)
- Profit/Positive: Green (`#6DBE45`)
- Alerts/Attention: Yellow (`#F4B400`)
- Background: `#F7FAFC`
- Grid lines: `#E2E8F0`

### Buttons
- Primary: `#1F5FA8`, hover `#174A82`, white text
- Secondary: `#3FA7A3`, hover `#2F8C89`, white text
- Focus ring: teal (`#3FA7A3`)

### Interactions
- Hover: subtle color darkening
- Transitions: 150-200ms ease-in-out (already in place)
- Focus: teal outline

## Migration Notes

- No API changes — only visual tokens and constants
- Chart colorway reduced from 8 to 5 colors; charts with more than 5 series will cycle
- `C_NAVY` in `sheet_reports.py` is split into `C_BANNER` and `C_HEADER` — all usages must be audited
- `BRAND_SUCCESS` changes meaning from teal to brand teal (`#3FA7A3`) — verify all semantic usages are still appropriate
- Login CSS in `styles.py` has its own `:root` block — must be updated in parallel
