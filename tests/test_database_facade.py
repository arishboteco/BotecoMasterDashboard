"""Tests for database facade exports and delegated origins."""

import database


def test_facade_groups_have_expected_symbols_and_callable_exports():
    expected_groups = {"auth", "reads", "writes", "analytics"}

    assert set(database.FACADE_EXPORT_GROUPS) == expected_groups

    for symbols in database.FACADE_EXPORT_GROUPS.values():
        for symbol in symbols:
            assert hasattr(database, symbol)
            assert callable(getattr(database, symbol))


def test_delegated_symbol_origins_match_grouped_exports():
    grouped_symbols = {
        symbol
        for symbols in database.FACADE_EXPORT_GROUPS.values()
        for symbol in symbols
    }

    assert grouped_symbols == set(database.DELEGATED_SYMBOL_ORIGINS)

    for symbol, module_name in database.DELEGATED_SYMBOL_ORIGINS.items():
        assert module_name in {
            "database_auth",
            "database_reads",
            "database_writes",
            "database_analytics",
        }
        assert symbol in database.__all__
