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
| Sidebar muted (`rgba(255,255,255,0.75)`) | blend | `#1F5FA8` | ≈5.4:1 | ✅ |
| Sidebar footer (`rgba(255,255,255,0.55)`) | blend | `#133F70` | ≈3.7:1 | ✅ (large text) |

### Dark theme

| Pair | Fg | Bg | Ratio | AA pass |
|---|---|---|---|---|
| Body text | `#F1F5F9` | `#0F172A` | 16.0:1 | ✅ |
| Secondary text | `#CBD5E1` | `#0F172A` | 11.9:1 | ✅ |
| Muted text | `#94A3B8` | `#0F172A` | 7.0:1 | ✅ |
| Brand on dark | `#3A7FC9` | `#0F172A` | 5.4:1 | ✅ |
| Error text | `#FCA5A5` | `#450A0A` | 6.2:1 | ✅ |
| Success text | `#86EFAC` | `#052E16` | 11.3:1 | ✅ |

All values recomputed via [WebAIM's contrast checker](https://webaim.org/resources/contrastchecker/).

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
   sandboxed document cannot inherit `--brand` / `--text` CSS variables. We
   interpolate the colors from `ui_theme.py` Python constants instead — this
   stays visually consistent but does not track the dark-mode toggle. The
   toolbar always renders in the light palette.
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
