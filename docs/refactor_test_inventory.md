# Refactor Regression Test Inventory

This document defines critical end-to-end and integration behaviors that must remain stable during upcoming refactors.

## Scope

- Focus: authentication/session, ingestion pipeline, persistence, report loading, analytics, tenancy scoping, and backend mode parity.
- Goal: reduce regression risk by making expected behavior explicit before runtime code changes.

## Critical Flows (Must Not Break)

## 1) Login and Session Lifecycle

**Area:** `auth.py`, `app.py`

### Invariants
- Valid credentials create a logged-in session and persist expected session state keys.
- Invalid credentials do not authenticate and show an error path without corrupting session state.
- Logout clears effective auth/session state and cookie-backed auth context.
- First-run/bootstrap admin flow remains functional when no admin exists.

### Regression Signals
- User appears logged out after page refresh despite valid session.
- Manager/admin role is missing or incorrect in session state.
- Logout leaves stale role/location data in session state.

## 2) File Detection

**Area:** `file_detector.py`, `smart_upload.py`

### Invariants
- Supported Petpooja export files are detected into the correct file kind.
- Unknown/invalid files are rejected with clear diagnostics.
- Detection remains stable across common header/casing/order variations.

### Regression Signals
- Valid Item Report / Timing / Dynamic files are classified as unknown.
- Detection confidence drops and routes parser to incorrect branch.

## 3) Smart Upload Parse Preview

**Area:** `smart_upload.py` and Upload tab wiring in `app.py`

### Invariants
- Multi-file upload produces per-file parse outcomes with preview-ready summaries.
- Parse errors are surfaced per file while successful files still preview.
- Day-level grouping/result assembly is deterministic for same input files.

### Regression Signals
- Preview table/cards disappear for valid uploads.
- One bad file aborts preview for all files.
- Parsed totals/date mappings differ unexpectedly from baseline fixtures.

## 4) Save Smart Upload Results

**Area:** `smart_upload.py`, `database.py`, `database_writes.py`

### Invariants
- Saving parsed upload results persists expected rows once (idempotency expectations preserved).
- Success/error counts and messages reflect actual DB write outcomes.
- Partial failure handling remains explicit (failures reported; successes committed as designed).

### Regression Signals
- Duplicate rows after repeated save on same payload where dedupe/upsert is expected.
- Silent write failures or success toast despite no DB persistence.

## 5) Report Bundle Loading

**Area:** report tab loaders and report data access in `database.py`/tab modules

### Invariants
- Selecting date/location loads complete report bundle (summary + related sections) without mismatch.
- Missing day data shows graceful empty/fallback state, not crash.
- Multi-location (admin) and single-location (manager) loading paths both resolve correctly.

### Regression Signals
- Bundle components sourced from different dates/locations in one view.
- Spinner ends with blank UI and no user-facing error state.

## 6) Analytics Date Range Queries

**Area:** analytics tab + `database_analytics.py` exports via `database.py`

### Invariants
- Date-range filters return only rows inside selected inclusive bounds.
- Aggregations (items/categories/services/super-categories) remain consistent with source summaries.
- Empty date range results are handled gracefully.

### Regression Signals
- Off-by-one-day results at start/end boundaries.
- Same query returns different totals between repeated runs without data changes.

## 7) Admin vs Manager Outlet Scope

**Area:** `auth.py`, `scope.py`, tab context building in `app.py`

### Invariants
- Admin can view all outlets and choose outlet scope.
- Manager is restricted to assigned location scope only.
- Server-side query parameters enforce scope regardless of UI controls.

### Regression Signals
- Manager can access cross-outlet records.
- Admin "all outlets" view drops locations or duplicates merged rows.

## 8) SQLite Fallback

**Area:** `database.py` mode selection and client initialization

### Invariants
- App remains functional with SQLite when Supabase is unavailable/unconfigured.
- Startup and core flows (login, upload, report, analytics) operate in SQLite-only mode.
- Warning logs are acceptable; hard crashes are not.

### Regression Signals
- Missing Supabase package/env causes startup failure.
- DB operations incorrectly assume Supabase response object shape in SQLite mode.

## 9) Supabase Mode Shape Expectations

**Area:** `database.py`, `database_writes.py`, read/write call sites

### Invariants
- Code consuming Supabase results handles expected response shape consistently.
- Insert/upsert/read paths map returned records to app schema without key mismatches.
- Failure responses are handled explicitly and surfaced to UI.

### Regression Signals
- `KeyError`/`TypeError` due to changed payload envelopes.
- Success path assumes `data` exists when backend returned error metadata.

---

## Manual QA Checklist (Streamlit)

Run app:

```bash
streamlit run app.py
```

Use this checklist for pre/post-refactor comparison.

### A. Auth and Session
- [ ] Log in with valid manager credentials; confirm landing page loads and role-gated UI is visible.
- [ ] Refresh browser; verify user remains authenticated (session/cookie continuity).
- [ ] Log out; verify redirected/unauthenticated state and role-specific widgets disappear.
- [ ] Attempt invalid login; verify clear error and no partial session state.

### B. File Detection + Preview
- [ ] Upload at least one valid file for each supported report type.
- [ ] Confirm each file is labeled with the correct detected type.
- [ ] Include one intentionally invalid file; verify it is rejected with a clear message.
- [ ] Confirm parse preview still renders for valid files when one file fails.

### C. Save Upload Results
- [ ] Save previewed results; verify success feedback and expected record counts.
- [ ] Re-run same upload/save scenario; verify dedupe/upsert semantics (no unintended duplicates).
- [ ] Validate persisted data appears in downstream report/analytics views.

### D. Report Bundle
- [ ] Open report tab for a known date/location with data; verify all sections load coherently.
- [ ] Switch to a date with no data; verify graceful empty state.
- [ ] For admin, toggle outlet scope and verify bundle updates correctly.

### E. Analytics Date Ranges
- [ ] Query a single-day range and compare totals to daily report.
- [ ] Query a multi-day range crossing month boundary; verify boundary inclusion is correct.
- [ ] Test empty range outcome (no records) and verify charts/tables handle it cleanly.

### F. Role Scope
- [ ] As manager, verify no control/access path to other outlets.
- [ ] As admin, verify all-outlets aggregation and single-outlet filtering both work.

### G. Backend Mode Validation
- [ ] SQLite mode: start app with Supabase unset/unavailable; run login, upload, report, analytics smoke checks.
- [ ] Supabase mode (if configured): repeat core smoke checks and verify no response-shape errors.

## Suggested Execution Cadence

- Before refactor: run full manual checklist once and capture baseline notes/screenshots.
- During refactor: run targeted sections for touched modules.
- Before merge: run full checklist + automated tests (`pytest`).
