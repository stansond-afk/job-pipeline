"""SQLite connection + schema helpers.

Kept deliberately thin — scrapers should use stdlib sqlite3 directly for any
query that's more than trivial. This module is just for connection wiring
and the one-time schema application.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "jobs.db"
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with sensible defaults.

    - foreign_keys ON (SQLite disables them by default — we want them on)
    - row_factory = Row for dict-like access
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def apply_schema(conn: sqlite3.Connection, schema_path: Path = SCHEMA_PATH) -> None:
    """Apply db/schema.sql to the connection. Idempotent (uses IF NOT EXISTS)."""
    sql = schema_path.read_text()
    conn.executescript(sql)
    conn.commit()
