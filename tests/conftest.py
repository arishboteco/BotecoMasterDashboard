"""Shared test fixtures for the BotecoMasterDashboard test suite."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

import database


@pytest.fixture
def tmp_db_path():
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def initialized_db(tmp_db_path, monkeypatch):
    """Initialize a fresh in-memory-like SQLite DB against a temp file.

    Patches DATABASE_PATH so all database module operations use the temp file.
    """
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_db_path)
    database.init_database()
    # Ensure at least one location exists for tests that need it
    with database.db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO locations (name) VALUES (?)", ("Test Outlet",)
        )
        conn.commit()
    yield tmp_db_path
