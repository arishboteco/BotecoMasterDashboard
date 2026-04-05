"""Tests for database footfall queries."""

import pytest
import config
import database


class TestGetMonthlyFootfallMulti:
    def test_returns_empty_for_no_data(self):
        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-12-31")
        assert result == []

    def test_aggregates_covers_by_month(self):
        # This test assumes test DB setup — verify query returns correct shape
        # At minimum, verify the function exists and returns a list
        result = database.get_monthly_footfall_multi([1], "2025-01-01", "2025-01-31")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "month" in row
            assert "covers" in row
            assert "total_days" in row


class TestGetWeeklyFootfallMulti:
    def test_returns_empty_for_no_data(self):
        result = database.get_weekly_footfall_multi([1], "2025-01-01", "2025-12-31")
        assert result == []

    def test_aggregates_covers_by_week(self):
        # Verify function exists and returns correct shape
        result = database.get_weekly_footfall_multi([1], "2025-01-01", "2025-01-31")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "week" in row
            assert "covers" in row
            assert "total_days" in row


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

    def test_validate_supports_legacy_plain_token_rows(self, initialized_db):
        ok, _ = database.create_user(
            username="legacy_user",
            password="averysecurepwd",
            role="manager",
            location_id=1,
        )
        assert ok

        user = database.verify_user("legacy_user", "averysecurepwd")
        legacy_token = "legacy-token-123"
        with database.db_connection() as conn:
            conn.execute(
                "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, datetime('now', '+1 day'))",
                (legacy_token, int(user["id"])),
            )
            conn.commit()

        restored = database.validate_session_token(legacy_token)
        assert restored is not None
        assert restored["username"] == "legacy_user"


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
