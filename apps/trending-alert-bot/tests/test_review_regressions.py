import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_runtime_modules(data_dir: str):
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

    for name in [
        "config",
        "chat_storage",
        "storage",
        "telegram_bot",
        "monitor_flow",
        "notifier",
    ]:
        if name in sys.modules:
            del sys.modules[name]

    import config
    import chat_storage
    import monitor_flow
    import notifier
    from storage import ContractStorage

    return config, chat_storage, monitor_flow, notifier, ContractStorage


def sample_contract(**overrides):
    contract = {
        "tokenAddress": "TOKEN1",
        "pairAddress": "PAIR1",
        "symbol": "SAFE",
        "name": "Safe Token",
        "priceUSD": "2.0",
        "marketCapUSD": "2000",
        "volume": "1000",
        "holders": 42,
        "priceChange24H": "12.3",
        "createTime": "1714550400000",
        "dexName": "Raydium",
        "launchFrom": "pump",
        "links": {},
        "auditInfo": {},
        "security": {"honeyPot": {"value": False}},
    }
    contract.update(overrides)
    return contract


class ReviewRegressionTests(unittest.TestCase):
    def test_dry_run_multiplier_does_not_mark_notified(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(str(Path(tmp) / "contracts.json"))
            storage.add_contract("TOKEN1", 1.0, sample_contract(priceUSD="1.0"))
            storage.update_telegram_message_id("TOKEN1", 111, 222)

            monitor_flow.DRY_RUN = True
            monitor_flow.MULTIPLIER_CONFIRMATIONS = 1
            with mock.patch.object(monitor_flow, "load_kol_status", return_value=([], [])):
                monitor_flow.check_multipliers(sample_contract(priceUSD="2.0"), storage, "sol", chat_id=111)

            self.assertEqual(storage.get_notified_multipliers("TOKEN1"), [])

    def test_failed_multiplier_send_does_not_mark_notified(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(str(Path(tmp) / "contracts.json"))
            storage.add_contract("TOKEN1", 1.0, sample_contract(priceUSD="1.0"))
            storage.update_telegram_message_id("TOKEN1", 111, 222)
            storage.update_pending_multiplier("TOKEN1", 2, 1)

            monitor_flow.DRY_RUN = False
            monitor_flow.MULTIPLIER_CONFIRMATIONS = 2
            with (
                mock.patch.object(monitor_flow, "load_kol_status", return_value=([], [])),
                mock.patch.object(monitor_flow.notifier, "send_with_reply_sync", return_value=False),
            ):
                monitor_flow.check_multipliers(sample_contract(priceUSD="2.0"), storage, "sol", chat_id=111)

            self.assertEqual(storage.get_notified_multipliers("TOKEN1"), [])
            self.assertEqual(storage.get_pending_multiplier("TOKEN1"), {"multiplier_int": 2, "count": 1})

    def test_notification_html_escapes_external_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, notifier, _ = load_runtime_modules(tmp)

            msg = notifier.format_initial_notification(
                sample_contract(
                    symbol="<BAD&>",
                    name="Name <x>",
                    dexName="Dex & <One>",
                    launchFrom="Launch <Pad>",
                    links={"web": "https://example.com?a=1&b=<x>"},
                ),
                "sol",
                kol_holders=[{"name": "Alice & <Team>", "holdValueUSD": "12", "holdPercent": "0.5"}],
            )

            self.assertIn("&lt;BAD&amp;&gt;", msg)
            self.assertIn("Name &lt;x&gt;", msg)
            self.assertIn("Dex &amp; &lt;One&gt;", msg)
            self.assertIn("Alice &amp; &lt;Team&gt;", msg)
            self.assertIn("<code>TOKEN1</code>", msg)
            self.assertNotIn("<BAD&>", msg)

    def test_silent_init_marks_all_loaded_contracts_as_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(str(Path(tmp) / "contracts.json"))
            contracts = [
                sample_contract(tokenAddress="TOKEN1", priceUSD="1.0"),
                sample_contract(tokenAddress="TOKEN2", priceUSD="2.0"),
            ]

            with mock.patch.object(monitor_flow, "fetch_trending", return_value={"data": contracts}):
                monitor_flow.initialize_storage(storage, "sol")

            self.assertEqual(storage.get_contract("TOKEN1")["telegram_message_ids"], {"-1": -1})
            self.assertEqual(storage.get_contract("TOKEN2")["telegram_message_ids"], {"-1": -1})

    def test_summary_report_is_due_after_missing_exact_59_minute(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, _ = load_runtime_modules(tmp)
            now = dt.datetime(2026, 5, 5, 4, 5, tzinfo=dt.timezone(dt.timedelta(hours=8)))

            with mock.patch.object(monitor_flow, "beijing_now", return_value=now):
                self.assertEqual(monitor_flow.due_summary_report_hour(last_report_hour=-1), 4)
                self.assertTrue(monitor_flow.should_send_summary_report(last_report_hour=-1))
                self.assertEqual(monitor_flow.due_summary_report_hour(last_report_hour=4), -1)

    def test_add_chat_preserves_existing_notification_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, chat_storage, _, _, _ = load_runtime_modules(tmp)
            chat_storage.CHATS_FILE = str(Path(tmp) / "telegram_chats.json")
            storage = chat_storage.ChatStorage()

            storage.add_chat(111, {"type": "group", "title": "Group"})
            self.assertTrue(storage.set_notification_mode(111, "anomaly"))
            storage.add_chat(111, {"type": "group", "title": "Renamed"})

            self.assertEqual(storage.get_notification_mode(111), "anomaly")

    def test_bad_api_numeric_value_does_not_abort_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, _ = load_runtime_modules(tmp)
            bad_contract = sample_contract(priceUSD="N/A")

            with mock.patch.object(monitor_flow, "fetch_trending", return_value={"data": [bad_contract]}):
                self.assertFalse(monitor_flow.scan_once("sol", [], {}))


if __name__ == "__main__":
    unittest.main()
