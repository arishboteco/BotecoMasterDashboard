"""Tests for centralized backend table names."""

from db.table_names import (
    SQLITE_CATEGORY_SALES,
    SQLITE_DAILY_SUMMARIES,
    SQLITE_ITEM_SALES,
    SQLITE_PAYMENT_METHOD_SALES,
    SQLITE_SERVICE_SALES,
    SUPABASE_BILL_ITEMS,
    SUPABASE_CATEGORY_SUMMARY,
    SUPABASE_DAILY_SUMMARY,
    SUPABASE_PAYMENT_METHOD_SALES,
)


def test_table_name_constants_match_expected_values() -> None:
    assert SQLITE_DAILY_SUMMARIES == "daily_summaries"
    assert SQLITE_ITEM_SALES == "item_sales"
    assert SQLITE_CATEGORY_SALES == "category_sales"
    assert SQLITE_SERVICE_SALES == "service_sales"
    assert SQLITE_PAYMENT_METHOD_SALES == "payment_method_sales"
    assert SUPABASE_DAILY_SUMMARY == "daily_summary"
    assert SUPABASE_CATEGORY_SUMMARY == "category_summary"
    assert SUPABASE_BILL_ITEMS == "bill_items"
    assert SUPABASE_PAYMENT_METHOD_SALES == "payment_method_sales"


def test_database_modules_import_successfully() -> None:
    import database_reads  # noqa: F401
    import database_writes  # noqa: F401
