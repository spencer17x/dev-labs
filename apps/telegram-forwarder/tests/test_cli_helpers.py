import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class CliHelpersTest(unittest.TestCase):
    def import_list_my_groups(self):
        sys.modules.pop("cli.list_my_groups", None)
        with patch.dict(os.environ, {}, clear=True):
            return importlib.import_module("cli.list_my_groups")

    def test_list_my_groups_import_does_not_require_credentials(self):
        module = self.import_list_my_groups()

        self.assertTrue(hasattr(module, "format_config_id"))

    def test_format_config_id_prefers_public_username(self):
        module = self.import_list_my_groups()
        entity = SimpleNamespace(id=1234567890, username="public_channel")

        self.assertEqual(
            module.format_config_id(entity, is_channel=True), "@public_channel"
        )

    def test_format_config_id_uses_minus_100_for_private_channels(self):
        module = self.import_list_my_groups()
        entity = SimpleNamespace(id=1234567890, username=None)

        self.assertEqual(
            module.format_config_id(entity, is_channel=True), -1001234567890
        )

    def test_format_config_id_keeps_regular_group_id(self):
        module = self.import_list_my_groups()
        entity = SimpleNamespace(id=12345, username=None)

        self.assertEqual(module.format_config_id(entity, is_channel=False), 12345)
