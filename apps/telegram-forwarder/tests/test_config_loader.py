import json
import os
import re
import tempfile
import unittest
from unittest.mock import patch

from config.loader import ConfigLoader
from config.validator import ConfigValidator


class ConfigLoaderTest(unittest.TestCase):
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

    def test_simplified_forwards_all_messages(self):
        config = self.load_config(
            {
                "forwards": [
                    {
                        "from": "@source_channel",
                        "to": "@target_channel",
                    }
                ]
            }
        )

        self.assertEqual(len(config.groups), 1)
        group = config.groups[0]
        self.assertEqual(group.id, "forward_1")
        self.assertEqual(group.name, "@source_channel -> @target_channel")
        self.assertEqual(group.source_id, "@source_channel")
        self.assertEqual(group.rules[0].target_ids, ["@target_channel"])
        self.assertEqual(group.rules[0].filter_mode, "all")

    def test_simplified_forwards_keywords_become_include_rule(self):
        config = self.load_config(
            {
                "forwards": [
                    {
                        "from": "@news",
                        "to": ["@btc"],
                        "keywords": ["BTC", "Bitcoin"],
                    }
                ]
            }
        )

        rule = config.groups[0].rules[0]
        self.assertEqual(rule.filter_mode, "include")
        self.assertEqual(
            rule.filter_rules,
            [
                {
                    "type": "keyword",
                    "config": {
                        "words": ["BTC", "Bitcoin"],
                        "match_case": False,
                        "match_mode": "any",
                    },
                }
            ],
        )

    def test_existing_targets_accept_single_string(self):
        config = self.load_config(
            {
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [{"targets": "@target"}],
                    }
                ]
            }
        )

        self.assertEqual(config.groups[0].rules[0].target_ids, ["@target"])

    def test_disabled_group_can_omit_source_and_rules(self):
        config = self.load_config(
            {
                "groups": [
                    {"id": "paused", "name": "Paused", "enabled": False},
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [{"targets": ["@target"]}],
                    },
                ]
            }
        )

        self.assertFalse(config.groups[0].enabled)
        ConfigValidator.validate(config)

    def test_environment_session_path_overrides_json_session_name(self):
        config = self.load_config(
            {
                "session_name": "json_session",
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [{"targets": ["@target"]}],
                    }
                ],
            },
            env={"TELEGRAM_SESSION_PATH": "/tmp/env_session"},
        )

        self.assertEqual(config.SESSION_NAME, "/tmp/env_session")

    def test_enabled_malformed_group_fails_fast(self):
        with self.assertRaisesRegex(ValueError, "缺少 source"):
            self.load_config(
                {
                    "groups": [
                        {
                            "id": "broken",
                            "name": "Broken",
                            "rules": [{"targets": ["@target"]}],
                        }
                    ]
                }
            )

    def test_get_group_config_uses_username_fallback(self):
        config = self.load_config(
            {
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source_channel",
                        "rules": [{"targets": ["@target"]}],
                    }
                ]
            }
        )

        self.assertIs(
            config.get_group_config(1234567890, "source_channel"), config.groups[0]
        )

    def test_invalid_filter_values_are_rejected(self):
        config = self.load_config(
            {
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [
                            {
                                "targets": ["@target"],
                                "filters": {
                                    "mode": "include",
                                    "rules": [
                                        {
                                            "type": "keyword",
                                            "config": {
                                                "words": [],
                                                "match_mode": "all",
                                            },
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ]
            }
        )

        with self.assertRaisesRegex(ValueError, "words"):
            ConfigValidator.validate(config)

    def test_regex_rules_are_precompiled_during_validation(self):
        config = self.load_config(
            {
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [
                            {
                                "targets": ["@target"],
                                "filters": {
                                    "mode": "include",
                                    "rules": [
                                        {
                                            "type": "regex",
                                            "config": {
                                                "pattern": "BTC",
                                                "flags": "i",
                                            },
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ]
            }
        )

        ConfigValidator.validate(config)
        compiled = (
            config.groups[0].rules[0].filter_rules[0]["config"]["_compiled_pattern"]
        )
        self.assertIsInstance(compiled, re.Pattern)

    def test_invalid_regex_is_rejected_by_validation(self):
        config = self.load_config(
            {
                "groups": [
                    {
                        "id": "main",
                        "name": "Main",
                        "source": "@source",
                        "rules": [
                            {
                                "targets": ["@target"],
                                "filters": {
                                    "mode": "include",
                                    "rules": [
                                        {
                                            "type": "regex",
                                            "config": {"pattern": "["},
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ]
            }
        )

        with self.assertRaisesRegex(ValueError, "正则"):
            ConfigValidator.validate(config)
