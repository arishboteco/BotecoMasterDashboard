# Boteco Dashboard — Production Deployment Checklist

## Pre-Deployment

- [ ] Set environment variables:
  - `SUPABASE_URL` — Supabase project URL
  - `SUPABASE_KEY` — Supabase anon key
  - `SUPABASE_SERVICE_KEY` — Supabase service role key (for privileged/admin operations)
  - `USE_SUPABASE=1` — Enable and enforce cloud database mode
  - `BOTECO_LOG_FILE=logs/boteco.log` — Log file path (optional)
- [ ] Verify `.env` is NOT in version control (`git status`)
- [ ] Run data integrity check: `python scripts/integrity_check.py`
- [ ] Run full tests: `pytest`

## Supabase Configuration

- [ ] RLS policies configured on all application tables
- [ ] Service role key is set only in secure deployment secrets
- [ ] Indexes and constraints are applied (especially date/location query paths)
- [ ] Health check works in Supabase mode: `curl "https://your-app.streamlit.app/?health=check"`

## First-Run Authentication Hardening

- [ ] On first boot, log in with bootstrap credentials: `admin` / `admin`
- [ ] Immediately change admin password in **Settings**
- [ ] Confirm at least one additional admin/manager user is created
- [ ] Validate login lockout behavior (failed-attempt throttling)
- [ ] Validate session persistence/logout flow

## Post-Deployment Smoke Tests

- [ ] Upload a test CSV/XLSX and verify data appears in Report tab
- [ ] Generate PNG report and verify layout/text
- [ ] Run basic analytics date ranges and confirm charts populate
- [ ] Check logs for structured output: `tail -f logs/boteco.log`

## Monitoring

- [ ] Streamlit Cloud dashboard shows no recurring errors
- [ ] Log file (if configured) is being written to
- [ ] Add log rotation/retention policy if using file logs
