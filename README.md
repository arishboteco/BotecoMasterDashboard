# Boteco Dashboard - Restaurant Sales Management System

A sales management system for **Boteco Bangalore** with multiple outlets. Ingests POS data from Petpooja exports, generates daily End-of-Day reports as formatted PNG images and WhatsApp-ready text, and provides analytics dashboards.

**Deployed at:** https://arishboteco-botecomasterdashboard.streamlit.app

## Setup Instructions

### 1. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 2. Install Runtime Dependencies
```bash
pip install -r requirements.txt
```

### 3. (Optional) Install Dev/Test Dependencies
```bash
pip install -r requirements-dev.txt
```

### 4. Run the Application
```bash
streamlit run app.py
```

### 5. First Time Setup
- On first run, you'll be prompted to create an admin account
- Default locations "Boteco - Indiqube" and "Boteco - Bagmane" will be created
- Set your monthly sales target (default: ₹5,000,000)

## Cloud Deployment (Streamlit Cloud)

1. Push this code to GitHub
2. Go to [streamlit.io](https://streamlit.io)
3. Connect your GitHub repository
4. Deploy

**Note:** For cloud deployment, SQLite file storage is limited. Consider using an external database (PostgreSQL, MySQL) for production.

## Default Credentials
- Username: admin
- Password: (set during first run)

## Features
- **Smart file upload** — Drop any mix of Petpooja exports; the system auto-detects file types by content
- **Multi-location support** — Manage multiple outlets with per-outlet targets and settings
- **Role-based access** — Admin and manager roles with location scoping
- **Daily EOD reports** — Polished PNG images and WhatsApp-ready text with sales, covers, APC, payment breakdown, category mix, and MTD summary
- **Analytics dashboard** — Sales trends, covers, APC, payment distribution, category mix, top-selling items, meal period breakdown, weekday analysis, and target tracking
- **Data export** — Download daily summaries as CSV or Excel

## File Structure
```
BotecoMasterDashboard/
├── app.py                      # Main Streamlit application (4 tabs)
├── auth.py                     # Authentication & session management
├── clipboard_ui.py             # HTML/JS clipboard helpers
├── config.py                   # Configuration constants & env resolution
├── database.py                 # SQLite database layer & schema
├── file_detector.py            # Auto-detects Petpooja export file types
├── logger.py                   # Centralized logging configuration
├── pos_parser.py               # Parses Item Report XLSX files
├── scope.py                    # Multi-location report aggregation
├── sheet_reports.py            # PNG report image generation + WhatsApp text
├── smart_upload.py             # Orchestrates multi-file upload pipeline
├── timing_parser.py            # Parses Restaurant Timing Report XLSX
├── ui_theme.py                 # Shared UI constants and Plotly theme defaults
├── utils.py                    # Helper functions (formatting, dates, growth calc)
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # Dev/test dependencies (includes runtime)
├── .streamlit/
│   └── config.toml             # Streamlit theme config
├── .devcontainer/
│   └── devcontainer.json       # VS Code dev container config
├── scripts/
│   └── inspect_exports.py      # Diagnostic script for POS files
│   └── profile_analytics_queries.py  # Synthetic benchmark for analytics SQL
└── data/
    └── boteco.db               # SQLite database (auto-created, gitignored)
```

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

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOTECO_LOG_FILE` | Optional file path for persistent logging |
