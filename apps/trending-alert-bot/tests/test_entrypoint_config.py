import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import main


APP_ROOT = Path(__file__).resolve().parents[1]


class EntrypointConfigTests(unittest.TestCase):
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

    def test_dry_run_uses_removed_temporary_data_dir(self):
        captured = {}
        fake_monitor = types.SimpleNamespace(
            normalize_clear_targets=lambda value: [],
            monitor_trending=lambda targets: captured.update(
                data_dir=os.environ["BOT_DATA_DIR"],
                dry_run=os.environ["BOT_DRY_RUN"],
            ),
        )
        args = types.SimpleNamespace(target="bsc", clear_storage="", dry_run=True)

        with (
            mock.patch.dict(os.environ, {"BSC_TELEGRAM_BOT_TOKEN": "123:test"}, clear=True),
            mock.patch.dict(sys.modules, {"monitor": fake_monitor}),
        ):
            run = getattr(main, "run", None)
            self.assertIsNotNone(run)
            run(args)

        self.assertEqual(captured["dry_run"], "1")
        self.assertFalse(os.path.exists(captured["data_dir"]))


if __name__ == "__main__":
    unittest.main()
