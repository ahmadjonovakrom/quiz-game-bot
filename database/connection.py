import sqlite3
from pathlib import Path

from config import DB_PATH as CONFIG_DB_PATH

DB_PATH = Path(CONFIG_DB_PATH)


def get_conn():
    # check_same_thread=False is required because PTB dispatches handlers
    # via an executor that may run on a different thread than the one that
    # opened the connection.  Each call creates a NEW connection so there is
    # no shared mutable state between threads — the flag merely removes
    # SQLite's overly-conservative same-thread assertion.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # WAL mode: allows concurrent readers alongside a single writer,
    # which dramatically reduces "database is locked" errors under load.
    conn.execute("PRAGMA journal_mode=WAL")

    # Enforce foreign-key constraints on every connection.
    conn.execute("PRAGMA foreign_keys=ON")

    return conn