# Architecture Overview

This document reflects the current post-refactor structure in `BotecoMasterDashboard`.

## 1) Data Flow

Primary runtime flow:

1. `app.py` bootstraps database/theme/auth state.
2. `auth.py` restores or creates authenticated session state.
3. User interacts with tab modules in `tabs/`.
4. Tabs call service-layer functions (`services/`) and database facade/read APIs.
5. `scope.py` and `sheet_reports.py` aggregate/format report output for report surfaces.

Ingestion/report flow:

- Upload inputs → `tabs/upload_tab.py`
- Preview/import orchestration → `services/upload_service.py`
- Parse/classify/merge/save pipeline → `smart_upload.py` + `uploads/`
- Persistence → `database.py`/`database_writes.py`
- Post-import invalidation → `services/cache_invalidation.py`
- Fresh report/analytics reads via `services/report_service.py`, `tabs/analytics_tab.py`, `database_reads.py`

## 2) Upload Pipeline

### Entry points

- UI: `tabs/upload_tab.py`
- Service wrapper: `services/upload_service.py`

### Pipeline stages

1. **File detection**: `file_detector.detect_and_describe` classifies each file.
2. **Parsing**: `smart_upload.py` dispatches to parsers:
   - `dynamic_report_parser.py` (preferred primary source)
   - `pos_parser.py` (item-order fallback)
   - `uploads/parsers/order_summary.py` (backup source)
   - `uploads/parsers/flash_report.py` (supplemental service-charge support)
   - `timing_parser.py` (service-period enrichment)
3. **Location routing**:
   - `uploads/router.py` groups restaurant-tagged fragments and maps them to location IDs.
   - `services/location_resolver.py` helps normalize names and aliases.
4. **Merge by date**: `uploads/merge.py` merges same-day fragments into `DayResult` records.
5. **Save**: `smart_upload.save_smart_upload_results(...)` persists summaries/uploads.
6. **Invalidate caches**: `services/cache_invalidation.invalidate_after_import(...)` clears stale reads.

## 3) Database / Repository Layer

## Database modules

- `database.py`: primary facade for bootstrap, connection management, migrations, and backend switching
  (SQLite default, Supabase when configured).
- `database_reads.py`: query/read helpers and `@st.cache_data`-cached read functions.
- `database_writes.py`: mutations/upserts/deletes.
- `database_auth.py`: auth/session persistence helpers.
- `database_analytics.py`: analytics aggregates.
- `db/`: database constants (`table_names.py`, `category_rows.py`).

## Repositories

- `repositories/sales_repository.py` defines `SalesRepository` protocol and DB-backed implementation.
- `repositories/category_repository.py` defines `CategoryRepository` protocol and DB-backed implementation.

Repositories currently delegate to database facade functions, providing protocol seams for testing/refactors.

## 4) Auth / Session Flow

1. `app.py` calls `auth.init_auth_state()` each render.
2. `auth.py` initializes session-state defaults (`authenticated`, `username`, `user_role`, scope fields).
3. Cookie manager (`streamlit_cookies_controller.CookieController`) attempts to restore `_COOKIE_NAME` token.
4. Token validation uses `database.validate_session_token(...)`.
5. On login form submit:
   - `database.verify_user(...)`
   - session created via `database.create_user_session(...)`
   - cookie persisted (`remember me` controls expiry)
6. `auth_permissions.py` helpers enforce location/role access constraints in UI/actions.

## 5) Cache Invalidation Rules

## Cache surfaces in use

- `database_reads.py`: several `@st.cache_data(ttl=600)` read functions.
- `services/report_service.py`: in-process caches registered via `cache_manager` (`report`, `mtd`, `foot`).
- `tabs/analytics_tab.py`: in-process raw-summary cache (`analytics_raw`) via `cache_manager`.

## Invalidation triggers

### After successful import (`tabs/upload_tab.py`)

`services/cache_invalidation.invalidate_after_import(location_ids)` runs:

- `invalidate_location_reads(location_id)` → `database_reads.clear_location_cache(location_id)`
- `invalidate_analytics()` → `tabs.analytics_tab.clear_analytics_cache()`
- `invalidate_reports()` → `tabs.report_tab.clear_report_cache()`

This ensures post-import report/analytics views are rebuilt from fresh persisted data.

### Settings-level broad reset

`tabs/settings_tab.py` may call `st.cache_data.clear()` for global cache resets on settings changes.

## 6) Testing Strategy

Testing is pytest-first with broad module coverage (not parser-only).

### Core principles

- Keep pure transformation logic in testable helpers (`uploads/`, `core/`, `tabs/*_logic.py`).
- Verify service orchestration with monkeypatch-based isolation (`services/*`).
- Guard regressions in report formatting, analytics logic, database modules, and style token usage.

### Representative suites

- Upload pipeline: `tests/test_smart_upload.py`, `tests/test_upload_service.py`, `tests/test_upload_models.py`
- Parsers: `tests/test_pos_parser.py`, `tests/test_dynamic_report_parser.py`,
  `tests/test_order_summary_parser.py`, `tests/test_flash_report_parser.py`
- Data layer: `tests/test_database*.py`, `tests/test_sales_repository.py`,
  `tests/test_category_repository.py`, `tests/test_table_names.py`
- Caching/reporting: `tests/test_cache_invalidation.py`, `tests/test_report_service.py`,
  `tests/test_sheet_reports_*.py`
- Analytics/UI logic: `tests/test_analytics_logic.py`, `tests/test_chart_builders.py`,
  `tests/test_ui_theme_plotly.py`, `tests/test_css_token_usage.py`, `tests/test_theme_consistency.py`

### Execution

- Full suite: `pytest`
- Targeted execution for local iteration is encouraged before full runs.
