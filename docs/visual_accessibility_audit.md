# Visual Accessibility Audit — BotecoMasterDashboard

Date: 2026-04-26

Scope inspected:
- `styles/_tokens.py`
- `styles/_contrast_fix.py`
- `styles/_visual_polish.py`
- `styles/_components.py`
- `styles/_sidebar.py`
- `styles/_base.py`
- `ui_theme.py`

---

## 1) Raw hex colours outside `styles/_tokens.py`

### A. `styles/_contrast_fix.py`
Raw hex values found:
- `#005AAB`, `#004080`, `#2D7AC9`, `#EBF4FF`
- `#FFFFFF`, `#F6FAFE`, `#1E293B`, `#475569`, `#64748B`
- `#E2E8F0`, `#CBD5E1`, `#15803D`, `#B91C1C`, `#F1F5F9`

Notable locations:
- Token redefinition block in `:root, .stApp, .stApp.stAppDark, .stApp.stAppDarkTheme` (lines ~9–28).
- Hard-coded foreground/background states for buttons and sidebar (e.g., lines ~89–128, ~173–199).

### B. `styles/_visual_polish.py`
Raw hex values found:
- `#005AAB`, `#004080`, `#003366`, `#2D7AC9`, `#EBF4FF`
- `#FDB813`, `#54C5D0`, `#A2D06E`
- `#FFFFFF`, `#F6FAFE`, `#E2E8F0`, `#F3F7FC`
- `#1E293B`, `#475569`, `#64748B`, `#CBD5E1`, `#94A3B8`

Notable locations:
- Large token redefinition block that applies to both light and dark wrappers (lines ~12–49).
- Multiple hard-coded white surfaces (`background: #FFFFFF !important`) throughout cards, tabs, inputs, and sidebar (e.g., lines ~53, ~108, ~138, ~166, ~242, ~271).

### C. `styles/_components.py`
Raw hex values found:
- `#FFFFFF` (primary button text)
- `#92400e` (warning info banner text)
- `#fff` (danger/critical style text)

Notable locations:
- Warning banner text color: `.info-banner--warning` (line ~588).
- Explicit white text in danger/utility elements (lines ~723, ~769).

### D. `styles/_sidebar.py`
Raw hex values found:
- `#FFFFFF`
- `#fff`

Notable locations:
- Sidebar logo card and sidebar text/button overrides (lines ~22, ~35, ~43, ~64–66, ~93, ~139).

### E. `styles/_base.py`
- No raw hex colors found.

### F. `ui_theme.py`
Raw hex values found:
- Brand/semantic constants: `#3FA7A3`, `#F4B400`, `#6DBE45`, `#EF4444`, `#6366F1`
- Achievement badges: `#DCFCE7`, `#166534`, `#FEF9C3`, `#854D0E`, `#FEE2E2`, `#991B1B`
- Chart colors: `#FF6B35`, `#22C55E`, `#1F5FA8`, `#174A82`
- Message warning: `#B45309`

---

## 2) Duplicate token definitions

The same CSS custom properties are redefined in both `styles/_contrast_fix.py` and `styles/_visual_polish.py` with identical values:

- `--brand: #005AAB`
- `--brand-dark: #004080`
- `--brand-light: #2D7AC9`
- `--brand-soft: #EBF4FF`
- `--surface: #FFFFFF`
- `--surface-elevated: #FFFFFF`
- `--surface-muted: #F6FAFE`
- `--text: #1E293B`
- `--text-secondary: #475569`
- `--text-muted: #64748B`
- `--border-subtle: #E2E8F0`
- `--border-medium: #CBD5E1`

Impact:
- Creates “shadow token systems” outside canonical `styles/_tokens.py`.
- Increases risk of drift when one file changes and the other is not updated.
- Makes effective runtime token source dependent on stylesheet composition order.

---

## 3) `!important` usage

Counts by file:

- `styles/_visual_polish.py`: **136**
- `styles/_components.py`: **101**
- `styles/_base.py`: **53**
- `styles/_contrast_fix.py`: **46**
- `styles/_sidebar.py`: **18**
- `ui_theme.py`: **0**

Total (scope files excluding `_tokens.py`): **354**

Accessibility/system impact:
- High `!important` usage reduces predictability of component state styling (focus, hover, disabled, selected).
- It can suppress user/OS-level contrast adjustments and makes dark/light theming brittle.
- It raises maintenance cost because safe overrides require even more specificity/`!important`.

---

## 4) Light/dark mode conflicts

