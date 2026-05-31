import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot_app import load_runtime_config


class BotAppConfigTests(unittest.TestCase):
    def test_single_chain_target_uses_env_token_convention(self):
        with mock.patch.dict(os.environ, {"BSC_TELEGRAM_BOT_TOKEN": "123:test"}, clear=True):
            cfg = load_runtime_config("bsc")

        self.assertEqual(cfg.chain, "bsc")
        self.assertEqual(cfg.chains, ["bsc"])
        self.assertEqual(cfg.telegram_bot_token, "123:test")
        self.assertTrue(cfg.data_dir.endswith("data/bsc-bot"))
        self.assertEqual(cfg.check_interval, 15)
        self.assertEqual(cfg.notify_cooldown_hours, 24)
        self.assertEqual(cfg.multiplier_confirmations, 2)
        self.assertEqual(cfg.notification_types, ["trending", "anomaly"])
        self.assertEqual(cfg.chain_allowlists, {"bsc": {}})

    def test_multi_target_uses_multi_env_token_and_all_chains(self):
        with mock.patch.dict(os.environ, {"MULTI_TELEGRAM_BOT_TOKEN": "456:test"}, clear=True):
            cfg = load_runtime_config("multi")

        self.assertEqual(cfg.chain, "bsc")
        self.assertEqual(cfg.chains, ["bsc", "sol", "base", "eth"])
        self.assertEqual(cfg.telegram_bot_token, "456:test")
        self.assertTrue(cfg.data_dir.endswith("data/multi-bot"))
        self.assertEqual(
            cfg.chain_allowlists,
            {"bsc": {}, "sol": {}, "base": {}, "eth": {}},
        )

    def test_dotenv_file_supplies_token_without_overriding_existing_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "SOL_TELEGRAM_BOT_TOKEN=from-dotenv\nBSC_TELEGRAM_BOT_TOKEN=from-dotenv\n",
                encoding="utf-8",
            )

            with (
                mock.patch("bot_app._app_root", return_value=Path(tmp)),
                mock.patch.dict(os.environ, {"BSC_TELEGRAM_BOT_TOKEN": "from-env"}, clear=True),
            ):
                sol_cfg = load_runtime_config("sol")
                bsc_cfg = load_runtime_config("bsc")

        self.assertEqual(sol_cfg.telegram_bot_token, "from-dotenv")
        self.assertEqual(bsc_cfg.telegram_bot_token, "from-env")

    def test_missing_target_token_names_required_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch("bot_app._app_root", return_value=Path(tmp)),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                with self.assertRaisesRegex(ValueError, "BSC_TELEGRAM_BOT_TOKEN"):
                    load_runtime_config("bsc")

    def test_unsupported_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported target"):
            load_runtime_config("polygon")


if __name__ == "__main__":
    unittest.main()
