"""Centralized cache registry for Boteco Dashboard.

Modules register their in-process caches at import time.
After uploads or configuration changes, call invalidate_all()
to clear every registered cache in one shot.

Usage:
    import cache_manager
    _MY_CACHE = cache_manager.register("my_module")

    # Later, after an upload:
    cache_manager.invalidate_all()
"""

from __future__ import annotations

from typing import Dict

from boteco_logger import get_logger

logger = get_logger(__name__)

_caches: Dict[str, dict] = {}


def register(name: str) -> dict:
    """Register and return a named cache dict.

    The returned dict is the live cache object — populate it directly.
    Re-registering the same name returns the existing cache (idempotent).
    """
    if name not in _caches:
        _caches[name] = {}
    return _caches[name]


def invalidate(name: str) -> None:
    """Clear a single named cache."""
    if name in _caches:
        _caches[name].clear()
        logger.debug("Cache '%s' invalidated", name)


def invalidate_all() -> None:
    """Clear every registered cache."""
    for name, cache in _caches.items():
        cache.clear()
    logger.debug("All caches invalidated (%d caches)", len(_caches))
