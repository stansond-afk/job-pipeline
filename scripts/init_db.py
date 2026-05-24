"""Create (or update) the SQLite database from db/schema.sql.

Idempotent — safe to run multiple times. Will not drop existing data.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sibling package importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import DB_PATH, apply_schema, connect


def main() -> int:
    conn = connect()
    try:
        apply_schema(conn)
        # Sanity check: list tables
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        print(f"Database ready at: {DB_PATH}")
        print(f"Tables: {', '.join(tables)}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
