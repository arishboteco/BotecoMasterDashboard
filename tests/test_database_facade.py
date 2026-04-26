"""Smoke tests for the database facade API."""

import database


class TestDatabaseFacadeSmoke:
    def test_key_facade_functions_are_callable(self):
        key_functions = [
            "get_connection",
            "db_connection",
            "init_database",
            "bootstrap",
            "get_all_locations",
            "save_daily_summary",
            "get_daily_summary",
            "get_summaries_for_date_range",
            "get_monthly_footfall_multi",
            "get_service_sales_for_date_range",
        ]

        for name in key_functions:
            assert hasattr(database, name)
            assert callable(getattr(database, name))

    def test_delegated_exports_are_callable(self):
        delegated_names = set(database.DELEGATED_SYMBOL_ORIGINS)

        for name in delegated_names:
            assert hasattr(database, name)
            assert callable(getattr(database, name))
