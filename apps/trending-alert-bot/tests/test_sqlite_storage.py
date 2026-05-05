import json
import os
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

    for name in ["config", "db_storage", "chat_storage", "storage", "monitor_flow"]:
        if name in sys.modules:
            del sys.modules[name]

    import config
    import chat_storage
    import monitor_flow
    from storage import ContractStorage

    return config, chat_storage, monitor_flow, ContractStorage


class SqliteStorageTests(unittest.TestCase):
    def test_chat_storage_migrates_legacy_json_and_writes_sqlite_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy_path = Path(tmp) / "telegram_chats.json"
            legacy_data = {
                "111": {
                    "chat_id": 111,
                    "type": "group",
                    "title": "Legacy Group",
                    "username": None,
                    "first_name": None,
                    "last_name": None,
                    "added_at": "2026-05-05 10:00:00",
                    "updated_at": "2026-05-05 10:00:00",
                    "active": True,
                    "message_count": 7,
                    "notification_mode": "anomaly",
                }
            }
            legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")
            original_json = legacy_path.read_text(encoding="utf-8")

            config, chat_storage, _, _ = load_storage_modules(tmp)
            storage = chat_storage.ChatStorage()

            self.assertTrue(Path(config.SQLITE_DB_FILE).exists())
            self.assertEqual(storage.get_notification_mode(111), "anomaly")
            self.assertEqual(storage.get_chat(111)["title"], "Legacy Group")
            self.assertEqual(storage.get_chat(111)["username"], "")
            self.assertEqual(storage.get_active_chats()[0]["chat_id"], 111)

            storage.increment_message_count(111)
            reloaded = chat_storage.ChatStorage()
            self.assertEqual(reloaded.get_chat(111)["message_count"], 8)
            self.assertEqual(legacy_path.read_text(encoding="utf-8"), original_json)

    def test_contract_storage_migrates_legacy_json_and_writes_sqlite_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, monitor_flow, ContractStorage = load_storage_modules(tmp)
            legacy_path = Path(monitor_flow.storage_file_path(111, "sol"))
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_data = {
                "TOKEN1": {
                    "initial_price": 1.0,
                    "initial_market_cap": 1000.0,
                    "push_time": "2026-05-05 10:00:00",
                    "notified_multipliers": [2.0],
                    "name": "Legacy Token",
                    "symbol": "LEG",
                    "telegram_message_ids": {"111": 222},
                    "pending_multiplier": {"multiplier_int": 3, "count": 1},
                    "last_notify_time": "2026-05-05 11:00:00",
                }
            }
            legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")
            original_json = legacy_path.read_text(encoding="utf-8")

            storage = ContractStorage(str(legacy_path), chain="sol", chat_id=111)

            self.assertTrue(Path(config.SQLITE_DB_FILE).exists())
            self.assertEqual(storage.get_contract("TOKEN1")["symbol"], "LEG")
            self.assertEqual(storage.get_telegram_message_id("TOKEN1", 111), 222)
            self.assertEqual(storage.get_pending_multiplier("TOKEN1"), {"multiplier_int": 3, "count": 1})

            storage.add_contract("TOKEN2", 5.0, {"marketCapUSD": "5000", "name": "Two", "symbol": "TWO"})
            storage.update_telegram_message_id("TOKEN2", 111, 333)
            storage.update_notified_multiplier("TOKEN2", 2.5)

            reloaded = ContractStorage(str(legacy_path), chain="sol", chat_id=111)
            self.assertEqual(reloaded.get_contract("TOKEN2")["symbol"], "TWO")
            self.assertEqual(reloaded.get_telegram_message_id("TOKEN2", 111), 333)
            self.assertEqual(reloaded.get_notified_multipliers("TOKEN2"), [2.5])
            self.assertEqual(legacy_path.read_text(encoding="utf-8"), original_json)

    def test_contract_storage_migrates_nullable_legacy_text_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, ContractStorage = load_storage_modules(tmp)
            legacy_path = Path(monitor_flow.storage_file_path(111, "sol"))
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_data = {
                "TOKEN_NULL": {
                    "initial_price": 1.0,
                    "initial_market_cap": 1000.0,
                    "push_time": None,
                    "name": None,
                    "symbol": None,
                    "last_notify_time": None,
                    "telegram_message_ids": {"111": 222},
                }
            }
            legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")

            storage = ContractStorage(str(legacy_path), chain="sol", chat_id=111)
            migrated = storage.get_contract("TOKEN_NULL")

            self.assertEqual(migrated["push_time"], "")
            self.assertEqual(migrated["name"], "")
            self.assertEqual(migrated["symbol"], "")
            self.assertNotIn("last_notify_time", migrated)

    def test_contract_storage_clear_all_only_removes_target_chat_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, ContractStorage = load_storage_modules(tmp)
            sol_111 = ContractStorage(monitor_flow.storage_file_path(111, "sol"), chain="sol", chat_id=111)
            sol_222 = ContractStorage(monitor_flow.storage_file_path(222, "sol"), chain="sol", chat_id=222)

            sol_111.add_contract("TOKEN1", 1.0, {"symbol": "ONE"})
            sol_222.add_contract("TOKEN2", 1.0, {"symbol": "TWO"})
            sol_111.clear_all()

            self.assertIsNone(sol_111.get_contract("TOKEN1"))
            self.assertEqual(sol_222.get_contract("TOKEN2")["symbol"], "TWO")


if __name__ == "__main__":
    unittest.main()
