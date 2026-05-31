import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


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
