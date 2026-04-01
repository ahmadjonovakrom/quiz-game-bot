import sqlite3
from pathlib import Path

from config import DB_PATH as CONFIG_DB_PATH

DB_PATH = Path(CONFIG_DB_PATH)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn