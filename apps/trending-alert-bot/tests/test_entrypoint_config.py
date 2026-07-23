import contextlib
import io
import os
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import main
import check_config
from bot_app import BotRuntimeConfig

APP_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULE_NAMES = (
    "monitor",
    "monitor_flow",
    "telegram_bot",
    "storage",
    "chat_storage",
    "db_storage",
    "narrative_service",
    "narrative_storage",
    "narrative_provider",
    "notifier",
    "config",
)


def remove_runtime_modules():
    for module_name in RUNTIME_MODULE_NAMES:
        sys.modules.pop(module_name, None)


class EntrypointConfigTests(unittest.TestCase):
    def test_clear_all_notification_data_is_a_standalone_command(self):
        args = main.parse_args(["--clear-all-notification-data"])

        with (
            mock.patch.object(main, "_run_clear_all_notification_data") as clear_mock,
            mock.patch.object(main, "load_runtime_config") as config_mock,
        ):
            main.run(args)

        clear_mock.assert_called_once_with()
        config_mock.assert_not_called()

    def test_clear_all_notification_data_rejects_runtime_options(self):
        invalid_argv = [
            [],
            ["multi", "--clear-all-notification-data"],
            ["--clear-all-notification-data", "--clear-storage", "all"],
            ["--clear-all-notification-data", "--dry-run"],
        ]
        with contextlib.redirect_stderr(io.StringIO()):
            for argv in invalid_argv:
                with self.subTest(argv=argv), self.assertRaises(SystemExit):
                    main.parse_args(argv)

    def test_main_py_is_the_only_python_entrypoint(self):
        self.assertTrue((APP_ROOT / "main.py").exists())
        self.assertFalse((APP_ROOT / "run.py").exists())

    def test_pm2_configs_run_main_py_directly(self):
        for config_name in [
            "ecosystem.bots.config.js",
            "ecosystem.multi.config.js",
            "ecosystem.all.config.js",
        ]:
            with self.subTest(config_name=config_name):
                config_path = APP_ROOT / config_name
                self.assertTrue(config_path.exists())
                content = config_path.read_text(encoding="utf-8")
                self.assertIn("script: 'main.py'", content)
                self.assertNotIn("script: 'run.py'", content)
                self.assertNotIn("args: 'run ", content)

    def test_robin_target_is_exposed_by_cli_pm2_and_env_example(self):
        with mock.patch.object(sys, "argv", ["main.py", "robin"]):
            self.assertEqual(main.parse_args().target, "robin")
        with mock.patch.object(sys, "argv", ["check_config.py", "robin"]):
            self.assertEqual(check_config.parse_args().target, "robin")

        for config_name in [
            "ecosystem.bots.config.js",
            "ecosystem.all.config.js",
        ]:
            content = (APP_ROOT / config_name).read_text(encoding="utf-8")
            self.assertIn("name: 'trending-alert-robin'", content)
            self.assertIn("args: 'robin'", content)

        env_example = (APP_ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("ROBIN_TELEGRAM_BOT_TOKEN=", env_example)

    def test_dry_run_reloads_cached_runtime_into_removed_temporary_data_dir(self):
        class CachedRuntimeDidNotExit(RuntimeError):
            pass

        runtime_cfg = BotRuntimeConfig(
            chain="bsc",
            chains=["bsc"],
            telegram_bot_token="123:test",
            data_dir="",
            notification_types=["trending", "anomaly"],
            chain_allowlists={"bsc": {}},
        )
        args = types.SimpleNamespace(target="bsc", clear_storage="", dry_run=True)
        observations = []
        opened_databases = []
        saved_runtime_modules = {
            name: sys.modules[name]
            for name in RUNTIME_MODULE_NAMES
            if name in sys.modules
        }

        with tempfile.TemporaryDirectory() as production_data_dir:
            production_db = Path(production_data_dir) / "trending_alert_bot.sqlite"
            runtime_cfg.data_dir = production_data_dir
            production_env = {
                "BOT_CHECK_INTERVAL": "15",
                "BOT_CHAINS": '["bsc"]',
                "BOT_CHAIN": "bsc",
                "BOT_NOTIFY_COOLDOWN_HOURS": "24",
                "BOT_MULTIPLIER_CONFIRMATIONS": "1",
                "BOT_NOTIFICATION_TYPES": '["trending", "anomaly"]',
                "BOT_CHAIN_ALLOWLIST_JSON": '{"bsc": {}}',
                "BOT_DATA_DIR": production_data_dir,
                "BOT_TELEGRAM_TOKEN": "123:test",
                "BOT_DRY_RUN": "0",
            }

            def fake_fetch_trending(*args, **kwargs):
                runtime_monitor = sys.modules["monitor"]
                runtime_config = sys.modules["config"]
                observations.append(
                    {
                        "dry_run": runtime_monitor.DRY_RUN,
                        "data_dir": runtime_config.STORAGE_DIR,
                    }
                )
                return {"data": []}

            real_sqlite_connect = sqlite3.connect

            def recording_connect(database, *args, **kwargs):
                opened_databases.append(os.fspath(database))
                return real_sqlite_connect(database, *args, **kwargs)

            forced_cached_runtime_exit = False
            try:
                with mock.patch.dict(os.environ, production_env, clear=True):
                    remove_runtime_modules()
                    import api

                    with mock.patch.object(
                        api, "fetch_trending", side_effect=fake_fetch_trending
                    ):
                        import chat_storage
                        import monitor

                        production_chats = chat_storage.ChatStorage()
                        production_chats.add_chat(
                            111,
                            {"type": "group", "title": "Production"},
                        )
                        monitor.ENABLE_TELEGRAM = False
                        monitor.SILENT_INIT = False
                        monitor.due_summary_report_hour = lambda marker: -1
                        production_db_before = production_db.read_bytes()

                        with (
                            mock.patch.object(
                                main, "load_runtime_config", return_value=runtime_cfg
                            ),
                            mock.patch.object(
                                sqlite3, "connect", side_effect=recording_connect
                            ),
                            mock.patch.object(
                                time,
                                "sleep",
                                side_effect=CachedRuntimeDidNotExit,
                            ),
                        ):
                            try:
                                main.run(args)
                            except CachedRuntimeDidNotExit:
                                forced_cached_runtime_exit = True

                self.assertEqual(len(observations), 1)
                self.assertTrue(observations[0]["dry_run"])
                self.assertNotEqual(observations[0]["data_dir"], production_data_dir)
                self.assertFalse(os.path.exists(observations[0]["data_dir"]))
                self.assertNotIn(str(production_db), opened_databases)
                self.assertEqual(production_db.read_bytes(), production_db_before)
                self.assertFalse(forced_cached_runtime_exit)
            finally:
                remove_runtime_modules()
                sys.modules.update(saved_runtime_modules)

    def test_normal_run_resets_prior_dry_run_flag(self):
        args = types.SimpleNamespace(target="bsc", clear_storage="", dry_run=False)
        captured = {}

        with (
            mock.patch.dict(os.environ, {"BOT_DRY_RUN": "1"}),
            mock.patch.object(
                main, "load_runtime_config", return_value=mock.sentinel.runtime_cfg
            ),
            mock.patch.object(main, "validate_runtime_config"),
            mock.patch.object(main, "apply_runtime_env"),
            mock.patch.object(
                main,
                "_run_monitor",
                side_effect=lambda clear_storage: captured.update(
                    dry_run=os.environ["BOT_DRY_RUN"]
                ),
            ),
        ):
            main.run(args)

        self.assertEqual(captured["dry_run"], "0")


if __name__ == "__main__":
    unittest.main()
