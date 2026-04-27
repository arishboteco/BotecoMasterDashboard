"""Phase 4 tests for decomposed database modules."""

import database


def test_database_auth_module_exposes_verify_user(initialized_db):
    import database_auth

    database.create_admin_user("phase4_admin", "averysecurepwd")
    user = database_auth.verify_user("phase4_admin", "averysecurepwd")
    assert user is not None
    assert user["username"] == "phase4_admin"


def test_database_reads_module_exposes_location_fetch(initialized_db):
    import database_reads

    locs = database_reads.get_all_locations()
    assert isinstance(locs, list)
    assert len(locs) >= 1


def test_database_writes_module_saves_upload_record(initialized_db):
    import database_reads
    import database_writes

    location_id = int(database_reads.get_all_locations()[0]["id"])
    database_writes.save_upload_record(
        location_id=location_id,
        date="2026-04-05",
        filename="phase4.csv",
        file_type="order_summary_csv",
        uploaded_by="phase4",
    )
    history = database_reads.get_upload_history(location_id, limit=5)
    assert any(h["filename"] == "phase4.csv" for h in history)


def test_database_writes_module_saves_daily_summary(initialized_db):
    import database_reads
    import database_writes

    location_id = int(database_reads.get_all_locations()[0]["id"])
    summary = {
        "date": "2026-04-06",
        "covers": 10,
        "gross_total": 1000.0,
        "net_total": 900.0,
        "cash_sales": 200.0,
        "card_sales": 300.0,
        "gpay_sales": 300.0,
        "zomato_sales": 50.0,
        "other_sales": 50.0,
        "categories": [{"category": "Food", "qty": 2, "amount": 600.0}],
        "services": [{"type": "Dinner", "amount": 700.0}],
        "top_items": [{"item_name": "Fries", "qty": 3, "amount": 300.0}],
    }

    summary_id = database_writes.save_daily_summary(location_id, summary)
    fetched = database_reads.get_daily_summary(location_id, "2026-04-06")

    assert summary_id > 0
    assert fetched is not None
    assert fetched["net_total"] == 900.0
    assert len(fetched["categories"]) == 1


def test_phase7_performance_indexes_exist(initialized_db):
    with database.db_connection() as conn:
        idx_rows = conn.execute("PRAGMA index_list('daily_summaries')").fetchall()
        names = {r[1] for r in idx_rows}

    assert "idx_daily_summaries_date" in names
    assert "idx_daily_summaries_date_location" in names


def test_database_writes_ignores_supabase_location_seed_errors(monkeypatch):
    import database_writes

    class _FailingQuery:
        def select(self, *_args, **_kwargs):
            return self

        def execute(self):
            raise RuntimeError("new row violates row-level security policy for table locations")

    class _FailingClient:
        def table(self, _name):
            return _FailingQuery()

    monkeypatch.setattr(database_writes.database, "use_supabase", lambda: True)
    monkeypatch.setattr(database_writes.database, "get_supabase_client", lambda: _FailingClient())

    database_writes.ensure_default_locations()


def test_database_writes_ignores_supabase_rls_upsert_errors(monkeypatch):
    import database_writes

    class _Query:
        data = []
        _operation = "read"

        def select(self, *_args, **_kwargs):
            self._operation = "read"
            return self

        def upsert(self, *_args, **_kwargs):
            self._operation = "write"
            return self

        def execute(self):
            if self._operation == "write":
                raise RuntimeError(
                    'new row violates row-level security policy for table "locations"'
                )
            return self

    class _Client:
        def table(self, name):
            if name == "locations":
                return _Query()
            raise AssertionError("Unexpected table name")

    monkeypatch.setattr(database_writes.database, "use_supabase", lambda: True)
    monkeypatch.setattr(database_writes.database, "get_supabase_client", lambda: _Client())

    database_writes.ensure_default_locations()
