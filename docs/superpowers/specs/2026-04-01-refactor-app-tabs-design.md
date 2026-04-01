# Design: Refactor app.py into Per-Tab Modules

## Overview

Extract the 4 tabs from `app.py` (2163 lines) into a `tabs/` package, each with its own module containing a `render(ctx)` function. `app.py` shrinks to ~60 lines of setup, auth, and tab routing.

## Architecture

### File Structure

```
app.py                    (~60 lines)  - Setup, auth, tab delegation
tabs/
  __init__.py             - Package init, exports render functions
  upload_tab.py           (~400 lines) - Upload, covers sync, delete data, history
  report_tab.py           (~350 lines) - Daily report, KPIs, PNG/WhatsApp
  analytics_tab.py        (~500 lines) - Period selector, all charts
  settings_tab.py         (~400 lines) - Account, outlets, users, export
```

### TabContext Dataclass

Shared context passed to every tab's `render()` function:

```python
@dataclass
class TabContext:
    location_id: int
    import_loc_id: int
    report_loc_ids: list[int]
    report_display_name: str
    all_locs: list[dict]
    location_settings: Optional[dict]
    import_location_settings: Optional[dict]
```

Defined in `tabs/__init__.py`. Each tab reads what it needs from `ctx` and manages its own internal `st.session_state` keys.

### app.py (After Refactor)

Keeps:
- All imports
- Logging setup, DB bootstrap, page config, CSS
- Auth initialization and flow
- Computation of `import_loc_id`, `report_loc_ids`, `report_display_name`, `all_locs`, `location_settings`
- Tab creation via `st.tabs()` and delegation: `upload_tab.render(ctx)` etc.

Removes:
- All tab body code (moved to respective modules)

### tabs/upload_tab.py

Contains current lines ~188–583:
- Upload header, caption, flash summary, "How it works" expander
- File uploader zone, detection display (Phase 1)
- Smart upload pipeline (Phase 2–3): overlap detection, confirmation, import button, covers merge, daily summary save, upload record
- Covers-only sync section
- Remove incorrect data section (admin-only)
- Recent uploads table

Imports needed: `streamlit`, `pandas`, `datetime`, `config`, `database`, `file_detector`, `pos_parser`, `smart_upload`, `customer_report_parser`, `utils`, `auth`

### tabs/report_tab.py

Contains current lines ~585–1081:
- Date navigation (Prev/Next buttons + date picker)
- Bundle fetch via `scope.get_daily_report_bundle()`
- Multi-outlet vs single-outlet KPI cards (net sales, covers, APC, orders/AOV, target)
- Sales & tax breakdown table
- MTD summary table
- Sheet-style PNG report generation + WhatsApp text
- Per-outlet report images (multi-outlet mode)
- Copy/download buttons (image, text, PNG, sections ZIP)
- Individual section previews
- Plain text preview

Imports needed: `streamlit`, `pandas`, `datetime/timedelta`, `io.BytesIO`, `zipfile`, `config`, `database`, `scope`, `sheet_reports`, `clipboard_ui`, `utils`

### tabs/analytics_tab.py

Contains current lines ~1083–1739:
- Period selector (This Week, Last Week, Last 7 Days, This Month, Last Month, Last 30 Days, Custom)
- Date range resolution + prior period calculation
- Data fetch + multi-outlet merge
- Period summary KPIs (total sales, covers, avg daily, days with data, projected month-end)
- Daily sales trend chart
- Covers trend chart
- APC trend chart with average line
- Payment mode distribution chart
- Category mix (bar + donut)
- Top selling items (bar + table)
- Meal period breakdown (stacked + total)
- Weekday analysis with target line
- Target achievement (bar + cumulative)
- Daily data table

Imports needed: `streamlit`, `pandas`, `plotly.express`, `plotly.graph_objects`, `plotly.subplots`, `datetime/timedelta`, `config`, `database`, `scope`, `ui_theme`, `utils`

### tabs/settings_tab.py

Contains current lines ~1741–2163:
- Account info display (username, role, home location)
- Non-admin early exit
- Outlet settings form (name, monthly target, seat count)
- Add new outlet expander
- Delete outlet expander
- User management table
- Create user form
- Edit user form
- Delete user form
- Data export (CSV/Excel with filters)
- Quick stats expander

Imports needed: `streamlit`, `pandas`, `datetime`, `config`, `database`, `utils`, `auth`

## Data Flow

```
app.py
  ├── Compute context values from auth + DB
  ├── Build TabContext dataclass
  ├── st.tabs(["Upload", "Report", "Analytics", "Settings"])
  └── tabX.render(ctx)
        ├── Read needed values from ctx
        ├── Manage own st.session_state keys (prefixed to avoid collisions)
        └── Call database/scope/reports/utils as needed
```

## Error Handling

- Unchanged from current behavior — each tab module handles its own errors inline
- No new error paths introduced

## Testing

- No existing tests for app.py UI code
- Post-refactor: can test each tab's render function in isolation (Streamlit testing framework or manual verification)
- Existing `tests/test_pos_parser.py` unaffected

## Migration Strategy

1. Create `tabs/` package with `__init__.py` and `TabContext`
2. Extract each tab one at a time into its module
3. Update `app.py` to import and delegate
4. Verify app runs identically (manual testing of all 4 tabs)
5. No behavior changes — pure extraction

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Session state key collisions between tabs | Prefix keys with tab name (e.g., `upload_delete_day_outlet`, `settings_which_location`) — already mostly done in current code |
| Import circular dependencies | `tabs/` imports from root modules, never the reverse |
| CSS class references break | CSS stays in `app.py`, class names unchanged |
| Streamlit rerun behavior changes | Each tab's `st.rerun()` calls remain in-place; no structural change to rerun logic |
