# Visual QA Checklist for UI Pull Requests

Use this checklist for **every PR that changes UI**. Capture screenshots (desktop + mobile when relevant) and verify visual consistency before requesting review.

## Core App Screens

- [ ] **Login screen**
  - [ ] Branding/logo renders correctly.
  - [ ] Username/password fields align and have consistent spacing.
  - [ ] Login action states are visible (default/hover/disabled/loading).
  - [ ] Error message styling is readable and non-overlapping.

- [ ] **Sidebar**
  - [ ] Sidebar opens/renders consistently across pages.
  - [ ] Navigation labels are readable and not truncated.
  - [ ] Active item state is visually distinct.
  - [ ] Collapse/expand behavior does not break layout.

- [ ] **Upload tab**
  - [ ] File inputs and upload controls are aligned.
  - [ ] Status/progress indicators are visible and understandable.
  - [ ] Success/error states are styled consistently.

- [ ] **Report tab**
  - [ ] Report filters, selectors, and actions align cleanly.
  - [ ] Report preview/output area has stable spacing and typography.
  - [ ] Export/download controls remain visible and clickable.

- [ ] **Analytics tab**
  - [ ] KPI cards are aligned and values are readable.
  - [ ] Date filters and grouping controls are visually consistent.
  - [ ] Chart legends, labels, and tooltips are legible.

- [ ] **Settings tab**
  - [ ] Settings groups/sections are clearly separated.
  - [ ] Toggles/selectors/inputs align and have consistent sizes.
  - [ ] Save/update feedback is visible and correctly styled.

## Cross-Cutting UI Components

- [ ] **Mobile layout**
  - [ ] Layout is usable on narrow widths (e.g., 320px, 375px, 768px).
  - [ ] No horizontal overflow or clipped controls.
  - [ ] Tap targets are large enough and have adequate spacing.

- [ ] **Buttons**
  - [ ] Primary/secondary/destructive variants are visually distinct.
  - [ ] Hover, focus, disabled, and loading states are all verified.

- [ ] **Tabs**
  - [ ] Active and inactive tab states are clearly differentiated.
  - [ ] Tab content switches without layout jumps or overlap.

- [ ] **Forms**
  - [ ] Labels are present and tied to inputs.
  - [ ] Required, invalid, and helper text styles are consistent.
  - [ ] Focus indicators are visible via keyboard navigation.

- [ ] **Alerts**
  - [ ] Info/success/warning/error styles are consistent.
  - [ ] Alert text wraps correctly and remains readable.

- [ ] **Tables**
  - [ ] Header/body alignment is correct.
  - [ ] Dense data remains legible at typical zoom levels.
  - [ ] Empty/loading/error states are handled visually.

- [ ] **Charts**
  - [ ] Axis labels and ticks are readable.
  - [ ] Color usage is consistent and non-ambiguous.
  - [ ] Tooltips/legends do not hide critical data.

- [ ] **Dark mode (if supported)**
  - [ ] All key screens render without low-contrast text.
  - [ ] Icons/borders/dividers remain visible.
  - [ ] States (hover/focus/active/disabled) remain distinguishable.

## Accessibility Reminders (WCAG Contrast)

- [ ] Verify normal text contrast is at least **4.5:1** (WCAG AA).
- [ ] Verify large text (18pt+ or 14pt bold+) is at least **3:1**.
- [ ] Verify UI component boundaries and focus indicators are perceivable.
- [ ] Do not rely on color alone to communicate meaning.

## PR Evidence

- [ ] Attach before/after screenshots for changed UI.
- [ ] Include desktop viewport and mobile viewport screenshots.
- [ ] List known visual regressions (if any) in PR description.
