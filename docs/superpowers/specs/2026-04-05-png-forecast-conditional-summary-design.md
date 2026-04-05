## Title
PNG Forecasting, Conditional Formatting, and Verbose Daily Summary (Phase 1)

## Objective
Enhance the existing EOD PNG report (without redesigning layout) so both outlet managers and leadership can quickly answer:
- Are we on pace for month target?
- What is likely month-end outcome if current pace continues?
- What are today’s key operational/profitability signals?

This phase adds three capabilities only:
1. Sales forecasting block
2. Conditional formatting for key metrics
3. Verbose daily summary narrative

## Scope
### In scope
- Add forecast KPI block to existing PNG report generation in `sheet_reports.py`
- Add RAG (green/amber/red) status logic for selected metrics
- Add structured verbose daily summary text in PNG
- Reuse summary logic in WhatsApp text output for consistency
- Add tests for calculations, threshold mapping, and summary fallback behavior

### Out of scope
- PNG layout redesign
- New analytics tab UI/charts
- Advanced forecasting models (seasonality decomposition, confidence intervals)

## Current System Context
- PNG report generation is implemented in `sheet_reports.py` via drawing primitives and section builders.
- WhatsApp text is generated in `generate_whatsapp_text()` in `sheet_reports.py`.
- Existing palette already includes semantic colors: `C_GREEN`, `C_AMBER`, `C_RED`.
- Existing data pipeline already provides day and MTD data used in reports.

## Proposed Design
### 1) Sales Forecast Block
Add a compact forecast block in the current report composition flow with:
- `Forecast Month-End Sales`
- `Forecast vs Monthly Target` (amount gap + % achievement)
- `Required Daily Run Rate` (for remaining days to hit target)

#### Formulae
- `elapsed_days = day_of_month(current_date)`
- `days_in_month = calendar days in current month`
- `remaining_days = max(days_in_month - elapsed_days, 0)`
- `forecast_month_end_sales = (mtd_sales / elapsed_days) * days_in_month` (when elapsed_days > 0)
- `forecast_target_pct = (forecast_month_end_sales / monthly_target) * 100` (when monthly_target > 0)
- `forecast_gap_amount = forecast_month_end_sales - monthly_target`
- `required_daily_run_rate = (monthly_target - mtd_sales) / remaining_days` (when remaining_days > 0)

If required denominator is zero or target missing, show safe fallback labels rather than errors.

### 2) Conditional Formatting (RAG)
Apply status colors for high-signal metrics using existing palette.

#### Thresholds
- Target achievement (today and MTD)
  - Green: >= 100%
  - Amber: 85% to <100%
  - Red: <85%

- Forecast vs target
  - Green: >= 100%
  - Amber: 95% to <100%
  - Red: <95%

- Discount % of gross
  - Green: <= 5%
  - Amber: >5% to 8%
  - Red: >8%

- APC vs trailing baseline
  - Green: drop <= 5%
  - Amber: drop >5% to 12%
  - Red: drop >12%

Implementation detail: convert each metric to a normalized status object:
- `status`: `green|amber|red|na`
- `label`: short display label
- `color`: concrete palette color

`na` is used for insufficient benchmark data and must render neutrally (no red default).

### 3) Verbose Daily Summary
Generate a 5-7 sentence structured brief that is easy to read in PNG and WhatsApp:
1. Day result vs daily target
2. MTD pace + month-end forecast
3. Comparison vs previous day and same weekday last week
4. Profitability watch (discount/APC/channel quality signal)
5. Positive driver (top category/item/service)
6. Primary risk signal
7. Suggested next-day action

Tone requirements:
- Operational and plain English
- No jargon-heavy finance language
- Useful for both manager (action) and leadership (status)

## Data Dependencies
### Required
- Current day sales, covers, APC, discounts, payment/channel split
- MTD sales and MTD target metrics
- Monthly target for selected location scope

### Comparative references
- Previous day (D-1)
- Same weekday last week (D-7)
- Trailing APC baseline (target: last 7 available days with valid APC)

### Missing-data handling
- Missing D-1 or D-7: summary line states benchmark unavailable
- Missing monthly target: forecast amount shown; target-gap and target-color omitted
- Missing APC baseline: APC anomaly omitted or marked `na`

Report generation must not fail because comparative inputs are incomplete.

## Component Boundaries
Keep implementation focused and testable with helper functions (initially in `sheet_reports.py`):
- `compute_forecast_metrics(...)`
- `compute_metric_statuses(...)`
- `build_verbose_daily_summary(...)`

These helpers are consumed by:
- PNG section rendering path
- WhatsApp text generation path

No cross-module refactor in this phase unless required for correctness.

## Error Handling
- Defensive numeric conversion for all metric inputs
- Zero/None denominator protection
- Graceful fallback strings (`"N/A"`, `"Insufficient benchmark data"`)
- Never raise on report rendering for absent comparative rows

## Testing Strategy
### Unit tests
- Forecast math: normal scenario, early-month, month-end, zero target
- RAG mapping: boundary checks at thresholds
- Summary generation: full input vs partial/missing input

### Formatting/output tests
- PNG-related section function includes forecast and summary fields when available
- WhatsApp output includes narrative paragraphs and fallback lines when data is missing

### Manual verification checklist
- First 3 days of month (thin data)
- Mid-month normal data
- Missing target config
- High-discount day
- APC drop anomaly day
- Multi-outlet scoped view

## Rollout Plan
1. Add helper calculations and status mapping
2. Wire forecast block into existing PNG report section flow
3. Wire verbose summary into PNG + WhatsApp outputs
4. Add tests and run test suite
5. Validate with sample historical days

## Acceptance Criteria
- Existing PNG structure remains recognizable (no redesign)
- Forecast month-end, forecast-vs-target, and required run-rate are visible
- Conditional formatting appears for specified metrics with agreed thresholds
- Verbose summary appears and reads naturally for daily operations
- Missing benchmark or target data degrades gracefully without report failure
- PNG and WhatsApp narrative are consistent in core conclusions

## Risks and Mitigations
- Risk: false alarms from rigid thresholds across outlets
  - Mitigation: centralize thresholds for easy tuning in future settings phase

- Risk: noisy narrative when data is sparse
  - Mitigation: explicit `na` conditions and concise fallback messaging

- Risk: duplicated logic between PNG and WhatsApp
  - Mitigation: shared helper functions for derived metrics and narrative text

## Future Phase (Not in this implementation)
- Forecast confidence band and probability-of-hit
- Period comparison dashboard enhancements in Analytics tab
- Outlet-specific threshold tuning in Settings
