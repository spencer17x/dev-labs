import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from bot_app import apply_runtime_env, load_runtime_config, validate_runtime_config


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

    def test_runtime_config_sets_narrative_defaults(self):
        with mock.patch.dict(os.environ, {"BSC_TELEGRAM_BOT_TOKEN": "123:test"}, clear=True):
            cfg = load_runtime_config("bsc")

        self.assertFalse(cfg.narrative_enabled)
        self.assertEqual(cfg.narrative_provider, "xai")
        self.assertEqual(cfg.narrative_cache_ttl_hours, 12)
        self.assertEqual(cfg.narrative_min_evidence, 3)
        self.assertEqual(cfg.narrative_timeout_seconds, 20)
        self.assertEqual(cfg.xai_api_key, "")

    def test_runtime_config_reads_narrative_env_values_after_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "BSC_TELEGRAM_BOT_TOKEN=123:test",
                        "NARRATIVE_ENABLED=true",
                        "NARRATIVE_PROVIDER=mock",
                        "NARRATIVE_CACHE_TTL_HOURS=6",
                        "NARRATIVE_MIN_EVIDENCE=2",
                        "NARRATIVE_TIMEOUT_SECONDS=9",
                        "XAI_API_KEY=abc",
                    ]
                ),
                encoding="utf-8",
            )

            with (
                mock.patch("bot_app._app_root", return_value=Path(tmp)),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                cfg = load_runtime_config("bsc")

        self.assertTrue(cfg.narrative_enabled)
        self.assertEqual(cfg.narrative_provider, "mock")
        self.assertEqual(cfg.narrative_cache_ttl_hours, 6)
        self.assertEqual(cfg.narrative_min_evidence, 2)
        self.assertEqual(cfg.narrative_timeout_seconds, 9)
        self.assertEqual(cfg.xai_api_key, "abc")

    def test_apply_runtime_env_passes_narrative_values_to_config_import_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    [
                        "BSC_TELEGRAM_BOT_TOKEN=123:test",
                        "NARRATIVE_ENABLED=true",
                        "NARRATIVE_PROVIDER=mock",
                        "NARRATIVE_CACHE_TTL_HOURS=6",
                        "NARRATIVE_MIN_EVIDENCE=2",
                        "NARRATIVE_TIMEOUT_SECONDS=9",
                        "XAI_API_KEY=abc",
                    ]
                ),
                encoding="utf-8",
            )

            with (
                mock.patch("bot_app._app_root", return_value=Path(tmp)),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                cfg = load_runtime_config("bsc")
                apply_runtime_env(cfg)

                self.assertEqual(os.environ["NARRATIVE_ENABLED"], "1")
                self.assertEqual(os.environ["NARRATIVE_PROVIDER"], "mock")
                self.assertEqual(os.environ["NARRATIVE_CACHE_TTL_HOURS"], "6")
                self.assertEqual(os.environ["NARRATIVE_MIN_EVIDENCE"], "2")
                self.assertEqual(os.environ["NARRATIVE_TIMEOUT_SECONDS"], "9")
                self.assertEqual(os.environ["XAI_API_KEY"], "abc")

    def test_validate_runtime_config_rejects_invalid_narrative_values(self):
        with mock.patch.dict(os.environ, {"BSC_TELEGRAM_BOT_TOKEN": "123:test"}, clear=True):
            cfg = load_runtime_config("bsc")

        invalid_cases = [
            ("narrative_provider", "openai", "narrative_provider"),
            ("narrative_cache_ttl_hours", 0, "narrative_cache_ttl_hours"),
            ("narrative_min_evidence", -1, "narrative_min_evidence"),
            ("narrative_timeout_seconds", 0, "narrative_timeout_seconds"),
        ]
        for field_name, value, message in invalid_cases:
            with self.subTest(field_name=field_name):
                invalid_cfg = replace(cfg)
                setattr(invalid_cfg, field_name, value)
                with self.assertRaisesRegex(ValueError, message):
                    validate_runtime_config(invalid_cfg)

    def test_multi_target_uses_multi_env_token_and_all_chains(self):
        with mock.patch.dict(os.environ, {"MULTI_TELEGRAM_BOT_TOKEN": "456:test"}, clear=True):
            cfg = load_runtime_config("multi")

        self.assertEqual(cfg.chain, "bsc")
        self.assertEqual(cfg.chains, ["bsc", "sol", "base", "eth", "robin"])
        self.assertEqual(cfg.telegram_bot_token, "456:test")
        self.assertTrue(cfg.data_dir.endswith("data/multi-bot"))
        self.assertEqual(
            cfg.chain_allowlists,
            {"bsc": {}, "sol": {}, "base": {}, "eth": {}, "robin": {}},
        )

    def test_robin_target_uses_robin_token_and_data_dir(self):
        with mock.patch.dict(
            os.environ,
            {"ROBIN_TELEGRAM_BOT_TOKEN": "789:test"},
            clear=True,
        ):
            cfg = load_runtime_config("robin")

        self.assertEqual(cfg.chain, "robin")
        self.assertEqual(cfg.chains, ["robin"])
        self.assertEqual(cfg.telegram_bot_token, "789:test")
        self.assertTrue(cfg.data_dir.endswith("data/robin-bot"))
        self.assertEqual(cfg.chain_allowlists, {"robin": {}})

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
