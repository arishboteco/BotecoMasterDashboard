# Analytics Tab Redesign — Forecasting & Chart Consolidation

## Problem
The Analytics tab currently renders 10+ charts that feel cluttered. No forecasting is present. Charts lack visual polish (no moving averages, no forecast bands, no clear actual-vs-projected distinction).

## Solution
Reduce to 6 focused charts + 1 data table. Add linear-regression forecasting to Daily Sales and Covers trends with gradient/semi-transparent styling for forecast regions.

## Architecture

### File Changes
| File | Change |
|------|--------|
| `tabs/analytics_sections.py` | Primary target — rewrite section renderers |
| `tabs/analytics_logic.py` | Add forecasting helpers + moving average |
| `tabs/analytics_tab.py` | Minor — remove calls to deleted sections |

### Sections (in order)
1. **Overview** (existing KPIs — no change)
2. **Sales Performance** — Daily Sales Trend (forecast), Covers Trend (forecast), APC Trend (cleaned up)
3. **Category Mix** — Donut chart only (% labels inside)
4. **Weekday Analysis** — Keep as-is + best/worst day annotations
5. **Target Achievement** — Cumulative with projected month-end + on-track badge
6. **Daily Data Table** — Keep as-is

### Forecasting Logic
- **Algorithm**: Simple linear regression via `numpy.polyfit` (already a pandas dependency)
- **Input**: Last N days of `net_total` or `covers` from the selected period
- **Output**: N/2 forecast days with point estimates + ±1 std dev band
- **Minimum data**: Require ≥7 days of data to forecast; otherwise show "Need more data" caption
- **No new dependencies**: numpy is already pulled in by pandas

### Chart Improvements Detail

#### Daily Sales Trend
- Solid line: actual data (brand primary)
- Dashed line: forecast (same color, 60% opacity)
- Gradient fill: forecast band between upper/lower bounds (±1 std dev)
- 7-day moving average overlay (secondary line, lighter shade)
- X-axis extends into forecast period

#### Covers Trend
- Actual bars: solid, full opacity (brand success)
- Forecast bars: same color, 40% opacity
- Trend line overlay: dashed, showing direction

#### APC Trend
- Keep average reference line
- Color segments: green when above avg, red when below
- No forecast (derived metric)

#### Category Mix
- Single donut chart (remove horizontal bar duplicate)
- % labels inside slices
- Color via existing `CHART_COLORWAY`

#### Weekday Analysis
- Add annotations: "Best day: X (₹Y)" and "Worst day: X (₹Y)"
- Keep target h-line if set

#### Target Achievement
- Cumulative area: green fill if above target pace, red if below
- Projected month-end point: dotted extension to end of month
- Badge: "On track" or "Behind by ₹X"

### Removed Charts
- Payment Mode Distribution
- Top Selling Items (bar + table)
- Meal Period Breakdown (2 charts)
- Category bar chart (duplicate of donut)

### Data Flow
```
User selects period → fetch summaries →
  render Overview KPIs →
  render Sales Performance (with forecast on sales + covers) →
  render Category Mix (donut) →
  render Weekday Analysis →
  render Target Achievement (with projection) →
  render Daily Data Table
```

### Error Handling
- <7 days data: skip forecast, show caption "Need at least 7 days of data for forecasting"
- No data at all: existing "No data in this period" message
- Zero variance: forecast = flat line (no std dev band)

### Testing
- Manual: Streamlit run, verify each period option
- Edge: 1 day, 7 days, 30 days, custom period
- Multi-outlet: verify aggregation still works
