import datetime as dt
import asyncio
import json
import os
import sys
import tempfile
import unittest
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
    def test_narrative_config_defaults_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, _, _, _ = load_runtime_modules(tmp)

            self.assertFalse(config.NARRATIVE_ENABLED)
            self.assertEqual(config.NARRATIVE_PROVIDER, "xai")
            self.assertEqual(config.NARRATIVE_CACHE_TTL_HOURS, 12)
            self.assertEqual(config.NARRATIVE_MIN_EVIDENCE, 3)
            self.assertEqual(config.NARRATIVE_TIMEOUT_SECONDS, 20)
            self.assertEqual(config.XAI_API_KEY, "")

    def test_dry_run_multiplier_does_not_mark_notified(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
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
            storage = ContractStorage(chain="sol", chat_id=111)
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

    def test_honeypot_contract_clears_pending_and_skips_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
            storage.add_contract("TOKEN1", 1.0, sample_contract(priceUSD="1.0"))
            storage.update_telegram_message_id("TOKEN1", 111, 222)
            storage.update_pending_multiplier("TOKEN1", 2, 1)
            honeypot = sample_contract(
                priceUSD="2.0",
                security={"honeyPot": {"value": True}},
            )

            monitor_flow.DRY_RUN = False
            monitor_flow.MULTIPLIER_CONFIRMATIONS = 1
            with (
                mock.patch.object(
                    monitor_flow,
                    "load_kol_status",
                    return_value=([], []),
                ) as kol_mock,
                mock.patch.object(
                    monitor_flow.notifier,
                    "send_with_reply_sync",
                    return_value=True,
                ) as send_mock,
            ):
                monitor_flow.check_multipliers(honeypot, storage, "sol", chat_id=111)

            kol_mock.assert_not_called()
            send_mock.assert_not_called()
            self.assertIsNone(storage.get_pending_multiplier("TOKEN1"))
            self.assertEqual(storage.get_notified_multipliers("TOKEN1"), [])

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

    def test_initial_notification_includes_narrative_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, notifier, _ = load_runtime_modules(tmp)

            msg = notifier.format_initial_notification(
                sample_contract(),
                "sol",
                narrative={
                    "tags": ["meme", "binance_related"],
                    "score": 72,
                    "summary": "CA matched in active meme posts.",
                    "confidence": "medium",
                    "risk_flags": ["mostly_shill_posts"],
                },
            )

            self.assertIn("🧠 叙事: meme, binance_related", msg)
            self.assertIn("⭐ 叙事分: 72/100", msg)
            self.assertIn("📌 依据: CA matched in active meme posts.", msg)
            self.assertIn("⚠️ 风险: mostly_shill_posts", msg)

    def test_initial_notification_without_narrative_omits_narrative_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, notifier, _ = load_runtime_modules(tmp)

            for kwargs in ({}, {"narrative": None}):
                msg = notifier.format_initial_notification(sample_contract(), "sol", **kwargs)

                self.assertIn("[SOL] 📈 趋势通知", msg)
                self.assertIn("💎 SAFE (Safe Token)", msg)
                self.assertNotIn("🧠 叙事", msg)

    def test_initial_notification_escapes_narrative_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, notifier, _ = load_runtime_modules(tmp)

            msg = notifier.format_initial_notification(
                sample_contract(),
                "sol",
                narrative={
                    "tags": ["<meme&>", "binance"],
                    "score": 72,
                    "summary": "CA <matched> & active posts.",
                    "confidence": "<medium&>",
                    "risk_flags": ["<mostly_shill&>"],
                },
            )

            self.assertIn("🧠 叙事: &lt;meme&amp;&gt;, binance", msg)
            self.assertIn("📌 依据: CA &lt;matched&gt; &amp; active posts.", msg)
            self.assertIn("🔎 置信度: &lt;medium&amp;&gt;", msg)
            self.assertIn("⚠️ 风险: &lt;mostly_shill&amp;&gt;", msg)
            self.assertNotIn("<meme&>", msg)
            self.assertNotIn("CA <matched> & active posts.", msg)

    def test_malformed_narrative_shapes_do_not_raise_or_split_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, notifier, _ = load_runtime_modules(tmp)

            msg = notifier.format_initial_notification(sample_contract(), "sol", narrative="narrative")

            self.assertNotIn("🧠 叙事", msg)

            msg = notifier.format_initial_notification(
                sample_contract(),
                "sol",
                narrative={
                    "tags": "meme",
                    "score": 72,
                    "summary": "shape fallback",
                    "confidence": "medium",
                    "risk_flags": 123,
                },
            )

            self.assertIn("🧠 叙事: N/A", msg)
            self.assertIn("⚠️ 风险: none", msg)
            self.assertNotIn("m, e, m, e", msg)

    def test_initial_notification_positional_anomaly_argument_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, notifier, _ = load_runtime_modules(tmp)

            msg = notifier.format_initial_notification(sample_contract(), "sol", None, None, True)

            self.assertIn("[SOL] ⚡️ 异动通知", msg)
            self.assertNotIn("🧠 叙事", msg)

    def test_candidate_notification_uses_narrative_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
            contract = sample_contract(tokenAddress="TOKEN1", priceUSD="1.0")
            fake_analysis = mock.Mock()
            fake_analysis.to_display_dict.return_value = {
                "tags": ["meme"],
                "score": 66,
                "summary": "Meme posts with CA evidence.",
                "confidence": "medium",
                "risk_flags": [],
            }

            monitor_flow.ENABLE_TELEGRAM = False
            monitor_flow.DRY_RUN = True
            with (
                mock.patch.object(monitor_flow, "analyze_contract_narrative", return_value=fake_analysis) as narrative_mock,
                mock.patch.object(monitor_flow, "format_initial_notification", return_value="msg") as format_mock,
            ):
                sent = monitor_flow._send_candidate_notification(
                    storage,
                    111,
                    "sol",
                    contract,
                    [],
                    [],
                    False,
                )

            self.assertEqual(sent, 1)
            narrative_mock.assert_called_once()
            self.assertEqual(format_mock.call_args.kwargs["narrative"]["score"], 66)

    def test_candidate_notification_continues_when_narrative_analysis_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
            contract = sample_contract(tokenAddress="TOKEN1", priceUSD="1.0")

            monitor_flow.ENABLE_TELEGRAM = False
            monitor_flow.DRY_RUN = True
            with (
                mock.patch.object(monitor_flow, "analyze_contract_narrative", return_value=None) as narrative_mock,
                mock.patch.object(monitor_flow, "format_initial_notification", return_value="msg") as format_mock,
            ):
                sent = monitor_flow._send_candidate_notification(
                    storage,
                    111,
                    "sol",
                    contract,
                    [],
                    [],
                    False,
                )

            self.assertEqual(sent, 1)
            narrative_mock.assert_called_once_with(contract, "sol", [])
            self.assertIsNone(format_mock.call_args.kwargs["narrative"])

    def test_scan_once_memoizes_failed_narrative_across_chats(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, _ = load_runtime_modules(tmp)
            contract = sample_contract(tokenAddress="TOKEN1", priceUSD="1.0")
            active_chats = [
                {"chat_id": 111},
                {"chat_id": 222},
                {"chat_id": 333},
            ]

            monitor_flow.ENABLE_TELEGRAM = False
            monitor_flow.DRY_RUN = True
            with (
                mock.patch.object(
                    monitor_flow,
                    "fetch_trending",
                    return_value={"data": [contract]},
                ),
                mock.patch.object(
                    monitor_flow,
                    "_pick_trend_and_anomaly_contract",
                    return_value=((contract, [], []), None),
                ),
                mock.patch.object(
                    monitor_flow,
                    "analyze_contract_narrative",
                    return_value=None,
                ) as narrative_mock,
                mock.patch.object(
                    monitor_flow,
                    "format_initial_notification",
                    return_value="msg",
                ),
            ):
                monitor_flow.scan_once("sol", active_chats, {})

            narrative_mock.assert_called_once_with(contract, "sol", [])

    def test_candidate_notification_continues_when_narrative_display_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
            contract = sample_contract(tokenAddress="TOKEN1", priceUSD="1.0")
            fake_analysis = mock.Mock()
            fake_analysis.to_display_dict.side_effect = ValueError("bad display")

            monitor_flow.ENABLE_TELEGRAM = False
            monitor_flow.DRY_RUN = True
            with (
                mock.patch.object(monitor_flow, "analyze_contract_narrative", return_value=fake_analysis),
                mock.patch.object(monitor_flow, "format_initial_notification", return_value="msg") as format_mock,
                mock.patch("builtins.print") as print_mock,
            ):
                sent = monitor_flow._send_candidate_notification(
                    storage,
                    111,
                    "sol",
                    contract,
                    [],
                    [],
                    False,
                )

            self.assertEqual(sent, 1)
            self.assertIsNone(format_mock.call_args.kwargs["narrative"])
            printed_lines = [args[0] for args, _ in print_mock.call_args_list if args]
            self.assertTrue(
                any(
                    "叙事分析失败" in line
                    and "[SOL]" in line
                    and "SAFE" in line
                    and "TOKEN1" in line
                    for line in printed_lines
                )
            )

    def test_existing_candidate_notification_skips_narrative_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
            contract = sample_contract(tokenAddress="TOKEN1", priceUSD="1.0")
            storage.add_contract("TOKEN1", 1.0, contract)
            storage.update_telegram_message_id("TOKEN1", 111, 222)

            with (
                mock.patch.object(monitor_flow, "analyze_contract_narrative") as narrative_mock,
                mock.patch.object(monitor_flow, "format_initial_notification") as format_mock,
            ):
                sent = monitor_flow._send_candidate_notification(
                    storage,
                    111,
                    "sol",
                    contract,
                    [],
                    [],
                    False,
                )

            self.assertEqual(sent, 0)
            narrative_mock.assert_not_called()
            format_mock.assert_not_called()

    def test_cooldown_candidate_notification_skips_narrative_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
            contract = sample_contract(tokenAddress="TOKEN1", priceUSD="1.0")
            storage.add_contract("TOKEN1", 1.0, contract)

            with (
                mock.patch.object(monitor_flow, "is_on_cooldown", return_value=True) as cooldown_mock,
                mock.patch.object(monitor_flow, "analyze_contract_narrative") as narrative_mock,
                mock.patch.object(monitor_flow, "format_initial_notification") as format_mock,
            ):
                sent = monitor_flow._send_candidate_notification(
                    storage,
                    111,
                    "sol",
                    contract,
                    [],
                    [],
                    False,
                )

            self.assertEqual(sent, 0)
            cooldown_mock.assert_called_once_with(storage, "TOKEN1")
            narrative_mock.assert_not_called()
            format_mock.assert_not_called()

    def test_silent_init_marks_all_loaded_contracts_as_suppressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, ContractStorage = load_runtime_modules(tmp)
            storage = ContractStorage(chain="sol", chat_id=111)
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

    def test_base_filters_ignore_audit_holder_percentages(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, _ = load_runtime_modules(tmp)
            contract = sample_contract(
                auditInfo={
                    "newHp": 99,
                    "insiderHp": 99,
                    "bundleHp": 99,
                    "devHp": 99,
                }
            )

            self.assertTrue(monitor_flow._passes_base_filters(contract, "sol"))

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

    def test_telegram_startup_failure_reaches_main_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import telegram_bot

            notifier = telegram_bot.TelegramNotifier()
            with mock.patch.object(
                notifier, "_setup_application", side_effect=RuntimeError("invalid token")
            ), mock.patch("traceback.print_exc"):
                with self.assertRaises(telegram_bot.TelegramRuntimeError):
                    notifier.start_bot()

    def test_telegram_health_rejects_dead_ready_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import telegram_bot

            notifier = telegram_bot.TelegramNotifier()
            notifier._ready_event.set()
            notifier.bot_loop = mock.Mock()
            notifier.bot_thread = mock.Mock()
            notifier.bot_thread.is_alive.return_value = False

            with self.assertRaises(telegram_bot.TelegramRuntimeError):
                notifier.ensure_healthy()

    def test_monitor_does_not_retry_dead_telegram_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import monitor
            import telegram_bot

            chat_storage = mock.Mock()
            chat_storage.get_active_chats.return_value = []
            worker_error = telegram_bot.TelegramRuntimeError("worker died")

            with (
                mock.patch.object(monitor, "ChatStorage", return_value=chat_storage),
                mock.patch.object(monitor, "_startup_telegram"),
                mock.patch.object(monitor, "SILENT_INIT", False),
                mock.patch.object(monitor, "_initial_report_marker", return_value=""),
                mock.patch.object(monitor, "load_last_summary_marker", return_value=""),
                mock.patch.object(monitor.notifier, "ensure_healthy", side_effect=worker_error),
                mock.patch.object(monitor.time, "sleep") as sleep_mock,
            ):
                with self.assertRaises(telegram_bot.TelegramRuntimeError):
                    monitor.monitor_trending()

            sleep_mock.assert_not_called()

    def test_dry_run_without_chats_scans_once_without_silent_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            load_runtime_modules(tmp)
            import monitor

            chat_storage = mock.Mock()
            chat_storage.get_active_chats.return_value = []

            with (
                mock.patch.object(monitor, "ChatStorage", return_value=chat_storage),
                mock.patch.object(monitor, "DRY_RUN", True),
                mock.patch.object(monitor, "ENABLE_TELEGRAM", True),
                mock.patch.object(monitor, "SILENT_INIT", True),
                mock.patch.object(monitor, "initialize_storage") as initialize_mock,
                mock.patch.object(monitor, "scan_chains_once", return_value=False) as scan_mock,
                mock.patch.object(monitor, "send_summary_report") as report_mock,
                mock.patch.object(monitor, "due_summary_report_hour", return_value=4),
                mock.patch.object(monitor, "load_last_summary_marker", return_value=""),
                mock.patch.object(monitor, "_initial_report_marker", return_value=""),
                mock.patch.object(monitor.notifier, "start_bot") as start_mock,
                mock.patch.object(monitor.notifier, "ensure_healthy") as health_mock,
                mock.patch.object(
                    monitor.time,
                    "sleep",
                    side_effect=AssertionError("dry-run must not sleep"),
                ) as sleep_mock,
            ):
                try:
                    monitor.monitor_trending()
                except AssertionError as exc:
                    self.fail(str(exc))

            initialize_mock.assert_not_called()
            start_mock.assert_not_called()
            health_mock.assert_not_called()
            report_mock.assert_not_called()
            sleep_mock.assert_not_called()
            scan_mock.assert_called_once()
            self.assertEqual(scan_mock.call_args.args[1], [{"chat_id": 0}])

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

    def test_summary_report_retries_only_failed_chats(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, monitor_flow, _, _ = load_runtime_modules(tmp)
            fake_chat_storage = mock.Mock()
            fake_chat_storage.get_active_chats.return_value = [
                {"chat_id": 111},
                {"chat_id": 222},
            ]
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
            attempts = {111: 0, 222: 0}

            def send_report(message, chat_id):
                attempts[chat_id] += 1
                if chat_id == 111:
                    return {111: 10}
                if attempts[chat_id] == 1:
                    return {}
                return {222: 20}

            monitor_flow.ENABLE_TELEGRAM = True
            monitor_flow.DRY_RUN = False
            with (
                mock.patch.object(monitor_flow, "ChatStorage", return_value=fake_chat_storage),
                mock.patch.object(monitor_flow, "_load_latest_contract_map", return_value={}),
                mock.patch.object(monitor_flow, "_build_chain_stats", return_value=stats),
                mock.patch.object(monitor_flow, "format_summary_report", return_value="report"),
                mock.patch.object(
                    monitor_flow.notifier,
                    "send_sync",
                    side_effect=send_report,
                ),
            ):
                first_result = monitor_flow.send_summary_report(
                    {"sol:111": object(), "sol:222": object()},
                    report_hour=4,
                )
                report_marker = monitor_flow.summary_report_marker(4)

                self.assertFalse(first_result)
                self.assertEqual(
                    monitor_flow.get_runtime_state(
                        "last_summary_report_marker:111"
                    ),
                    report_marker,
                )
                self.assertEqual(
                    monitor_flow.get_runtime_state(
                        "last_summary_report_marker:222"
                    ),
                    "",
                )

                second_result = monitor_flow.send_summary_report(
                    {"sol:111": object(), "sol:222": object()},
                    report_hour=4,
                )

            self.assertTrue(second_result)
            self.assertEqual(attempts, {111: 1, 222: 2})
            self.assertEqual(
                monitor_flow.get_runtime_state("last_summary_report_marker:222"),
                report_marker,
            )

    def test_monitor_advances_summary_marker_only_after_all_chats_succeed(self):
        for delivery_succeeded in (False, True):
            with self.subTest(delivery_succeeded=delivery_succeeded):
                with tempfile.TemporaryDirectory() as tmp:
                    load_runtime_modules(tmp)
                    import monitor

                    chat_storage = mock.Mock()
                    chat_storage.get_active_chats.return_value = [{"chat_id": 111}]
                    with (
                        mock.patch.object(monitor, "ChatStorage", return_value=chat_storage),
                        mock.patch.object(monitor, "_startup_telegram"),
                        mock.patch.object(monitor, "_bootstrap_storages"),
                        mock.patch.object(monitor, "ENABLE_TELEGRAM", False),
                        mock.patch.object(monitor, "DRY_RUN", False),
                        mock.patch.object(monitor, "SILENT_INIT", False),
                        mock.patch.object(monitor, "load_last_summary_marker", return_value=""),
                        mock.patch.object(monitor, "_initial_report_marker", return_value=""),
                        mock.patch.object(monitor, "due_summary_report_hour", return_value=4),
                        mock.patch.object(
                            monitor,
                            "send_summary_report",
                            return_value=delivery_succeeded,
                        ),
                        mock.patch.object(monitor, "save_last_summary_marker") as save_mock,
                        mock.patch.object(
                            monitor,
                            "scan_chains_once",
                            side_effect=KeyboardInterrupt,
                        ),
                    ):
                        monitor.monitor_trending()

                    if delivery_succeeded:
                        save_mock.assert_called_once_with(4)
                    else:
                        save_mock.assert_not_called()

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
