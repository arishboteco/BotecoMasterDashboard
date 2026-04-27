"""Tests for database footfall queries."""

import sys
from types import SimpleNamespace

import pytest

import config
import database
import database_analytics


class _BillItemsQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _columns):
        return self

    def in_(self, _column, _values):
        return self

    def gte(self, _column, _value):
        return self

    def lte(self, _column, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class _BillItemsClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, table_name):
        assert table_name == "bill_items"
        return _BillItemsQuery(self.rows)


def test_supabase_client_prefers_service_key_for_server_side_reads(monkeypatch):
    created = []

    def fake_create_client(url, key):
        created.append((url, key))
        return {"url": url, "key": key}

    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_KEY", "anon-key")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setattr(database, "_supabase_client", None)
    monkeypatch.setitem(sys.modules, "supabase", SimpleNamespace(create_client=fake_create_client))

    client = database.get_supabase_client()

    assert client == {"url": "https://example.supabase.co", "key": "service-key"}
    assert created == [("https://example.supabase.co", "service-key")]


class TestGetServiceSalesForDateRange:
    def test_supabase_classifies_17xx_timestamps_as_lunch(self, monkeypatch):
        rows = [
            {
                "created_date_time": "2026-04-08 17:30:00",
                "net_amount": 500.0,
                "bill_status": "SuccessOrder",
            },
            {
                "created_date_time": "2026-04-08 18:00:00",
                "net_amount": 700.0,
                "bill_status": "SuccessOrder",
            },
        ]
        monkeypatch.setattr(database, "use_supabase", lambda: True)
        monkeypatch.setattr(database, "get_supabase_client", lambda: _BillItemsClient(rows))

        result = database_analytics.get_service_sales_for_date_range(
            [1], "2026-04-08", "2026-04-08"
        )

        assert result == [
            {"type": "Lunch", "amount": 500.0},
            {"type": "Dinner", "amount": 700.0},
        ]

    def test_supabase_classifies_pos_non_iso_timestamps_by_hour(self, monkeypatch):
        rows = [
            {
                "created_date_time": "2026-04-8 12:00:00",
                "net_amount": 400.0,
                "bill_status": "SuccessOrder",
            },
            {
                "created_date_time": "2026-04-8 21:15:00",
                "net_amount": 600.0,
                "bill_status": "SuccessOrder",
            },
        ]
        monkeypatch.setattr(database, "use_supabase", lambda: True)
        monkeypatch.setattr(database, "get_supabase_client", lambda: _BillItemsClient(rows))

        result = database_analytics.get_service_sales_for_date_range(
            [1], "2026-04-08", "2026-04-08"
        )

        assert result == [
            {"type": "Lunch", "amount": 400.0},
            {"type": "Dinner", "amount": 600.0},
        ]


class TestGetMonthlyFootfallMulti:
    def test_returns_empty_for_no_data(self, initialized_db):
        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-12-31")
        assert result == []

    def test_aggregates_covers_by_month(self, initialized_db):
        with database.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO daily_summaries (location_id, date, covers, net_total, gross_total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "2025-01-01", 10, 1000.0, 1200.0),
            )
            conn.execute(
                """
                INSERT INTO daily_summaries (location_id, date, covers, net_total, gross_total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "2025-01-02", 20, 1800.0, 2000.0),
            )
            conn.execute(
                """
                INSERT INTO daily_summaries (location_id, date, covers, net_total, gross_total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "2025-02-01", 5, 600.0, 700.0),
            )
            conn.commit()

        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-02-28")

        assert result == [
            {
                "month": "2025-01",
                "covers": 30,
                "net_total": 2800.0,
                "gross_total": 3200.0,
                "total_days": 2,
            },
            {
                "month": "2025-02",
                "covers": 5,
                "net_total": 600.0,
                "gross_total": 700.0,
                "total_days": 1,
            },
        ]


