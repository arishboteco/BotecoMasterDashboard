# SQLite Category Sales Migration Path

This project currently stores category totals in SQLite by writing **synthetic rows** into `item_sales` with `item_name` prefixed as `__category_row:`.

As of this change, `init_database()` also creates a real `category_sales` table for SQLite.

## Goals

- Keep existing behavior working (reads from synthetic rows continue unchanged).
- Provide an opt-in, safe migration path to populate `category_sales`.
- Avoid forced cutovers during deploy.

## New Table

`category_sales` schema:

- `id` (PK)
- `summary_id` (FK to `daily_summaries.id`)
- `category_name`
- `qty`
- `net_amount`
- `source` (`direct` by default; migration uses `synthetic_backfill`)
- `created_at`
- unique key on `(summary_id, category_name)`

## Backfill Function

Use:

```python
database.migrate_category_sales_from_synthetic_rows()
```

Behavior:

- SQLite-only (no-op in Supabase mode).
- Reads synthetic rows from `item_sales` where `item_name LIKE '__category_row:%'`.
- Inserts missing rows into `category_sales` using `INSERT OR IGNORE`.
- Idempotent and non-destructive.
- Returns counters: `{"inserted": int, "skipped_existing": int}`.

## Recommended Rollout

1. Deploy this schema + migration function while keeping all reads unchanged.
2. Run the backfill function once per environment.
3. Add dual-write (or direct-write) to `category_sales` in a later PR.
4. Switch reads to `category_sales` only after validation.
5. Remove synthetic-row dependency in a final cleanup PR.
