import os
import sqlite3
import threading

from config import SQLITE_DB_FILE


_SCHEMA_LOCK = threading.RLock()


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(SQLITE_DB_FILE), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema():
    with _SCHEMA_LOCK:
        with connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS telegram_chats (
                    chat_id INTEGER PRIMARY KEY,
                    type TEXT NOT NULL DEFAULT 'unknown',
                    title TEXT NOT NULL DEFAULT '',
                    username TEXT NOT NULL DEFAULT '',
                    first_name TEXT NOT NULL DEFAULT '',
                    last_name TEXT NOT NULL DEFAULT '',
                    added_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    removed_at TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    notification_mode TEXT NOT NULL DEFAULT 'all'
                );

                CREATE TABLE IF NOT EXISTS contracts (
                    chain TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    token_address TEXT NOT NULL,
                    initial_price REAL NOT NULL DEFAULT 0,
                    initial_market_cap REAL NOT NULL DEFAULT 0,
                    push_time TEXT NOT NULL DEFAULT '',
                    notified_multipliers_json TEXT NOT NULL DEFAULT '[]',
                    name TEXT NOT NULL DEFAULT '',
                    symbol TEXT NOT NULL DEFAULT '',
                    telegram_message_ids_json TEXT NOT NULL DEFAULT '{}',
                    pending_multiplier_json TEXT NOT NULL DEFAULT '',
                    last_notify_time TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (chain, chat_id, token_address)
                );
                """
            )
