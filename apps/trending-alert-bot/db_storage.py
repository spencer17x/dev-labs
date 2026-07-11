import os
import sqlite3
import threading

from config import SQLITE_DB_FILE
from timezone_utils import format_beijing_time

_SCHEMA_LOCK = threading.RLock()
CONTRACT_SCHEMA_VERSION = 2
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
_RELATION_TABLES = (
    "contract_message_ids",
    "contract_notified_multipliers",
    "contract_pending_multipliers",
)


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(SQLITE_DB_FILE), exist_ok=True)
    conn = sqlite3.connect(
        SQLITE_DB_FILE,
        timeout=5,
        factory=_ClosingConnection,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _create_contracts_table(conn: sqlite3.Connection, table_name: str = "contracts"):
    conn.execute(f"""
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
        """)


def _create_contract_relation_tables(conn: sqlite3.Connection):
    conn.execute("""
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
        )
        """)
    conn.execute("""
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
        )
        """)
    conn.execute("""
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
        )
        """)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _contract_schema_is_current(conn: sqlite3.Connection) -> bool:
    if conn.execute("PRAGMA user_version").fetchone()[0] != CONTRACT_SCHEMA_VERSION:
        return False
    if not _table_exists(conn, "contracts"):
        return False
    return _table_columns(conn, "contracts") == _CONTRACT_COLUMNS


def _drop_tracking_tables(conn: sqlite3.Connection):
    for table_name in _RELATION_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.execute("DROP TABLE IF EXISTS narrative_analysis")
    conn.execute("DROP TABLE IF EXISTS contracts")


def _recreate_tracking_schema(conn: sqlite3.Connection):
    _drop_tracking_tables(conn)
    _create_contracts_table(conn)
    _create_contract_relation_tables(conn)
    _create_narrative_analysis_table(conn)
    conn.execute(f"PRAGMA user_version = {CONTRACT_SCHEMA_VERSION}")


def _create_narrative_analysis_table(conn: sqlite3.Connection):
    conn.execute("""
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
        """)


def ensure_schema():
    with _SCHEMA_LOCK:
        with connect() as conn:
            conn.execute("""
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
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
                """)
            if _contract_schema_is_current(conn):
                _create_contracts_table(conn)
                _create_contract_relation_tables(conn)
                _create_narrative_analysis_table(conn)
                return

            conn.execute("BEGIN IMMEDIATE")
            try:
                if _contract_schema_is_current(conn):
                    _create_contracts_table(conn)
                    _create_contract_relation_tables(conn)
                    _create_narrative_analysis_table(conn)
                else:
                    _recreate_tracking_schema(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                raise


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
