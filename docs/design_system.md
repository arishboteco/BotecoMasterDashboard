
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
