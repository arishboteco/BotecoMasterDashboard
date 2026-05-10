## Covers Trend + Weekend vs Weekday Insight (Analysis Tab)

### Objective
Enhance the Analysis tab to improve interpretation of cover movement by:
- using a line chart for Covers Trend,
- adding a Friday-Sunday vs Monday-Thursday comparison,
- and showing concise commentary on current performance.

This change is scoped to the Analysis tab only.

### Approved Direction
Approach 1 (approved): keep Covers Trend as a line chart and add a compact insight block directly below it with:
- Avg Weekday Covers (Mon-Thu)
- Avg Weekend Covers (Fri-Sun)
- Delta % (weekend vs weekday)
- 1-2 sentence commentary

### Definitions
- Weekend days: Friday, Saturday, Sunday
- Weekday days: Monday, Tuesday, Wednesday, Thursday

### User Experience
Within the existing Drivers section in Analysis:
1. Covers Trend remains in its current card position.
2. Chart is rendered as a line chart (with markers) for readability over time.
3. A compact insight panel appears under the chart with comparison metrics and commentary.
4. If data is insufficient for one or both groups, show a neutral "Insufficient data for comparison" message.

No major layout changes are introduced.

### Data and Calculation Rules
Use the same filtered Analysis dataset already in scope (selected period + outlet scope).

For each date row:
- Map day name from date.
- Bucket into weekday (Mon-Thu) or weekend (Fri-Sun).

Compute:
- `avg_weekday_covers`: mean of covers for weekday bucket
- `avg_weekend_covers`: mean of covers for weekend bucket
- `delta_pct`: `((avg_weekend_covers - avg_weekday_covers) / avg_weekday_covers) * 100` when weekday average is greater than 0

Edge handling:
- If either bucket has zero rows, skip delta and show insufficient-data state.
- If weekday average is 0, do not compute percentage; show absolute difference only.
- Covers are treated as numeric with coercion and null-safe fill where needed.

### Commentary Rules
Generate concise operational commentary (1-2 lines):

1. Weekend-led pattern (delta positive):
   - "Weekend-led pattern: covers are up X% vs weekdays, indicating stronger late-week demand."
2. Weekday-led pattern (delta negative):
   - "Weekday-led pattern: weekend covers are down X% vs weekdays; review Friday-Sunday conversion/visibility."
3. Balanced pattern (near flat):
   - "Balanced pattern: weekday and weekend covers are largely stable."

Low-sample note:
- Add a cautionary note when bucket counts are small (for example, very short date windows).

### Technical Design
Primary file: `tabs/analytics_sections.py`

Planned updates:
1. Add a helper to compute weekend/weekday covers comparison from the already prepared covers dataframe.
2. Update Covers Trend rendering to line-chart presentation in both single-outlet and multi-outlet contexts.
3. Add a rendering helper (or inline block) for the insight panel under the covers chart.
4. Keep existing forecast behavior unchanged.
5. Keep existing chart summary/accessibility pattern (`_chart_summary`) and extend with comparison summary text.

### Non-Goals
- No changes to EOD report text output.
- No changes to upload, parsing, or storage behavior.
- No changes to target-setting logic.
- No redesign of the broader Analysis tab structure.

### Validation Plan
Manual checks in Analysis tab:
1. Covers chart displays as line chart with markers.
2. Comparison metrics appear and use Fri-Sun vs Mon-Thu classification.
3. Commentary text changes correctly for positive/negative/near-flat deltas.
4. Insufficient-data state appears when one bucket lacks data.
5. Multi-outlet and single-outlet views both render without regression.

Optional regression checks:
- Run targeted analytics tests and related UI smoke checks.

### Risks and Mitigations
- Risk: Misclassification expectations for weekend definition.
  - Mitigation: Weekend definition is explicitly fixed as Fri-Sun in code and copy.
- Risk: Noisy commentary on small samples.
  - Mitigation: Include low-sample caution and insufficient-data guardrails.
- Risk: Visual inconsistency with nearby cards.
  - Mitigation: Reuse current container and caption styling patterns.

### Rollout
Ship as a direct enhancement to Analysis tab with no migration or data backfill required.
