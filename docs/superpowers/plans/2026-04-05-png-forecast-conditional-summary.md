# PNG Forecasting, Conditional Formatting, and Verbose Daily Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add month-end sales forecasting, metric-level conditional formatting, and a verbose daily summary to the existing PNG and WhatsApp report outputs without redesigning the current report layout.

**Architecture:** Keep all new logic in focused helper functions inside `sheet_reports.py` for phase-1 speed and low-risk integration. Reuse the same helper outputs in both `_section_sales_summary(...)` (PNG) and `generate_whatsapp_text(...)` (text) to avoid drift. Use explicit fallbacks (`na`) for missing benchmark data so report generation never fails.

**Tech Stack:** Python 3.11+, matplotlib (PNG), pytest

---

## File Structure and Responsibilities

- Modify: `sheet_reports.py`
  - Add forecast/status/summary helper functions
  - Wire forecast + summary rows into sales summary section
  - Wire narrative into WhatsApp output
- Create: `tests/test_sheet_reports_forecasting.py`
  - Forecast math tests
  - Status threshold mapping tests
  - Verbose summary behavior tests
- Modify: `tests/test_sheet_reports_sections.py`
  - Assert WhatsApp output includes new forecast/summary lines
- Modify: `tests/test_sheet_reports_formatting.py`
  - Keep existing rupee formatting checks and add one small currency formatting compatibility check for forecast output values

---

### Task 1: Add failing tests for forecast math and status thresholds

**Files:**
- Create: `tests/test_sheet_reports_forecasting.py`
- Test: `tests/test_sheet_reports_forecasting.py`

- [ ] **Step 1: Write the failing tests for forecast calculations**

```python
"""Forecast/status/summary tests for sheet reports."""

import sheet_reports


class TestForecastMetrics:
    def test_forecast_metrics_mid_month(self):
        result = sheet_reports.compute_forecast_metrics(
            {
                "date": "2026-04-15",
                "mtd_net_sales": 225000,
                "mtd_target": 450000,
            }
        )
        assert result["days_in_month"] == 30
        assert result["elapsed_days"] == 15
        assert round(result["forecast_month_end_sales"], 2) == 450000.00
        assert round(result["forecast_target_pct"], 2) == 100.00

    def test_forecast_handles_missing_target(self):
        result = sheet_reports.compute_forecast_metrics(
            {"date": "2026-04-15", "mtd_net_sales": 225000, "mtd_target": 0}
        )
        assert result["forecast_month_end_sales"] > 0
        assert result["forecast_target_pct"] is None
        assert result["forecast_gap_amount"] is None


class TestMetricStatuses:
    def test_target_status_red_under_85(self):
        status = sheet_reports.status_from_threshold(
            74,
            green_min=100,
            amber_min=85,
            higher_is_better=True,
        )
        assert status["status"] == "red"

    def test_forecast_status_amber_between_95_and_100(self):
        status = sheet_reports.status_from_threshold(
            97,
            green_min=100,
            amber_min=95,
            higher_is_better=True,
        )
        assert status["status"] == "amber"

    def test_discount_status_green_at_or_below_5(self):
        status = sheet_reports.status_from_threshold(
            4.9,
            green_max=5,
            amber_max=8,
            higher_is_better=False,
        )
        assert status["status"] == "green"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sheet_reports_forecasting.py -v`

