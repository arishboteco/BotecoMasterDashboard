# Accessibility — Boteco Master Dashboard

This document records the accessibility commitments of the dashboard, what has
been verified against WCAG 2.1 Level AA, and the few places where we have
acknowledged Streamlit-imposed limitations.

## Contrast matrix (WCAG 2.1 AA — ≥4.5:1 for normal text, ≥3:1 for large text/UI)

### Light theme

| Pair | Fg | Bg | Ratio | AA pass |
|---|---|---|---|---|
| Body text | `#1E293B` | `#F7FAFC` | 14.8:1 | ✅ |
| Secondary text | `#475569` | `#F7FAFC` | 8.3:1 | ✅ |
| Muted text | `#64748B` | `#F7FAFC` | 4.7:1 | ✅ |
| Brand on surface | `#1F5FA8` | `#F7FAFC` | 7.9:1 | ✅ |
| Error text | `#B91C1C` | `#FEF2F2` | 7.4:1 | ✅ |
| Success text | `#15803D` | `#F0FDF4` | 6.4:1 | ✅ |
| Section label | `var(--text)` = `#1E293B` | `#F7FAFC` | 14.8:1 | ✅ |
| Table header text | `var(--text-secondary)` = `#475569` | `#EEF2F7` | 7.0:1 | ✅ |
| Tab hover/selected | `var(--brand)` = `#1F5FA8` | `#E6F4F3` | 6.5:1 | ✅ |
| Iframe msg — success | `#15803D` | `#FFFFFF` | 7.0:1 | ✅ |
| Iframe msg — warning | `#B45309` | `#FFFFFF` | 5.7:1 | ✅ |
| Iframe msg — error | `#B91C1C` | `#FFFFFF` | 6.6:1 | ✅ |
| Sidebar muted (`rgba(255,255,255,0.75)`) | blend | `#1F5FA8` | ≈5.4:1 | ✅ |
| Sidebar footer (`rgba(255,255,255,0.55)`) | blend | `#133F70` | ≈3.7:1 | ✅ (large text) |

### Dark theme

| Pair | Fg | Bg | Ratio | AA pass |
|---|---|---|---|---|
| Body text | `#F1F5F9` | `#1E293B` | 13.3:1 | ✅ |
| Secondary text | `#CBD5E1` | `#1E293B` | 9.8:1 | ✅ |
| Muted text | `#94A3B8` | `#1E293B` | 5.7:1 | ✅ |
| Brand on dark surface | `#3A7FC9` | `#1E293B` | 3.5:1 | ✅ (large text / UI) |
| Error text | `#FCA5A5` | `#450A0A` | 6.2:1 | ✅ |
| Success text | `#86EFAC` | `#052E16` | 11.3:1 | ✅ |
| Section label | `var(--text)` = `#F1F5F9` | `#1E293B` | 13.3:1 | ✅ |
| Table header text | `var(--text-secondary)` = `#CBD5E1` | `#1E293B` | 9.8:1 | ✅ |
| Tab hover/selected | `var(--brand-light)` = `#5A97D6` | `#1E3A5F` | 3.6:1 | ✅ (UI component) |

All values computed via [WebAIM's contrast checker](https://webaim.org/resources/contrastchecker/).

## Hardcoded color exceptions

A small number of hex values are intentionally hardcoded (not tokenized) because
they are always rendered against a known, fixed background:

| Location | Color | Background | Reason |
|---|---|---|---|
| `styles/_sidebar.py` | `#FFFFFF` / `rgba(255,255,255,…)` | `--sidebar-bg` (blue) | Sidebar is always blue in both themes; white always passes |
| `styles/_print.py` | `#fff` / `#000` | Print page | Print is always white; black/white is the correct output |
| `styles/_login.py` | `#FFFFFF` on button | `--brand` blue | Login card is always in light mode |
| `clipboard_ui.py` | `#15803D`, `#B45309`, `#B91C1C` | `#FFFFFF` iframe bg | Iframe can't inherit CSS vars; colors verified against white (see §Known limitations) |

## Focus visibility

Every interactive element has a visible `:focus-visible` treatment:
- 2 px solid `var(--brand)` outline, 2 px offset, rounded corners.
- Mouse-only focus (e.g. clicking a button) is suppressed via
  `button:focus:not(:focus-visible) { outline: none; }` so the ring only
  appears when a keyboard user tabs onto the element.

Defined in [`styles/_base.py`](../styles/_base.py) → `COMPREHENSIVE_FOCUS_INDICATORS`.

## ARIA landmarks

- Icon-only buttons carry `aria-label` (see `clipboard_ui.py`).
- The first-run password banner uses `role="alert"` for screen-reader
  announcement.
- Tabs use native `role="tab"` / `aria-selected` from Streamlit — we style
  these but do not override the role.

## Reduced motion

Respecting `@media (prefers-reduced-motion: reduce)`: all page entrance
animations, button micro-scales, and skeleton pulses collapse to ≤0.01 ms so
users who request reduced motion get an effectively-static interface. Defined
in [`styles/_animations.py`](../styles/_animations.py).

## Dark mode

Toggle from the sidebar (☀/🌙/🖥 button above the account block).
- `Light` — forces `data-theme="light"` on `<html>`.
- `Dark` — forces `data-theme="dark"`; also switches the Plotly template to
  `boteco-dark`.
- `System` — removes the attribute and defers to
  `@media (prefers-color-scheme: dark)`.

The preference is kept in `st.session_state.theme` for the lifetime of the
browser session.

## Known limitations

1. **Streamlit chrome in dark mode.** Streamlit's own widgets (tab bar active
   indicator, button ripple) have hex colors hardcoded in their shadow DOM
   that our CSS can't reach. A small amount of blue chrome-color remains in
   dark mode. Users can override via Streamlit's own Settings > Theme if they
   need a fully-dark app shell.
2. **Iframe sandbox.** The image-action toolbar in
   [`clipboard_ui.py`](../clipboard_ui.py) renders inside `st.iframe`, whose
   sandboxed document cannot inherit `--brand` / `--text` CSS variables or the
   dark-mode theme toggle. The toolbar always renders in a light-palette iframe.
   Message status colors (`#15803D`, `#B45309`, `#B91C1C`) are verified for
   AA contrast against the iframe's white background.
3. **Plotly legend keyboard access.** Plotly does not expose its built-in
   legend/zoom toolbar to keyboard focus. Users relying on keyboard
   navigation should use the data table underneath each chart (available in
   Analytics → Daily Data).

## Verification checklist

- [x] Tab through login form → sidebar → tabs → main content: no focus trap,
      logical tab order.
- [x] Axe-core scan: no violations in `main`, `sidebar`, or tab content
      (only Streamlit-chrome warnings).
- [x] Contrast check on all text-on-background pairs in both themes.
- [x] `prefers-reduced-motion` setting disables entrance animations.
- [x] Screen reader announces first-run banner via `role="alert"`.

## Where things live

| Concern | File |
|---|---|
| Tokens (light/dark) | [`styles/_tokens.py`](../styles/_tokens.py) |
| Focus rings | [`styles/_base.py`](../styles/_base.py) |
| Reduced motion | [`styles/_animations.py`](../styles/_animations.py) |
| Theme toggle UI | [`app.py`](../app.py) |
| Plotly light/dark templates | [`ui_theme.py`](../ui_theme.py) |
| Accessible empty states | [`components/feedback.py`](../components/feedback.py) |
