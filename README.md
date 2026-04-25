# Boteco Dashboard - Restaurant Sales Management System

A sales management system for **Boteco Bangalore** with multiple outlets. It ingests POS data from Petpooja exports, generates daily End-of-Day reports as formatted PNG images and WhatsApp-ready text, and provides analytics dashboards.

**Deployed at:** https://arishboteco-botecomasterdashboard.streamlit.app

## Setup Instructions

### 1. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
streamlit run app.py
```

## Database Modes: SQLite vs Supabase

The app supports **two data backends** and auto-selects behavior based on environment configuration:

### Local/default mode (SQLite)
- Default when `SUPABASE_KEY` is not set.
- Data is stored in `data/boteco.db`.
- Good for local development and small single-instance setups.

### Cloud mode (Supabase)
- Enabled when `SUPABASE_URL` + `SUPABASE_KEY` are set and the Supabase client can be created.
- `USE_SUPABASE=1` is recommended in deployment environments to make intent explicit.
- Service-role operations require `SUPABASE_SERVICE_KEY`.

### Required environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Supabase mode | Supabase project URL |
| `SUPABASE_KEY` | Supabase mode | Supabase anon key used by app client |
| `SUPABASE_SERVICE_KEY` | Optional / admin ops | Service role key for privileged operations |
| `USE_SUPABASE` | Optional | Deployment guardrail (if set without key, app stops with error) |
| `BOTECO_LOG_FILE` | Optional | File path for persistent logs |

> On Streamlit Cloud, file-based SQLite can be ephemeral or constrained. Use Supabase for persistent multi-user deployments.

## First-Run Behavior & Authentication

On startup, `app.py` calls `database.bootstrap()`, which initializes schema, runs migrations, ensures default outlets, and purges expired sessions.

### What happens on first run
- If `users` table is empty, app auto-creates an admin user:
  - **Username:** `admin`
  - **Password:** `admin`
- Default outlets are ensured:
  - `Boteco - Indiqube`
  - `Boteco - Bagmane`

### What to do immediately after first login
1. Log in with `admin` / `admin`.
2. Go to **Settings** and change admin password.
3. Verify outlet names and monthly targets.
4. (Cloud) Confirm Supabase credentials and RLS policies.

## Features
- **Smart file upload** — Drop any mix of Petpooja exports; the system auto-detects file types by content
- **Multi-location support** — Manage multiple outlets with per-outlet targets and settings
- **Role-based access** — Admin and manager roles with location scoping
- **Daily EOD reports** — Polished PNG images and WhatsApp-ready text with sales, covers, APC, payment breakdown, category mix, and MTD summary
- **Analytics dashboard** — Sales trends, covers, APC, payment distribution, category mix, top-selling items, meal period breakdown, weekday analysis, and target tracking
- **Data export** — Download daily summaries as CSV or Excel

## Current Architecture Map

Database responsibilities are split by module:

- `database.py`
  - Facade / compatibility layer
  - Connection management, bootstrap, Supabase client creation, shared migrations
  - Delegates read/write/auth/analytics calls to specialized modules

- `database_reads.py`
  - Query/read-oriented operations (summaries, locations, exports, settings reads)

- `database_writes.py`
  - Mutation/upsert operations (daily summaries, uploads, location updates, cleanup)

- `database_auth.py`
  - User auth lifecycle (create/verify users, sessions, failed login lockouts)

- `database_analytics.py`
  - Aggregate/reporting queries (top items, category/service trends, date-range analytics)

## File Structure
```text
BotecoMasterDashboard/
├── app.py
├── auth.py
├── boteco_logger.py
├── config.py
├── database.py
├── database_auth.py
├── database_reads.py
├── database_writes.py
├── database_analytics.py
├── file_detector.py
├── pos_parser.py
├── scope.py
├── sheet_reports.py
├── smart_upload.py
├── timing_parser.py
├── ui_theme.py
├── utils.py
├── tabs/
├── components/
├── styles/
├── tests/
├── scripts/
└── data/
    └── boteco.db
```

## Testing

Run all tests:

```bash
pytest
```

Run targeted suites:

```bash
pytest tests/test_database_phase4_modules.py -v
pytest tests/test_smart_upload.py -v
pytest tests/test_report_tab.py -v
```

Current test coverage areas in `tests/` include:
- Database split modules and core DB behavior
- Upload/report/analytics tab logic
- Smart upload + parser flows
- Sheet report formatting/sections/forecasting
- Utility helpers, theming, validation, and scope calculations

## Performance Profiling

Run synthetic analytics benchmark (temporary DB, no production data touched):

```bash
python scripts/profile_analytics_queries.py --days 365 --locations 3
```

## Supported Petpooja Export Types

| Type | File | Usage |
|------|------|-------|
| Item Report With Customer/Order Details | `.xlsx` | Primary data source — sales, categories, items, payments |
| Restaurant Timing Report | `.xlsx` | Meal period breakdown (Breakfast, Lunch, Dinner) |
| Order Summary Report | `.csv` | Backup data source when Item Report unavailable |
| Flash Report / POS Collection | `.xlsx` | Supplement for service charge data |
| Customer/Booking Report | `.xlsx` | Detected but not imported |
| Group Wise / All Restaurant / Comparison | `.xlsx/.xls` | Skipped — redundant data |

## Cloud Deployment (Streamlit Cloud)

1. Push this code to GitHub.
2. Go to [streamlit.io](https://streamlit.io).
3. Connect your repository and deploy `app.py`.
4. Configure environment variables in Streamlit Secrets / app settings.
5. Validate `?health=check` endpoint after deployment.
