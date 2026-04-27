"""Import safety tests for the Footfall tab."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType


def test_footfall_tab_imports_when_cache_helper_is_absent(monkeypatch):
    """A stale cache_invalidation module should not crash app startup."""
    fake_cache = ModuleType("services.cache_invalidation")
    monkeypatch.setitem(sys.modules, "services.cache_invalidation", fake_cache)
    sys.modules.pop("tabs.footfall_tab", None)

    module = importlib.import_module("tabs.footfall_tab")

    assert module is not None
