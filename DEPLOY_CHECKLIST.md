# Boteco Dashboard — Production Deployment Checklist

## Pre-Deployment

- [ ] Set environment variables:
  - `SUPABASE_URL` — Supabase project URL
  - `SUPABASE_KEY` — Supabase anon key (**rotate immediately** — old key was in source history)
  - `SUPABASE_SERVICE_KEY` — Supabase service role key
  - `USE_SUPABASE=1` — Enable cloud database mode
  - `BOTECO_LOG_FILE=logs/boteco.log` — Log file path (optional)
- [ ] Verify `.env` is NOT in version control (`git status`)
- [ ] Dead code files removed (no `*.sql`, `generate_insert*.py` in repo root)
- [ ] Default admin password changed from the generated one shown on first run
- [ ] Run data integrity check: `python scripts/integrity_check.py`
- [ ] All tests pass: `pytest tests/ -v`

## Supabase Configuration

- [ ] **Rotate the Supabase anon key** — the previous key was committed to source history and must be invalidated via the Supabase dashboard (Settings → API → Regenerate anon key)
- [ ] RLS policies configured on all tables
- [ ] Service role key is set for admin operations
- [ ] Database indexes exist on `daily_summaries(location_id, date)`

## Post-Deployment

- [ ] Health check returns OK: `curl "https://your-app.streamlit.app/?health=check"`
- [ ] Login with admin credentials works (first-run password shown on login screen)
- [ ] Upload a test CSV — verify data appears in Report tab
- [ ] Generate PNG report — verify layout is correct
- [ ] Check logs for structured output: `tail -f logs/boteco.log`

## Monitoring

- [ ] Log file is being written to
- [ ] Streamlit Cloud dashboard shows no errors
- [ ] Set up log rotation if using file-based logging
