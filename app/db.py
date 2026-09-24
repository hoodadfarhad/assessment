"""SQLite access. One connection per request via the get_conn dependency."""
import os
import sqlite3
from typing import Iterator

DB_PATH = os.environ.get("ADVISOR_DB", "advisor.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    account_number TEXT NOT NULL,
    balance REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS funds (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    nav REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    fund_code TEXT NOT NULL REFERENCES funds(code),
    units REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS transfers (
    id TEXT PRIMARY KEY,
    from_account TEXT NOT NULL REFERENCES accounts(id),
    to_account TEXT NOT NULL REFERENCES accounts(id),
    amount REAL NOT NULL,
    created_at TEXT NOT NULL,
    idempotency_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    type TEXT NOT NULL CHECK (type IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out')),
    amount REAL NOT NULL,
    created_at TEXT NOT NULL,
    transfer_id TEXT REFERENCES transfers(id)
);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