Expected: FAIL with `AttributeError` for missing functions like `compute_forecast_metrics` and `status_from_threshold`.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_sheet_reports_forecasting.py
git commit -m "test: add failing forecast and threshold coverage for sheet reports"
```

---

### Task 2: Implement forecast and status helper functions

**Files:**
- Modify: `sheet_reports.py`
- Test: `tests/test_sheet_reports_forecasting.py`

- [ ] **Step 1: Implement minimal helpers to satisfy Task 1 tests**

```python
from datetime import datetime, timedelta
import math


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def compute_forecast_metrics(report_data: Dict[str, Any]) -> Dict[str, Any]:
    iso = str(report_data.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]
    dt = datetime.strptime(iso, "%Y-%m-%d")
    days_in_month = (dt.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    dim = int(days_in_month.day)
    elapsed = int(dt.day)
    remaining = max(dim - elapsed, 0)

    mtd_net = _safe_float(report_data.get("mtd_net_sales"))
    mtd_target = _safe_float(report_data.get("mtd_target"))

    forecast = (mtd_net / elapsed * dim) if elapsed > 0 else 0.0
    pct = (forecast / mtd_target * 100.0) if mtd_target > 0 else None
    gap = (forecast - mtd_target) if mtd_target > 0 else None
    req_run_rate = (
        (mtd_target - mtd_net) / remaining
        if mtd_target > 0 and remaining > 0
        else None
    )

    return {
        "days_in_month": dim,
        "elapsed_days": elapsed,
        "remaining_days": remaining,
        "forecast_month_end_sales": forecast,
        "forecast_target_pct": pct,
        "forecast_gap_amount": gap,
        "required_daily_run_rate": req_run_rate,
    }


def status_from_threshold(
    value: Optional[float],
    *,
    green_min: Optional[float] = None,
    amber_min: Optional[float] = None,
    green_max: Optional[float] = None,
    amber_max: Optional[float] = None,
    higher_is_better: bool,
) -> Dict[str, Any]:
    if value is None:
        return {"status": "na", "color": C_MUTED, "label": "N/A"}

    v = float(value)
    if higher_is_better:
        if green_min is not None and v >= green_min:
            return {"status": "green", "color": C_GREEN, "label": "On Track"}
        if amber_min is not None and v >= amber_min:
            return {"status": "amber", "color": C_AMBER, "label": "Watch"}
        return {"status": "red", "color": C_RED, "label": "At Risk"}

    if green_max is not None and v <= green_max:
        return {"status": "green", "color": C_GREEN, "label": "Healthy"}
    if amber_max is not None and v <= amber_max:
        return {"status": "amber", "color": C_AMBER, "label": "Watch"}
    return {"status": "red", "color": C_RED, "label": "At Risk"}
```

- [ ] **Step 2: Run tests to verify Task 1 now passes**

Run: `pytest tests/test_sheet_reports_forecasting.py -v`

Expected: PASS for all tests in `TestForecastMetrics` and `TestMetricStatuses`.

- [ ] **Step 3: Commit helper implementation**

```bash
git add sheet_reports.py
git commit -m "feat: add forecasting and threshold status helpers for sheet reports"
```

---

### Task 3: Add failing tests for verbose summary behavior and missing-data fallback

**Files:**
- Modify: `tests/test_sheet_reports_forecasting.py`
- Test: `tests/test_sheet_reports_forecasting.py`

- [ ] **Step 1: Add summary-focused failing tests**

```python
class TestVerboseSummary:
    def test_verbose_summary_contains_forecast_and_action(self):
        result = sheet_reports.build_verbose_daily_summary(
            {
                "date": "2026-04-15",
                "net_total": 18000,
                "target": 20000,
                "mtd_net_sales": 225000,
                "mtd_target": 450000,
                "discount": 1200,
                "gross_total": 22000,
                "apc": 410,
                "apc_baseline_7d": 460,
                "previous_day_net_total": 20000,
                "same_weekday_last_week_net_total": 19500,
            }
        )
        assert "Forecast month-end" in result
        assert "Suggested action" in result
        assert len(result.split("\n")) >= 5

    def test_verbose_summary_handles_missing_benchmarks(self):
        result = sheet_reports.build_verbose_daily_summary(
            {
                "date": "2026-04-02",
                "net_total": 9000,
                "target": 12000,
                "mtd_net_sales": 18000,
                "mtd_target": 360000,
            }
        )
        assert "benchmark unavailable" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail first**

Run: `pytest tests/test_sheet_reports_forecasting.py::TestVerboseSummary -v`

Expected: FAIL with `AttributeError` for missing `build_verbose_daily_summary`.

- [ ] **Step 3: Commit failing summary tests**

```bash
git add tests/test_sheet_reports_forecasting.py
git commit -m "test: add failing verbose summary behavior coverage"
```

---

### Task 4: Implement verbose summary helper and integrate with WhatsApp text

**Files:**
- Modify: `sheet_reports.py`
- Modify: `tests/test_sheet_reports_sections.py`
- Test: `tests/test_sheet_reports_forecasting.py`
- Test: `tests/test_sheet_reports_sections.py`

- [ ] **Step 1: Implement summary helper in `sheet_reports.py`**

```python
def build_verbose_daily_summary(report_data: Dict[str, Any]) -> str:
    r = dict(report_data or {})
    forecast = compute_forecast_metrics(r)

    net = _safe_float(r.get("net_total"))
    target = _safe_float(r.get("target"))
    pct_target = (net / target * 100.0) if target > 0 else None

    prev_day = r.get("previous_day_net_total")
    wk_ref = r.get("same_weekday_last_week_net_total")
    gross = _safe_float(r.get("gross_total"))
    discount = _safe_float(r.get("discount"))
    discount_pct = (discount / gross * 100.0) if gross > 0 else None

    apc = _safe_float(r.get("apc"))
    apc_base = r.get("apc_baseline_7d")
    apc_drop_pct = None
    if apc_base not in (None, 0):
        apc_drop_pct = ((float(apc_base) - apc) / float(apc_base)) * 100.0

    line_1 = (
        f"Today closed at {_r(net)} against target {_r(target)} "
        f"({pct_target:.0f}% achievement)."
        if pct_target is not None
        else f"Today closed at {_r(net)}; daily target is not configured."
    )
    line_2 = (
        f"Forecast month-end: {_r(forecast['forecast_month_end_sales'])} "
        f"({forecast['forecast_target_pct']:.0f}% of target)."
        if forecast["forecast_target_pct"] is not None
        else f"Forecast month-end: {_r(forecast['forecast_month_end_sales'])}; target comparison unavailable."
    )
    if prev_day is None or wk_ref is None:
        line_3 = "Comparison to previous day/week benchmark unavailable due to incomplete history."
    else:
        line_3 = (
            f"Vs previous day: {_r(net - float(prev_day))}; "
            f"vs same weekday last week: {_r(net - float(wk_ref))}."
        )

    if discount_pct is None:
        line_4 = "Profitability watch: discount signal unavailable (gross sales missing)."
    else:
        line_4 = f"Profitability watch: discount at {discount_pct:.1f}% of gross."

    if apc_drop_pct is None:
        line_5 = "APC benchmark unavailable for anomaly check."
    else:
        line_5 = f"APC is {_r(apc)} ({apc_drop_pct:.1f}% below 7-day baseline)."

    line_6 = "Suggested action: tighten discount approvals and push high-APC combos in next shift."
    return "\n".join([line_1, line_2, line_3, line_4, line_5, line_6])
```

- [ ] **Step 2: Integrate verbose summary into `generate_whatsapp_text(...)`**

```python
summary_text = build_verbose_daily_summary(r)

report += (
    "\n🧾 DAILY OPERATIONS BRIEF\n"
    f"{summary_text}\n"
)
```

- [ ] **Step 3: Add assertion in `tests/test_sheet_reports_sections.py` for WhatsApp brief**

```python
def test_whatsapp_text_includes_daily_operations_brief(self) -> None:
    txt = sheet_reports.generate_whatsapp_text(_base_report_data(), "Boteco Bangalore")
    assert "DAILY OPERATIONS BRIEF" in txt
    assert "Forecast month-end" in txt
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_sheet_reports_forecasting.py tests/test_sheet_reports_sections.py -v`

Expected: PASS for verbose summary tests and WhatsApp brief inclusion test.

- [ ] **Step 5: Commit summary integration**

```bash
git add sheet_reports.py tests/test_sheet_reports_forecasting.py tests/test_sheet_reports_sections.py
git commit -m "feat: add verbose daily operations brief to whatsapp output"
```

---

### Task 5: Wire forecast block and conditional colors into PNG sales summary section

**Files:**
- Modify: `sheet_reports.py`
- Modify: `tests/test_sheet_reports_formatting.py`
- Test: `tests/test_sheet_reports_sections.py`
- Test: `tests/test_sheet_reports_formatting.py`

- [ ] **Step 1: Add helper for composite metric statuses**

```python
def compute_metric_statuses(report_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    r = dict(report_data or {})
    forecast = compute_forecast_metrics(r)

    pct_target = _safe_float(r.get("pct_target"), 0.0)
    target_status = status_from_threshold(
        pct_target,
        green_min=100,
        amber_min=85,
        higher_is_better=True,
    )

    fc_pct = forecast.get("forecast_target_pct")
    forecast_status = status_from_threshold(
        fc_pct,
        green_min=100,
        amber_min=95,
        higher_is_better=True,
    )

    gross = _safe_float(r.get("gross_total"))
    discount = _safe_float(r.get("discount"))
    discount_pct = (discount / gross * 100.0) if gross > 0 else None
    discount_status = status_from_threshold(
        discount_pct,
        green_max=5,
        amber_max=8,
        higher_is_better=False,
    )

    apc = _safe_float(r.get("apc"))
    apc_base = r.get("apc_baseline_7d")
    apc_drop_pct = None
    if apc_base not in (None, 0):
        apc_drop_pct = ((float(apc_base) - apc) / float(apc_base)) * 100.0
    apc_status = status_from_threshold(
        apc_drop_pct,
        green_max=5,
        amber_max=12,
        higher_is_better=False,
    )

    return {
        "target": target_status,
        "forecast": forecast_status,
        "discount": discount_status,
        "apc": apc_status,
    }
```

- [ ] **Step 2: Add forecast rows and color mapping in `_section_sales_summary(...)`**

```python
forecast = compute_forecast_metrics(r)
statuses = compute_metric_statuses(r)

_row(None, None, section_label="Forecast")
_row("Forecast Month-End", lambda d: forecast["forecast_month_end_sales"], fmt="currency")
_row(
    "Forecast vs Target",
    lambda d: forecast["forecast_target_pct"] if forecast["forecast_target_pct"] is not None else "N/A",
    fmt="pct" if forecast["forecast_target_pct"] is not None else "str",
    right_color=statuses["forecast"]["color"],
)
_row(
    "Required Daily Run Rate",
    lambda d: forecast["required_daily_run_rate"] if forecast["required_daily_run_rate"] is not None else "N/A",
    fmt="currency" if forecast["required_daily_run_rate"] is not None else "str",
)

_row(
    "% of Target",
    "mtd_pct_target",
    fmt="pct",
    bold=True,
    right_color=statuses["target"]["color"],
)
```

- [ ] **Step 3: Add summary block in PNG section footer (text-only block in existing card)**

```python
summary_text = build_verbose_daily_summary(r)
_row(None, None, section_label="Daily Operations Brief")
for idx, ln in enumerate(summary_text.split("\n")):
    _row(f"Note {idx + 1}", lambda _d, text=ln: text, fmt="str")
```

- [ ] **Step 4: Add lightweight formatting regression test**

```python
class TestForecastFormatting:
    def test_currency_formatter_handles_forecast_values(self):
        assert sheet_reports._r(300000.4) == "₹300,000"
```

- [ ] **Step 5: Run targeted rendering and formatting tests**

Run: `pytest tests/test_sheet_reports_sections.py tests/test_sheet_reports_formatting.py -v`

Expected: PASS and generated buffers remain non-empty.

- [ ] **Step 6: Commit PNG integration**

```bash
git add sheet_reports.py tests/test_sheet_reports_sections.py tests/test_sheet_reports_formatting.py
git commit -m "feat: add forecast and conditional formatting to sales summary png"
```

---

### Task 6: Full verification and cleanup

**Files:**
- Modify: none (verification-only unless failures require fixes)
- Test: `tests/test_sheet_reports_forecasting.py`
- Test: `tests/test_sheet_reports_sections.py`
- Test: `tests/test_sheet_reports_formatting.py`

- [ ] **Step 1: Run full relevant test set**

Run: `pytest tests/test_sheet_reports_forecasting.py tests/test_sheet_reports_sections.py tests/test_sheet_reports_formatting.py -v`

Expected: PASS across all tests.

- [ ] **Step 2: Run full suite smoke check**

Run: `pytest -q`

Expected: PASS (or only pre-existing unrelated failures).

- [ ] **Step 3: Commit final test/stability fixes (if any)**

```bash
git add sheet_reports.py tests/test_sheet_reports_forecasting.py tests/test_sheet_reports_sections.py tests/test_sheet_reports_formatting.py
git commit -m "test: finalize forecast summary report coverage"
```

---

## Spec Coverage Self-Check

- Forecasting block in PNG: covered by Task 5.
- Conditional formatting thresholds: covered by Task 2 + Task 5.
- Verbose daily summary in PNG + WhatsApp: covered by Task 4 + Task 5.
- Graceful fallback for missing benchmarks/target: covered by Task 3 + Task 4 tests.
- No layout redesign: preserved by integrating rows into existing `_section_sales_summary(...)` table.

## Placeholder Scan

- No `TBD`/`TODO` placeholders.
- Each code-change step includes concrete code snippets.
- Each test step includes exact pytest commands and expected outcomes.

## Type/Signature Consistency Check

- `compute_forecast_metrics(report_data)` used consistently across tasks.
- `status_from_threshold(...)` signature is consistent in tests and integration.
- `build_verbose_daily_summary(report_data)` used consistently in PNG and WhatsApp integration tasks.
