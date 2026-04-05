## Blended Forecast (Run-Rate + Weekday-Weighted)

### Objective
Replace naive run-rate forecast with blended model that accounts for day-of-week seasonality.

### Algorithm
1. Run-rate: `(MTD / elapsed) × days_in_month` (existing)
2. Weekday-weighted:
   - Group available daily sales by weekday (Mon=0..Sun=6)
   - Compute average sales per weekday
   - For each remaining calendar day in month, assign its weekday average
   - Sum = weekday forecast for remaining days
   - Total = `MTD + remaining_forecast`
3. Blended: `0.5 × run_rate + 0.5 × weekday_weighted`
4. Fallback: < 7 days history → pure run-rate

### Changes
- `compute_forecast_metrics(report_data, daily_sales_history=None)` gains optional param
- Returns dict with `forecast_month_end_sales` (blended), `forecast_run_rate`, `forecast_weekday_weighted`
- Backward compatible: no history → existing behavior
- PNG section and WhatsApp text unchanged (they consume `forecast_month_end_sales`)

### Tests
- Blended with 15 days history
- Fallback to run-rate with 3 days history
- Missing weekday data handled gracefully
