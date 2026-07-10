import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_storage_modules(data_dir: str):
    os.environ.update(
        {
            "BOT_CHECK_INTERVAL": "15",
            "BOT_CHAINS": json.dumps(["sol"]),
            "BOT_CHAIN": "sol",
            "BOT_NOTIFY_COOLDOWN_HOURS": "24",
            "BOT_MULTIPLIER_CONFIRMATIONS": "1",
            "BOT_NOTIFICATION_TYPES": json.dumps(["trending", "anomaly"]),
            "BOT_CHAIN_ALLOWLIST_JSON": json.dumps({"sol": {}}),
            "BOT_DATA_DIR": data_dir,
            "BOT_TELEGRAM_TOKEN": "123:test",
            "BOT_DRY_RUN": "0",
        }
    )

    for name in ["config", "db_storage", "chat_storage", "storage"]:
        if name in sys.modules:
            del sys.modules[name]

    import config
    import chat_storage
    import storage

    return config, chat_storage, storage.ContractStorage


class SqliteStorageTests(unittest.TestCase):
    def test_schema_recheck_after_lock_preserves_competing_migrator_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_storage_modules(tmp)
            import db_storage

            with db_storage.connect() as conn:
                conn.execute("PRAGMA user_version = 1")

            original_connect = db_storage.connect
            state = {"interleaved": False}

            class InterleavingConnection:
                def __init__(self):
                    self._connection = original_connect()

                def __enter__(self):
                    self._connection.__enter__()
                    return self

                def __exit__(self, *args):
                    return self._connection.__exit__(*args)

                def __getattr__(self, name):
                    return getattr(self._connection, name)

                def execute(self, statement, parameters=()):
                    if (
                        statement.strip() == "BEGIN IMMEDIATE"
                        and not state["interleaved"]
                    ):
                        state["interleaved"] = True
                        with original_connect() as competitor:
                            competitor.execute("BEGIN IMMEDIATE")
                            db_storage._recreate_tracking_schema(competitor)
                            competitor.execute(
                                "INSERT INTO contracts "
                                "(chain, chat_id, token_address) "
                                "VALUES ('sol', 111, 'CONCURRENT')"
                            )
                            competitor.commit()
                    return self._connection.execute(statement, parameters)

            with patch.object(
                db_storage,
                "connect",
                side_effect=lambda: InterleavingConnection(),
            ):
                db_storage.ensure_schema()

            self.assertTrue(state["interleaved"])
            with original_connect() as conn:
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM contracts WHERE token_address = 'CONCURRENT'"
                    ).fetchone()
                )

    def test_incompatible_contract_schema_is_recreated_but_chats_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, chat_storage, _ = load_storage_modules(tmp)
            chat_storage.ChatStorage().add_chat(
                111, {"type": "group", "title": "Keep Me"}
            )
            import db_storage

            with db_storage.connect() as conn:
                conn.execute("DROP TABLE contract_message_ids")
                conn.execute("DROP TABLE contract_notified_multipliers")
                conn.execute("DROP TABLE contract_pending_multipliers")
                conn.execute("DROP TABLE narrative_analysis")
                conn.execute("DROP TABLE contracts")
                conn.execute(
                    """
                    CREATE TABLE contracts (
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
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO contracts (chain, chat_id, token_address) "
                    "VALUES ('sol', 111, 'OLD')"
                )
                conn.execute("PRAGMA user_version = 1")

            db_storage.ensure_schema()

            with db_storage.connect() as conn:
                self.assertIsNotNone(
                    conn.execute(
                        "SELECT 1 FROM telegram_chats WHERE chat_id = 111"
                    ).fetchone()
                )
                self.assertIsNone(
                    conn.execute(
                        "SELECT 1 FROM contracts WHERE token_address = 'OLD'"
                    ).fetchone()
                )
                self.assertEqual(
                    conn.execute("PRAGMA user_version").fetchone()[0],
                    db_storage.CONTRACT_SCHEMA_VERSION,
                )
                for table in (
                    "contract_message_ids",
                    "contract_notified_multipliers",
                    "contract_pending_multipliers",
                ):
                    parents = {
                        row["table"]
                        for row in conn.execute(f"PRAGMA foreign_key_list({table})")
                    }
                    self.assertEqual(parents, {"contracts"})

    def test_chat_storage_ignores_legacy_json_and_writes_sqlite_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy_path = Path(tmp) / "telegram_chats.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "111": {
                            "chat_id": 111,
                            "type": "group",
                            "title": "Legacy Group",
                            "active": True,
                            "message_count": 7,
                            "notification_mode": "anomaly",
                        }
                    }
                ),
                encoding="utf-8",
            )

            config, chat_storage, _ = load_storage_modules(tmp)
            storage = chat_storage.ChatStorage()

            self.assertTrue(Path(config.SQLITE_DB_FILE).exists())
            self.assertIsNone(storage.get_chat(111))

            storage.add_chat(222, {"type": "group", "title": "SQLite Group"})
            storage.increment_message_count(222)

            reloaded = chat_storage.ChatStorage()
            self.assertEqual(reloaded.get_chat(222)["title"], "SQLite Group")
            self.assertEqual(reloaded.get_chat(222)["message_count"], 1)
            self.assertIsNone(reloaded.get_chat(111))
            self.assertTrue(legacy_path.exists())

    def test_contract_storage_uses_relation_tables_without_json_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, ContractStorage = load_storage_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)

            storage.add_contract("TOKEN1", 5.0, {"marketCapUSD": "5000", "name": "One", "symbol": "ONE"})
            storage.update_telegram_message_id("TOKEN1", 111, 333)
            storage.update_telegram_message_id("TOKEN1", 222, 444)
            storage.update_notified_multiplier("TOKEN1", 2.5)
            storage.update_pending_multiplier("TOKEN1", 3, 1)

            reloaded = ContractStorage(chain="sol", chat_id=111)
            self.assertEqual(reloaded.get_contract("TOKEN1")["symbol"], "ONE")
            self.assertEqual(reloaded.get_telegram_message_id("TOKEN1", 111), 333)
            self.assertEqual(reloaded.get_telegram_message_id("TOKEN1", 222), 444)
            self.assertEqual(reloaded.get_notified_multipliers("TOKEN1"), [2.5])
            self.assertEqual(reloaded.get_pending_multiplier("TOKEN1"), {"multiplier_int": 3, "count": 1})

            with sqlite3.connect(config.SQLITE_DB_FILE) as conn:
                contract_columns = {
                    row[1] for row in conn.execute("PRAGMA table_info(contracts)").fetchall()
                }
                self.assertNotIn("telegram_message_ids_json", contract_columns)
                self.assertNotIn("notified_multipliers_json", contract_columns)
                self.assertNotIn("pending_multiplier_json", contract_columns)

                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM contract_message_ids").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM contract_notified_multipliers").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM contract_pending_multipliers").fetchone()[0],
                    1,
                )

    def test_contract_storage_clear_all_cascades_relation_tables_for_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, ContractStorage = load_storage_modules(tmp)
            sol_111 = ContractStorage(chain="sol", chat_id=111)
            sol_222 = ContractStorage(chain="sol", chat_id=222)

            sol_111.add_contract("TOKEN1", 1.0, {"symbol": "ONE"})
            sol_111.update_telegram_message_id("TOKEN1", 111, 333)
            sol_111.update_notified_multiplier("TOKEN1", 2.0)
            sol_111.update_pending_multiplier("TOKEN1", 3, 1)
            sol_222.add_contract("TOKEN2", 1.0, {"symbol": "TWO"})
            sol_222.update_telegram_message_id("TOKEN2", 222, 444)
            sol_111.clear_all()

            self.assertIsNone(sol_111.get_contract("TOKEN1"))
            self.assertEqual(sol_222.get_contract("TOKEN2")["symbol"], "TWO")

            with sqlite3.connect(config.SQLITE_DB_FILE) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM contract_message_ids").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM contract_notified_multipliers").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM contract_pending_multipliers").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
