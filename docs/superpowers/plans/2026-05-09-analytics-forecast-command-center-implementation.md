# Analytics Forecast Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a forecast-first Analytics tab with redesign-style date selector and mandatory previous-period comparison.

**Architecture:** Extend analytics period logic for new presets and consistent prior-period windows, then reshape tab composition to surface forecasting and ranked actionable recommendations before secondary reconciliation/detail sections.

**Tech Stack:** Python 3.11+, Streamlit, pandas, Plotly, pytest.

---

### Task 1: Period Logic + Tests
- Update `tabs/analytics_logic.py` to support `7D`, `30D`, `MTD`, `QTD`, `Custom` and compute prior window for custom.
- Add/adjust tests in `tests/test_analytics_logic.py`.

### Task 2: Forecast Horizon + Tests
- Update `tabs/forecasting.py` forecast-day mapping for new period labels and optional range-length behavior.
- Add/adjust tests in `tests/test_forecasting.py`.

### Task 3: Actionable Insights Helpers
- Add pure helpers in `tabs/analytics_sections.py` to compute trend deltas and top action cards.
- Add tests in `tests/test_analytics_sections.py` for deterministic insight ranking.

### Task 4: Analytics UI Restructure
- Update `tabs/analytics_tab.py` filter controls to redesign-style segmented presets + custom dates.
- Show explicit current/prior context band and pass comparison data to sections.

### Task 5: Forecast-First Rendering
- Update `tabs/analytics_sections.py` overview/forecast blocks to surface forecast, confidence, reliability, and action cards.
- Keep existing secondary reconciliation/table sections under mobile wrapper hooks.

### Task 6: Validation
- Run targeted test suites.
- Run lint check for touched files.