### Conflict A: Dark wrappers forced to light tokens
Both files define light values even when dark wrappers are targeted:
- `styles/_contrast_fix.py`: `:root, .stApp, .stApp.stAppDark, .stApp.stAppDarkTheme { ... }`
- `styles/_visual_polish.py`: same pattern.

Result:
- `.stApp.stAppDark` and `.stApp.stAppDarkTheme` still receive light palettes, overriding dark intent from `styles/_tokens.py`.

### Conflict B: Sidebar intent mismatch across layers
- `styles/_sidebar.py` assumes a dark/gradient sidebar with white text.
- `styles/_contrast_fix.py` enforces sidebar background to white and text to dark.
- `styles/_visual_polish.py` also enforces white sidebar shell in places.

Result:
- Depending on injection order, users can see either dark-on-light or light-on-dark combinations unexpectedly.

### Conflict C: Multiple dark-mode strategies at once
Active strategies in scope:
- `:root[data-theme="dark"]`
- `.stApp.stAppDark` / `.stApp.stAppDarkTheme`
- `@media (prefers-color-scheme: dark)`

Result:
- Competing entry points increase chance of partially-applied themes and mixed state colors.

---

## 5) Likely WCAG contrast issues

Potential issues (manual review + quick ratio checks):

1. **Muted text on pale gray surfaces is near AA threshold for normal text**
   - Example pair: `#64748B` on `#F1F5F9` ≈ **4.34:1** (below 4.5 AA for normal body text).
   - Appears in disabled/secondary contexts and may fail at smaller font sizes.

2. **White text on accent-teal/accent-green would fail if used for text**
   - `#FFFFFF` on `#54C5D0` ≈ **2.04:1**
   - `#FFFFFF` on `#A2D06E` ≈ **1.78:1**
   - These colors appear as accents/tokens; if applied to button text or badge text they would fail.

3. **Theme-order-dependent sidebar contrast risk**
   - White text rules in `_sidebar.py` plus white sidebar backgrounds in `_contrast_fix.py`/`_visual_polish.py` can produce low contrast if selector precedence changes.

4. **Focus ring color mismatch from older accent**
   - `_base.py` focus shadow uses `rgba(63,167,163,0.25)` (teal), while primary semantic focus is brand blue.
   - This is more of a consistency/visibility risk than a guaranteed failure, but it weakens predictable focus affordance.

---

## 6) Recommendations for a token-only design system

### Priority 1 — Remove shadow token roots
- Keep **all source-of-truth color values only in `styles/_tokens.py`**.
- In `_contrast_fix.py` and `_visual_polish.py`, replace token value declarations with consumption-only (`var(--token)`), no new hard-coded hex.

### Priority 2 — Define semantic tokens for state-specific UI
Add/standardize these tokens in `_tokens.py` to eliminate raw values elsewhere:
- `--warning-bg`, `--warning-text`, `--warning-border`
- `--focus-ring-color`, `--focus-ring-shadow`
- `--disabled-bg`, `--disabled-text`, `--disabled-border`
- `--sidebar-surface`, `--sidebar-text`, `--sidebar-muted`, `--sidebar-button-*`

### Priority 3 — Single dark-mode activation model
Choose one primary mechanism (recommended: `:root[data-theme="dark"]`) and keep others as thin compatibility aliases only.
- Avoid assigning light token values inside `.stApp.stAppDark*` wrappers.
- Ensure dark theme token values are not overwritten in late-loaded CSS layers.

### Priority 4 — Reduce `!important` footprint
- Restrict `!important` to narrowly-scoped Streamlit/BaseWeb collisions only.
- Use CSS layer order and selector architecture (component class wrappers) for normal precedence.
- Track remaining `!important` rules with a “must-justify” comment convention.

### Priority 5 — Contrast guardrails in CI
- Add a token-level contrast test script for key pairs (text/surface, primary/on-primary, error/surface, etc.).
- Enforce AA >= 4.5:1 for normal text and >= 3:1 for large text/UI components.

### Priority 6 — Rationalize `ui_theme.py`
- Replace direct hex constants in `ui_theme.py` with token aliases sourced from `_tokens.py`.
- If chart palettes intentionally differ, define chart tokens once in `_tokens.py` and import from there.

---

## Suggested remediation sequence
1. Consolidate token definitions in `_tokens.py`.
2. Replace raw hex usage in `_contrast_fix.py`, `_visual_polish.py`, `_sidebar.py`, `_components.py`, `ui_theme.py` with semantic vars/constants.
3. Remove conflicting dark-mode overrides from late polish/fix layers.
4. Trim `!important` usage and verify keyboard focus styling.
5. Add automated contrast checks and baseline visual regression snapshots.
