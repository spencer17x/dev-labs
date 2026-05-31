import json
import os
import tempfile
import unittest
from unittest.mock import patch

from config.loader import ConfigLoader


class BotOptionsTest(unittest.TestCase):
    def load_config(self, data, env=None):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        env_values = {
            "TELEGRAM_API_ID": "12345",
            "TELEGRAM_API_HASH": "hash",
        }
        env_values.update(env or {})
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with patch.dict(os.environ, env_values, clear=True):
            return ConfigLoader(path)

    def test_operational_flags_have_safe_defaults(self):
        config = self.load_config(
            {
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [{"targets": ["@target"]}],
                    }
                ]
            }
        )

        self.assertFalse(config.SEND_STARTUP_NOTIFICATION)
        self.assertFalse(config.STARTUP_NOTIFICATION_DETAILS)
        self.assertFalse(config.LOG_MESSAGE_CONTENT)
        self.assertEqual(config.FLOOD_WAIT_MAX_SECONDS, 0)

    def test_operational_flags_can_be_enabled_from_env(self):
        config = self.load_config(
            {
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [{"targets": ["@target"]}],
                    }
                ]
            },
            env={
                "SEND_STARTUP_NOTIFICATION": "true",
                "STARTUP_NOTIFICATION_DETAILS": "1",
                "LOG_MESSAGE_CONTENT": "yes",
                "FLOOD_WAIT_MAX_SECONDS": "3",
            },
        )

        self.assertTrue(config.SEND_STARTUP_NOTIFICATION)
        self.assertTrue(config.STARTUP_NOTIFICATION_DETAILS)
        self.assertTrue(config.LOG_MESSAGE_CONTENT)
        self.assertEqual(config.FLOOD_WAIT_MAX_SECONDS, 3)
