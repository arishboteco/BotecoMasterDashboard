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


def test_payment_method_sales_table_exists(initialized_db):
    with database.db_connection() as conn:
        row = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'payment_method_sales'
            """
        ).fetchone()
        idx_rows = conn.execute("PRAGMA index_list('payment_method_sales')").fetchall()
        index_names = {r[1] for r in idx_rows}

    assert row is not None
    assert "idx_payment_method_sales_loc_date" in index_names


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


def test_wipe_all_data_supabase_includes_upload_history(monkeypatch):
    import database_writes

    class _Query:
        def __init__(self, client, table):
            self.client = client
            self.table = table
            self.count = 3

        def select(self, *_args, **_kwargs):
            return self

        def delete(self):
            return self

        def neq(self, *_args, **_kwargs):
            return self

        def execute(self):
            self.client.executed.append(self.table)
            return self

    class _Client:
        def __init__(self):
            self.executed = []

        def table(self, name):
            return _Query(self, name)

    client = _Client()
    monkeypatch.setattr(database_writes.database, "use_supabase", lambda: True)
    monkeypatch.setattr(database_writes.database, "get_supabase_admin_client", lambda: client)
    monkeypatch.setattr(database_writes.database, "get_supabase_client", lambda: None)

    counts, errors = database_writes.wipe_all_data()

    assert errors == []
    assert counts == {
        "bill_items": 3,
        "daily_summary": 3,
        "category_summary": 3,
        "payment_method_sales": 3,
        "upload_history": 3,
    }
    assert client.executed == [
        "bill_items",
        "daily_summary",
        "category_summary",
        "payment_method_sales",
        "upload_history",
        "bill_items",
        "daily_summary",
        "category_summary",
        "payment_method_sales",
        "upload_history",
    ]


def test_save_payment_method_sales_batch_upserts_by_date_location_method():
    import database_writes

    class _Query:
        def __init__(self, client):
            self.client = client

        def upsert(self, rows, **kwargs):
            self.client.upsert_rows.extend(rows)
            self.client.upsert_kwargs = kwargs
            return self

        def execute(self):
            return self

    class _Client:
        def __init__(self):
            self.table_name = None
            self.upsert_rows = []
            self.upsert_kwargs = {}

        def table(self, name):
            self.table_name = name
            return _Query(self)

    client = _Client()
    database_writes.save_payment_method_sales_batch(
        client,
        [
            {
                "location_id": 1,
                "date": "2026-05-01",
                "payment_method": "Zomato Delivery",
                "payment_key": "zomato_delivery",
                "amount": 1234.567,
            }
        ],
    )

    assert client.table_name == "payment_method_sales"
    assert client.upsert_kwargs == {"on_conflict": "location_id,date,payment_key"}
    assert client.upsert_rows == [
        {
            "location_id": 1,
            "date": "2026-05-01",
            "payment_method": "Zomato Delivery",
            "payment_key": "zomato_delivery",
            "amount": 1234.57,
            "source_report": "growth_report_day_wise",
        }
    ]


def test_save_daily_summary_sqlite_persists_payment_methods(initialized_db):
    import database_writes

    database_writes.save_daily_summary(
        1,
        {
            "date": "2026-05-01",
            "net_total": 1000.0,
            "payment_methods": [
                {
                    "payment_method": "Zomato Delivery",
                    "payment_key": "zomato_delivery",
                    "amount": 1000.456,
                }
            ],
        },
    )
    database_writes.save_daily_summary(
        1,
        {
            "date": "2026-05-01",
            "net_total": 500.0,
            "payment_methods": [
                {"payment_method": "Razorpay", "payment_key": "razorpay", "amount": 500.0}
            ],
        },
    )

    with database.db_connection() as conn:
        rows = conn.execute(
            """
            SELECT location_id, date, payment_method, payment_key, amount, source_report
            FROM payment_method_sales
            WHERE location_id = 1 AND date = '2026-05-01'
            ORDER BY payment_key
            """
        ).fetchall()

    assert [dict(row) for row in rows] == [
        {
            "location_id": 1,
            "date": "2026-05-01",
            "payment_method": "Razorpay",
            "payment_key": "razorpay",
            "amount": 500.0,
            "source_report": "growth_report_day_wise",
        }
    ]


def test_save_category_summary_batch_deduplicates_exact_category_conflicts():
    import database_writes

    class _Query:
        def __init__(self, client):
            self.client = client

        def upsert(self, rows, **kwargs):
            self.client.upsert_rows.extend(rows)
            self.client.upsert_kwargs = kwargs
            return self

        def execute(self):
            return self

    class _Client:
        def __init__(self):
            self.upsert_rows = []
            self.upsert_kwargs = {}

        def table(self, _name):
            return _Query(self)

    client = _Client()
    database_writes.save_category_summary_batch(
        client,
        [
            {
                "location_id": 1,
                "date": "2026-05-01",
                "category_name": "Beer",
                "normalized_category": "beer",
                "net_amount": 10.0,
                "qty": 1,
            },
            {
                "location_id": 1,
                "date": "2026-05-01",
                "category_name": "Beer",
                "normalized_category": "beer",
                "net_amount": 99.0,
                "qty": 9,
            },
        ],
    )

    assert len(client.upsert_rows) == 1
    assert client.upsert_kwargs["on_conflict"] == "location_id,date,category_name"
    assert client.upsert_rows[0]["normalized_category"] == "beer"
    assert client.upsert_rows[0]["net_amount"] == 99.0
    assert client.upsert_rows[0]["qty"] == 9


def test_save_category_summary_batch_keeps_distinct_categories_same_normalized():
    import database_writes

    class _Query:
        def __init__(self, client):
            self.client = client

        def upsert(self, rows, **kwargs):
            self.client.upsert_rows.extend(rows)
            self.client.upsert_kwargs = kwargs
            return self

        def execute(self):
            return self

    class _Client:
        def __init__(self):
            self.upsert_rows = []
            self.upsert_kwargs = {}

        def table(self, _name):
            return _Query(self)

    client = _Client()
    database_writes.save_category_summary_batch(
        client,
        [
            {
                "location_id": 1,
                "date": "2026-05-07",
                "category_name": "Sake & Soju",
                "group_name": "Liquor",
                "normalized_category": "Liquor",
                "net_amount": 410.0,
                "qty": 2,
            },
            {
                "location_id": 1,
                "date": "2026-05-07",
                "category_name": "Red Wine",
                "group_name": "Liquor",
                "normalized_category": "Liquor",
                "net_amount": 590.0,
                "qty": 1,
            },
        ],
    )

    assert client.upsert_kwargs["on_conflict"] == "location_id,date,category_name"
    assert len(client.upsert_rows) == 2
    assert {row["category_name"] for row in client.upsert_rows} == {"Sake & Soju", "Red Wine"}
