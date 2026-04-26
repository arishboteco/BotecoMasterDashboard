# AGENTS.md — BotecoMasterDashboard

## Project Overview

Python 3.11+ Streamlit dashboard for restaurant sales management ("Boteco Bangalore"). Ingests POS data from Petpooja exports, generates daily End-of-Day reports as PNG images and WhatsApp-ready text, and provides analytics dashboards.

## Commands

### Setup
```bash
python -m venv venv
source venv/bin/activate          # macOS/Linux
venv\Scripts\activate             # Windows
pip install -r requirements.txt
```

### Run
```bash
streamlit run app.py
```

### Test
```bash
pytest                            # run all tests
pytest tests/test_pos_parser.py   # run single test file
pytest tests/test_pos_parser.py::TestF -v  # run single test class
pytest tests/test_pos_parser.py::TestF::test_f_returns_float -v  # run single test
```

### Lint
Ruff is configured in `pyproject.toml` with:
- line length = 100
- rules: `E` (pycodestyle), `F` (pyflakes), `I` (import sorting), `B` (bugbear)

Use these exact commands:
```bash
ruff check . --select E,F,I,B                 # lint repository with configured baseline rules
ruff check <path> --select E,F,I,B --fix      # apply safe auto-fixes to a specific file/folder
ruff format <path>                             # format only touched files (do not run repo-wide yet)
```

## Code Style

### Imports
- Standard library first, then third-party, then local modules — one blank line between groups.
- Third-party: use common aliases (`import pandas as pd`, `import plotly.express as px`).
- Local: plain imports (`import config`, `import database`, `import pos_parser as parser`).
- Use `from __future__ import annotations` in files with forward references.

### Formatting
- 4-space indentation.
- Line length: keep under 100–120 characters.
- Double quotes for strings; single quotes inside f-string expressions and dict literals.
- Trailing commas in multi-line structures (dicts, lists, function args).

### Naming Conventions
- Modules/files: `snake_case` (e.g., `pos_parser.py`, `file_detector.py`).
- Functions: `snake_case` (e.g., `parse_item_order_details`, `detect_file_type`).
- Private helpers: leading underscore (e.g., `_f`, `_norm_header`, `_cell_date_to_iso`).
- Classes: `PascalCase` (e.g., `FileResult`, `DayResult`, `SmartUploadResult`).
- Constants: `UPPER_SNAKE_CASE` (e.g., `MONTHLY_TARGET`, `DATABASE_PATH`, `C_BRAND`).
- Variables: `snake_case` (e.g., `location_id`, `date_str`).

### Type Hints
- Extensively used. Annotate all function signatures.
- Import from `typing`: `Dict`, `List`, `Optional`, `Tuple`, `Any`, `Union`, `Generator`.
- Use type aliases for complex types (e.g., `ParseResult = Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]`).
- Use `@dataclass` for structured data containers.

### Error Handling
- Use try/except around file I/O, Excel parsing, and database operations.
- Graceful degradation: provide fallback paths (e.g., multiple Excel engines: `None`, `"openpyxl"`, `"xlrd"`).
- Validation functions return `(bool, List[str])` tuples: `validate_data(data)` → `(ok, errors)`.
- Defensive checks for None/NaN: `if val is None or (isinstance(val, float) and pd.isna(val))`.
- No custom exception classes — use built-in exceptions and return error tuples/messages.

### Logging
- Centralized via `logger.py` using Python's `logging` module under `boteco` namespace.
- Pattern: `from logger import get_logger` then `logger = get_logger(__name__)`.

### Docstrings
- Module-level docstring at top of every file.
- Function docstrings using Google-style or simple descriptive format (triple-quoted).
- Include Args/Returns sections for complex functions.

## Architecture

### Key Modules
| File/Folder | Purpose |
|------|---------|
| `app.py` | Main Streamlit app shell: bootstrap + auth gate + tab rendering |
| `tabs/` | UI tabs (`upload_tab.py`, `report_tab.py`, `analytics_tab.py`, `settings_tab.py`) |
| `services/upload_service.py` | Upload preview/import wrapper with overlap checks and options |
| `services/report_service.py` | Cached report data loaders (bundle, MTD maps, footfall rows) |
| `services/cache_invalidation.py` | Central post-import cache invalidation across read/report/analytics layers |
| `smart_upload.py` | Multi-file ingest orchestrator (detect, parse, merge, save) |
| `uploads/` | Upload domain package: models, routing, merge logic, dedicated parsers |
| `database.py` | DB facade + bootstrap/migrations + SQLite/Supabase mode switching |
| `database_reads.py` / `database_writes.py` / `database_auth.py` / `database_analytics.py` | Split DB responsibilities by concern |
| `repositories/` | Protocol-based repository interfaces and default DB-backed implementations |
| `scope.py` | Multi-location aggregation for report/analytics consumers |
| `sheet_reports.py` | PNG report generation and WhatsApp text formatter |
| `auth.py` / `auth_permissions.py` | Session/cookie authentication and role/location permission checks |
| `core/` | Shared domain models and date utilities |
| `components/` + `styles/` | Reusable UI components and theme/style system |
| `config.py`, `utils.py`, `ui_theme.py` | Configuration, formatting/math helpers, Plotly/UI theme defaults |

### Data Flow
Files uploaded → `file_detector.py` classifies → `smart_upload.py` orchestrates parsing → `pos_parser.py`/`timing_parser.py` extract data → `database.py` stores → `scope.py` aggregates → `sheet_reports.py` generates output.

### Database
- Raw SQLite with parameterized queries, `sqlite3.Row` row factory.
- Context manager `db_connection()` preferred over manual `get_connection()`/`conn.close()`.
- Multi-tenancy: locations (outlets) have separate data; admin users view all, managers scoped to their location.

## Testing
- Framework: pytest (`pytest.ini` and `tests/conftest.py` are present).
- Tests in `tests/` cover parser, upload pipeline, services, repositories, cache behavior,
  analytics logic, theming/style guardrails, and database modules.
- Example focused suites: `tests/test_upload_service.py`, `tests/test_sales_repository.py`,
  `tests/test_cache_invalidation.py`, `tests/test_database_phase4_modules.py`.

## Context7 Usage
- Always use Context7 when library/API documentation, code generation, setup, or configuration steps are needed — do not wait for explicit requests.
- Use `resolve-library-id` first to find the correct library ID (format: `/org/project`), then `query-docs` with your specific question.
- Applies to all libraries, frameworks, SDKs, APIs, and cloud services — even well-known ones.

## UI Quality

- For any PR that changes UI, complete `docs/visual_qa_checklist.md` before requesting review.
