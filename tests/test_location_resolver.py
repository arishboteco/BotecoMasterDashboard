"""Tests for canonical location alias resolution."""

from services.location_resolver import build_location_alias_map, resolve_location_id


class TestBuildLocationAliasMap:
    def test_includes_exact_location_names_and_aliases(self):
        locations = [
            {"id": 10, "name": "Boteco - Indiqube"},
            {"id": 20, "name": "Boteco - Bagmane"},
        ]
        aliases = {
            "Boteco": "Boteco - Indiqube",
            "Boteco - Bagmane": "Boteco - Bagmane",
        }

        alias_map = build_location_alias_map(locations, aliases)

        assert alias_map["boteco - indiqube"] == 10
        assert alias_map["boteco - bagmane"] == 20
        assert alias_map["boteco"] == 10

    def test_skips_aliases_pointing_to_unknown_location_names(self):
        locations = [{"id": 10, "name": "Boteco - Indiqube"}]
        aliases = {
            "Boteco": "Boteco - Indiqube",
            "Ghost Outlet": "Nonexistent",
        }

        alias_map = build_location_alias_map(locations, aliases)

        assert "ghost outlet" not in alias_map
        assert alias_map["boteco"] == 10


class TestResolveLocationId:
    def test_resolves_by_alias(self):
        locations = [{"id": 10, "name": "Boteco - Indiqube"}]
        aliases = {"Boteco": "Boteco - Indiqube"}

        assert resolve_location_id("Boteco", locations, aliases) == 10

    def test_resolves_by_exact_db_location_name(self):
        locations = [{"id": 20, "name": "Boteco - Bagmane"}]
        aliases = {"Boteco": "Boteco - Indiqube"}

        assert resolve_location_id("Boteco - Bagmane", locations, aliases) == 20

    def test_returns_fallback_only_when_no_match(self):
        locations = [{"id": 10, "name": "Boteco - Indiqube"}]
        aliases = {"Boteco": "Boteco - Indiqube"}

        assert resolve_location_id("Unknown", locations, aliases, fallback_location_id=99) == 99

    def test_returns_none_when_no_match_and_no_fallback(self):
        locations = [{"id": 10, "name": "Boteco - Indiqube"}]
        aliases = {"Boteco": "Boteco - Indiqube"}

        assert resolve_location_id("Unknown", locations, aliases) is None
