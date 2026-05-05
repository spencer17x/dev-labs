import datetime as dt
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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
        "db_storage",
        "storage",
        "telegram_bot",
        "monitor",
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
                self.assertEqual(monitor_flow.due_summary_report_hour(last_report_marker=""), 4)
                self.assertTrue(monitor_flow.should_send_summary_report(last_report_marker=""))
                marker = monitor_flow.summary_report_marker(4)
                self.assertEqual(monitor_flow.due_summary_report_hour(last_report_marker=marker), -1)

    def test_summary_report_marker_is_persisted_to_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, _ = load_runtime_modules(tmp)
            now = dt.datetime(2026, 5, 5, 4, 5, tzinfo=dt.timezone(dt.timedelta(hours=8)))

            with mock.patch.object(monitor_flow, "beijing_now", return_value=now):
                expected_marker = monitor_flow.summary_report_marker(4)
                monitor_flow.save_last_summary_marker(4)

            self.assertEqual(monitor_flow.load_last_summary_marker(), expected_marker)

            with mock.patch.object(monitor_flow, "beijing_now", return_value=now):
                self.assertEqual(monitor_flow.due_summary_report_hour(expected_marker), -1)

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

    def test_startup_silent_init_failure_does_not_abort_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import monitor

            storages = {}
            with mock.patch.object(monitor, "initialize_storage", side_effect=RuntimeError("api down")):
                monitor._bootstrap_storages("sol", set(), storages, [{"chat_id": 111}])

            self.assertIn("sol:111", storages)

    def test_scan_chains_once_continues_after_chain_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import monitor

            with mock.patch.object(monitor, "scan_once", side_effect=[RuntimeError("bsc down"), True]) as scan_mock:
                found = monitor.scan_chains_once(["bsc", "sol"], [], {}, None)

            self.assertTrue(found)
            self.assertEqual(scan_mock.call_count, 2)

    def test_summary_report_skips_inactive_chats(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, _ = load_runtime_modules(tmp)
            fake_chat_storage = mock.Mock()
            fake_chat_storage.get_active_chats.return_value = [{"chat_id": 111}]
            stats = {
                "sol": {
                    "trend_count": 0,
                    "total_multiplier_contracts": 0,
                    "win_count": 0,
                    "top_contracts": [],
                    "multiplier_distribution": {"2x": 0, "5x": 0, "10x_plus": 0},
                    "gain_distribution": {"20%": 0, "30%": 0, "50%": 0, "80%": 0},
                }
            }

            monitor_flow.ENABLE_TELEGRAM = True
            monitor_flow.DRY_RUN = False
            with (
                mock.patch.object(monitor_flow, "ChatStorage", return_value=fake_chat_storage),
                mock.patch.object(monitor_flow, "_load_latest_contract_map", return_value={}),
                mock.patch.object(monitor_flow, "_build_chain_stats", return_value=stats),
                mock.patch.object(monitor_flow, "format_summary_report", return_value="report"),
                mock.patch.object(monitor_flow.notifier, "send_sync") as send_mock,
            ):
                monitor_flow.send_summary_report({"sol:111": object(), "sol:222": object()})

            send_mock.assert_called_once_with("report", chat_id=111)

    def test_non_start_events_do_not_create_first_subscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import telegram_bot

            notifier = telegram_bot.TelegramNotifier.__new__(telegram_bot.TelegramNotifier)
            notifier.chat_storage = mock.Mock()
            notifier.chat_storage.get_chat.return_value = None

            chat = SimpleNamespace(
                id=111,
                type="group",
                title="Group",
                username=None,
                first_name=None,
                last_name=None,
            )
            update = SimpleNamespace(effective_chat=chat)
            asyncio.run(telegram_bot.TelegramNotifier._handle_any_message(notifier, update, SimpleNamespace()))

            notifier.chat_storage.add_chat.assert_not_called()

    def test_join_event_does_not_create_first_subscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import telegram_bot

            notifier = telegram_bot.TelegramNotifier.__new__(telegram_bot.TelegramNotifier)
            notifier.chat_storage = mock.Mock()
            notifier.chat_storage.get_chat.return_value = None
            notifier._get_chat_type_name = lambda chat_type: "群组"

            chat = SimpleNamespace(
                id=111,
                type="group",
                title="Group",
                username=None,
                first_name=None,
                last_name=None,
            )
            update = SimpleNamespace(
                my_chat_member=SimpleNamespace(
                    chat=chat,
                    old_chat_member=SimpleNamespace(status="left"),
                    new_chat_member=SimpleNamespace(status="member"),
                )
            )
            context = SimpleNamespace(bot=SimpleNamespace(send_message=mock.AsyncMock()))
            asyncio.run(telegram_bot.TelegramNotifier._handle_chat_member_updated(notifier, update, context))

            notifier.chat_storage.add_chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
