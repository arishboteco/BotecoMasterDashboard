
# Design System: Visual Accessibility Standard

This document defines the accessibility baseline for visual design decisions in the BotecoMasterDashboard app.

## WCAG Contrast Targets

All UI and content colours must meet or exceed these contrast ratios:

- **Normal text:** minimum **4.5:1**
- **Large text:** minimum **3:1**
- **UI components, borders, and focus states:** minimum **3:1**

## Approved Semantic Colour Tokens

Use the following semantic tokens for colour decisions:

- `background`
- `surface`
- `surface-elevated`
- `text-primary`
- `text-secondary`
- `text-muted`
- `border-subtle`
- `border-strong`
- `primary`
- `primary-hover`
- `primary-soft`
- `success-bg`
- `success-text`
- `warning-bg`
- `warning-text`
- `error-bg`
- `error-text`
- `info-bg`
- `info-text`

## Implementation Rules

1. **No raw hex colours outside token files** unless explicitly justified in code comments and reviewed.
2. **No new `!important` declarations** unless interacting with Streamlit/BaseWeb generated selectors.
3. **Do not define colour inside tab/component files** if an approved token already exists.

## Scope and Rollout

- This standard is documentation-only for now.
- Runtime CSS is intentionally unchanged in this update.

## Button State Tokens

Use button tokens instead of component-local hard-coded colour declarations.

### Shared/default button
- Default: `--btn-default-bg`, `--btn-default-fg`, `--btn-default-border`
- Hover: `--btn-default-hover-bg`, `--btn-default-hover-fg`, `--btn-default-hover-border`

### Primary button
- Default: `--btn-primary-bg`, `--btn-primary-fg`, `--btn-primary-border`
- Hover: `--btn-primary-hover-bg`, `--btn-primary-hover-fg`, `--btn-primary-hover-border`

### Disabled button
- Use: `--btn-disabled-bg`, `--btn-disabled-fg`, `--btn-disabled-border`
- Applies consistently to standard, download, and form-submit buttons.

### Download button
- Default: `--btn-download-bg`, `--btn-download-fg`, `--btn-download-border`
- Hover: `--btn-download-hover-bg`, `--btn-download-hover-fg`, `--btn-download-hover-border`

### Form submit button
- Default: `--btn-form-submit-bg`, `--btn-form-submit-fg`, `--btn-form-submit-border`
- Hover: `--btn-form-submit-hover-bg`, `--btn-form-submit-hover-fg`, `--btn-form-submit-hover-border`

### Sidebar button
- Default: `--btn-sidebar-bg`, `--btn-sidebar-fg`, `--btn-sidebar-border`
- Hover: `--btn-sidebar-hover-bg`, `--btn-sidebar-hover-fg`, `--btn-sidebar-hover-border`

### Nested labels inside buttons

All nested `p`/`span` labels in Streamlit button render paths must inherit foreground color:
- `.stButton > button p/span`
- `.stDownloadButton > button p/span`
- `.stFormSubmitButton > button p/span`
- sidebar button labels under `[data-testid="stSidebar"]`

## Tab and Navigation State Tokens

Tab styling must be token-driven and centralized (no per-component hard-coded tab colors).

### Required states
- Inactive tab: `--tab-inactive-bg`, `--tab-inactive-fg`, `--tab-inactive-border`
- Hover tab: `--tab-hover-bg`, `--tab-hover-fg`, `--tab-hover-border`
- Active tab: `--tab-active-bg`, `--tab-active-fg`, `--tab-active-border`
- Focus state: `--tab-focus-ring`

### Contrast requirement
- Active tab text/background must meet **WCAG AA normal text contrast (≥ 4.5:1)**.
- Do not assume white text is valid by default; only use it when the paired background token is verified to meet the ratio target.

### Selector and duplication guidance
- Keep tab behavior in one place (`styles/_base.py` tab refinement block).
- Keep nested tab label inheritance in the contrast safety layer (`styles/_contrast_fix.py`).
- Avoid redefining tab state colors in component modules unless adding new tokens in `styles/_tokens.py`.
