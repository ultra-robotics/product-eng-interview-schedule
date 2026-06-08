"""SQLite connection helper for schedule storage.

The app stores everything in a single local SQLite file — no server to run.
SCHEDULE_DATABASE_URL may be a bare path (``./schedule.db``) or a
``sqlite:///abs/path.db`` URL; when unset we default to ``backend/schedule.db``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = _BACKEND_DIR / "schedule.db"


def resolve_db_path(url_or_path: str | None) -> Path:
    if not url_or_path or not url_or_path.strip():
        return DEFAULT_DB_PATH
    s = url_or_path.strip()
    if s.startswith("sqlite:///"):
        s = s[len("sqlite:///") :]
    elif s.startswith("sqlite://"):
        s = s[len("sqlite://") :]
    p = Path(s).expanduser()
    if not p.is_absolute():
        p = _BACKEND_DIR / p
    return p


def connect(url_or_path: str | None) -> sqlite3.Connection:
    """Open a fresh SQLite connection. Cheap enough to do per-request."""
    path = resolve_db_path(url_or_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    # WAL gives readers/writers concurrency; busy_timeout avoids "database is
    # locked" under FastAPI's threadpool.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
