import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