class TestGetWeeklyFootfallMulti:
    def test_returns_empty_for_no_data(self, initialized_db):
        result = database.get_weekly_footfall_multi([1], "2025-01-01", "2025-12-31")
        assert result == []

    def test_aggregates_covers_by_week(self, initialized_db):
        with database.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO daily_summaries (location_id, date, covers, net_total)
                VALUES (?, ?, ?, ?)
                """,
                (1, "2025-01-01", 10, 1000.0),
            )
            conn.execute(
                """
                INSERT INTO daily_summaries (location_id, date, covers, net_total)
                VALUES (?, ?, ?, ?)
                """,
                (1, "2025-01-02", 15, 1500.0),
            )
            conn.execute(
                """
                INSERT INTO daily_summaries (location_id, date, covers, net_total)
                VALUES (?, ?, ?, ?)
                """,
                (1, "2025-01-08", 8, 900.0),
            )
            conn.commit()

        result = database.get_weekly_footfall_multi([1], "2025-01-01", "2025-01-31")

        assert result == [
            {
                "week": "2024-W53",
                "covers": 25,
                "net_total": 2500.0,
                "total_days": 2,
            },
            {
                "week": "2025-W01",
                "covers": 8,
                "net_total": 900.0,
                "total_days": 1,
            },
        ]


class TestSaveDailySummaryTopItems:
    def test_persists_top_items_rows(self, initialized_db):
        locations = database.get_all_locations()
        location_id = int(locations[0]["id"])
        date_str = "2026-04-01"

        summary = {
            "date": date_str,
            "covers": 120,
            "gross_total": 12000.0,
            "net_total": 11000.0,
            "cash_sales": 2500.0,
            "card_sales": 3000.0,
            "gpay_sales": 3500.0,
            "zomato_sales": 1000.0,
            "other_sales": 1000.0,
            "service_charge": 0.0,
            "cgst": 300.0,
            "sgst": 300.0,
            "discount": 1000.0,
            "complimentary": 0.0,
            "apc": 91.67,
            "turns": 1.2,
            "target": 166667.0,
            "pct_target": 6.6,
            "mtd_total_covers": 120,
            "mtd_net_sales": 11000.0,
            "mtd_discount": 1000.0,
            "mtd_avg_daily": 11000.0,
            "mtd_target": 5000000.0,
            "mtd_pct_target": 0.22,
            "categories": [{"category": "Food", "qty": 10, "amount": 7000.0}],
            "services": [{"type": "Dinner", "amount": 8000.0}],
            "top_items": [
                {"item_name": "Paneer Tikka", "qty": 7, "amount": 2800.0},
                {"item_name": "Craft Beer", "qty": 12, "amount": 3600.0},
            ],
        }

        database.save_daily_summary(location_id, summary)

        top = database.get_top_items_for_date_range(
            [location_id],
            date_str,
            date_str,
            limit=10,
        )
        by_name = {row["item_name"]: row for row in top}

        assert "Paneer Tikka" in by_name
        assert "Craft Beer" in by_name
        assert int(by_name["Paneer Tikka"]["qty"]) == 7
        assert float(by_name["Paneer Tikka"]["amount"]) == 2800.0


class TestSessionTokens:
    def test_create_user_session_stores_hashed_token(self, initialized_db):
        ok, _ = database.create_user(
            username="session_user",
            password="averysecurepwd",
            role="manager",
            location_id=1,
        )
        assert ok

        user = database.verify_user("session_user", "averysecurepwd")
        token = database.create_user_session(int(user["id"]), days=30)

        with database.db_connection() as conn:
            row = conn.execute(
                "SELECT token FROM user_sessions WHERE user_id = ?",
                (int(user["id"]),),
            ).fetchone()

        assert row is not None
        assert row["token"] != token
        assert len(row["token"]) == 64
        restored = database.validate_session_token(token)
        assert restored is not None
        assert restored["username"] == "session_user"

    def test_validate_rejects_legacy_plain_token_rows(self, initialized_db):
        ok, _ = database.create_user(
            username="legacy_user",
            password="averysecurepwd",
            role="manager",
            location_id=1,
        )
        assert ok

        user = database.verify_user("legacy_user", "averysecurepwd")
        plain_legacy_token = "legacy-token-123"
        with database.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (token, user_id, expires_at)
                VALUES (?, ?, datetime('now', '+1 day'))
                """,
                (plain_legacy_token, int(user["id"])),
            )
            conn.commit()

        restored = database.validate_session_token(plain_legacy_token)
        assert restored is None, (
            "Plain-text tokens must not authenticate — security risk"
        )

    def test_validate_accepts_hashed_token(self, initialized_db):
        ok, _ = database.create_user(
            username="hashed_user",
            password="averysecurepwd",
            role="manager",
            location_id=1,
        )
        assert ok

        user = database.verify_user("hashed_user", "averysecurepwd")
        token = database.create_user_session(int(user["id"]), days=1)
        restored = database.validate_session_token(token)
        assert restored is not None
        assert restored["username"] == "hashed_user"


class TestPasswordPolicy:
    def test_create_user_enforces_min_password_length(self, initialized_db):
        short = "x" * (config.MIN_PASSWORD_LENGTH - 1)
        ok, msg = database.create_user(
            username="short_pwd",
            password=short,
            role="manager",
            location_id=1,
        )

        assert not ok
        assert str(config.MIN_PASSWORD_LENGTH) in msg

    def test_public_password_reset_is_not_exposed(self):
        assert not hasattr(database, "reset_password")


class TestLoginLockout:
    def test_locks_after_max_failed_attempts_and_clears(self, initialized_db):
        username = "lock_user"
        database.create_admin_user(username, "averysecurepwd")

        locked, mins = database.is_login_locked(username)
        assert not locked
        assert mins == 0

        for _ in range(config.MAX_LOGIN_ATTEMPTS - 1):
            locked, _ = database.record_failed_login(username)
            assert not locked

        locked, mins = database.record_failed_login(username)
        assert locked
        assert mins > 0

        database.clear_failed_login(username)
        locked, mins = database.is_login_locked(username)
        assert not locked
        assert mins == 0


class TestLocationSettings:
    def test_update_location_settings_rejects_duplicate_name(self, initialized_db):
        locations = database.get_all_locations()
        location_id = int(locations[0]["id"])
        ok, _ = database.create_location("Second Outlet")
        assert ok

        with pytest.raises(ValueError, match="already exists"):
            database.update_location_settings(location_id, {"name": "Second Outlet"})

    def test_update_location_settings_allows_existing_same_name(self, initialized_db):
        locations = database.get_all_locations()
        location_id = int(locations[0]["id"])
        existing_name = str(locations[0]["name"])

        database.update_location_settings(location_id, {"name": existing_name})
        settings = database.get_location_settings(location_id)

        assert settings is not None
        assert settings["name"] == existing_name
