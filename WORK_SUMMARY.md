# Boteco Dashboard - Work Summary (Current)

## Project Overview
A Streamlit dashboard for Boteco Bangalore to ingest POS exports, generate daily report outputs (WhatsApp text + PNG), and analyze historical sales.

**Repository:** https://github.com/arishboteco/BotecoMasterDashboard

---

## Current Core Modules

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit app (Upload, Report, Analytics, Settings tabs) |
| `database.py` | Database facade/bootstrap + shared schema/migration helpers |
| `database_reads.py` | Read/query operations |
| `database_writes.py` | Write/upsert/delete operations |
| `database_auth.py` | User/session auth operations |
| `database_analytics.py` | Aggregated analytics queries |
| `auth.py` | Login/logout/session state UI flow |
| `boteco_logger.py` | Centralized logging configuration |
| `smart_upload.py` | Multi-file upload orchestration |
| `sheet_reports.py` | PNG and WhatsApp report generation |

---

## Database & Deployment Modes

- **SQLite (default/local):** used when Supabase credentials are not configured.
- **Supabase (cloud):** used when `SUPABASE_URL` + `SUPABASE_KEY` are configured and client initialization succeeds.
- `USE_SUPABASE=1` acts as a deployment guardrail and should be enabled in production environments.

---

## First-Run Authentication Behavior

- `database.bootstrap()` initializes schema/migrations/default outlets.
- If no users exist, app bootstraps `admin` / `admin`.
- Default outlets are ensured (`Boteco - Indiqube`, `Boteco - Bagmane`).
- Immediate post-deploy action: log in and rotate the admin password.

---

## Testing Snapshot

Test suite now covers database layers, tabs, reporting, forecasting, uploads, utilities, and validation.

Run all tests:

```bash
pytest
```

Representative targeted runs:

```bash
pytest tests/test_database_phase4_modules.py -v
pytest tests/test_report_tab.py -v
pytest tests/test_smart_upload.py -v
```

---

*Last Updated: 25 April 2026*
