import os
import sqlite3
import threading

from config import SQLITE_DB_FILE
from timezone_utils import format_beijing_time


_SCHEMA_LOCK = threading.RLock()
_CONTRACT_COLUMNS = {
    "chain",
    "chat_id",
    "token_address",
    "initial_price",
    "initial_market_cap",
    "push_time",
    "name",
    "symbol",
    "last_notify_time",
}


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(SQLITE_DB_FILE), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _create_contracts_table(conn: sqlite3.Connection, table_name: str = "contracts"):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            chain TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            token_address TEXT NOT NULL,
            initial_price REAL NOT NULL DEFAULT 0,
            initial_market_cap REAL NOT NULL DEFAULT 0,
            push_time TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            symbol TEXT NOT NULL DEFAULT '',
            last_notify_time TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (chain, chat_id, token_address)
        )
        """
    )


def _create_contract_relation_tables(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS contract_message_ids (
            chain TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            token_address TEXT NOT NULL,
            telegram_chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            PRIMARY KEY (chain, chat_id, token_address, telegram_chat_id),
            FOREIGN KEY (chain, chat_id, token_address)
                REFERENCES contracts(chain, chat_id, token_address)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS contract_notified_multipliers (
            chain TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            token_address TEXT NOT NULL,
            multiplier REAL NOT NULL,
            notified_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (chain, chat_id, token_address, multiplier),
            FOREIGN KEY (chain, chat_id, token_address)
                REFERENCES contracts(chain, chat_id, token_address)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS contract_pending_multipliers (
            chain TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            token_address TEXT NOT NULL,
            multiplier_int INTEGER NOT NULL DEFAULT 0,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (chain, chat_id, token_address),
            FOREIGN KEY (chain, chat_id, token_address)
                REFERENCES contracts(chain, chat_id, token_address)
                ON DELETE CASCADE
        );
        """
    )


def _ensure_contract_schema(conn: sqlite3.Connection):
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'contracts'"
    ).fetchone()
    if not existing:
        _create_contracts_table(conn)
        _create_contract_relation_tables(conn)
        return

    if _table_columns(conn, "contracts") == _CONTRACT_COLUMNS:
        _create_contract_relation_tables(conn)
        return

    conn.execute("ALTER TABLE contracts RENAME TO contracts_previous")
    _create_contracts_table(conn)
    conn.execute(
        """
        INSERT INTO contracts (
            chain, chat_id, token_address, initial_price, initial_market_cap,
            push_time, name, symbol, last_notify_time
        )
        SELECT
            chain, chat_id, token_address, initial_price, initial_market_cap,
            push_time, name, symbol, last_notify_time
        FROM contracts_previous
        """
    )
    conn.execute("DROP TABLE contracts_previous")
    _create_contract_relation_tables(conn)


def _create_narrative_analysis_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS narrative_analysis (
            chain TEXT NOT NULL,
            token_address TEXT NOT NULL,
            provider TEXT NOT NULL,
            score INTEGER NOT NULL,
            confidence TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            summary TEXT NOT NULL,
            influencer_hits_json TEXT NOT NULL,
            risk_flags_json TEXT NOT NULL,
            evidence_links_json TEXT NOT NULL,
            raw_result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            PRIMARY KEY (chain, token_address, provider)
        )
        """
    )


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

                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                """
            )
            _ensure_contract_schema(conn)
            _create_narrative_analysis_table(conn)


def get_runtime_state(key: str, default: str = "") -> str:
    ensure_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM runtime_state WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def set_runtime_state(key: str, value: str):
    ensure_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runtime_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                updated_at=excluded.updated_at
            """,
            (key, value, format_beijing_time()),
        )
