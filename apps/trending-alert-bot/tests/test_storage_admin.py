import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from storage_admin import clear_all_notification_data


def create_test_database(database_path: Path):
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("""
            CREATE TABLE telegram_chats (
                chat_id INTEGER PRIMARY KEY,
                notification_mode TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE contracts (
                chain TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                token_address TEXT NOT NULL,
                PRIMARY KEY (chain, chat_id, token_address)
            )
            """)
        conn.execute("""
            CREATE TABLE contract_message_ids (
                chain TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                token_address TEXT NOT NULL,
                telegram_chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                FOREIGN KEY (chain, chat_id, token_address)
                    REFERENCES contracts(chain, chat_id, token_address)
                    ON DELETE CASCADE
            )
            """)
        conn.execute("""
            CREATE TABLE contract_notified_multipliers (
                chain TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                token_address TEXT NOT NULL,
                multiplier REAL NOT NULL,
                FOREIGN KEY (chain, chat_id, token_address)
                    REFERENCES contracts(chain, chat_id, token_address)
                    ON DELETE CASCADE
            )
            """)
        conn.execute("""
            CREATE TABLE contract_pending_multipliers (
                chain TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                token_address TEXT NOT NULL,
                multiplier_int INTEGER NOT NULL,
                count INTEGER NOT NULL,
                FOREIGN KEY (chain, chat_id, token_address)
                    REFERENCES contracts(chain, chat_id, token_address)
                    ON DELETE CASCADE
            )
            """)
        conn.execute("""
            CREATE TABLE narrative_analysis (
                chain TEXT NOT NULL,
                token_address TEXT NOT NULL,
                provider TEXT NOT NULL
            )
            """)
        conn.execute("""
            CREATE TABLE runtime_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)
        conn.execute(
            "INSERT INTO telegram_chats VALUES (?, ?)",
            (111, "all"),
        )
        conn.executemany(
            "INSERT INTO contracts VALUES (?, ?, ?)",
            [
                ("eth", 111, "TOKEN1"),
                ("eth", 222, "TOKEN2"),
            ],
        )
        conn.execute(
            "INSERT INTO contract_message_ids VALUES (?, ?, ?, ?, ?)",
            ("eth", 111, "TOKEN1", 111, 10),
        )
        conn.execute(
            "INSERT INTO contract_notified_multipliers VALUES (?, ?, ?, ?)",
            ("eth", 111, "TOKEN1", 2.0),
        )
        conn.execute(
            "INSERT INTO contract_pending_multipliers VALUES (?, ?, ?, ?, ?)",
            ("eth", 222, "TOKEN2", 2, 1),
        )
        conn.execute(
            "INSERT INTO narrative_analysis VALUES (?, ?, ?)",
            ("eth", "TOKEN1", "xai"),
        )
        conn.execute(
            "INSERT INTO runtime_state VALUES (?, ?)",
            ("last_summary_report_marker", "marker"),
        )


class StorageAdminTests(unittest.TestCase):
    def test_clear_all_notification_data_clears_every_database_and_keeps_metadata(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp)
            bot_targets = {
                "eth": {"data_dir": "data/eth-bot"},
                "multi": {"data_dir": "data/multi-bot"},
                "missing": {"data_dir": "data/missing-bot"},
            }
            for target in ("eth", "multi"):
                create_test_database(
                    app_root
                    / bot_targets[target]["data_dir"]
                    / "trending_alert_bot.sqlite"
                )

            results = clear_all_notification_data(
                app_root=app_root,
                bot_targets=bot_targets,
                now=datetime(2026, 7, 23, 12, 34, 56),
            )

            result_by_target = {result.target: result for result in results}
            self.assertEqual(result_by_target["eth"].status, "cleared")
            self.assertEqual(result_by_target["eth"].deleted_contracts, 2)
            self.assertEqual(result_by_target["multi"].status, "cleared")
            self.assertEqual(result_by_target["multi"].deleted_contracts, 2)
            self.assertEqual(result_by_target["missing"].status, "missing")

            for target in ("eth", "multi"):
                result = result_by_target[target]
                self.assertTrue(result.backup_path.exists())
                with sqlite3.connect(result.database_path) as conn:
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM contract_message_ids"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM contract_notified_multipliers"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM contract_pending_multipliers"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM telegram_chats"
                        ).fetchone()[0],
                        1,
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM narrative_analysis"
                        ).fetchone()[0],
                        1,
                    )
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM runtime_state").fetchone()[0],
                        1,
                    )

                with sqlite3.connect(result.backup_path) as backup_conn:
                    self.assertEqual(
                        backup_conn.execute(
                            "SELECT COUNT(*) FROM contracts"
                        ).fetchone()[0],
                        2,
                    )


if __name__ == "__main__":
    unittest.main()
