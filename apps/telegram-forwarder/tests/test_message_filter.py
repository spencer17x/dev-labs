import re
import unittest
from types import SimpleNamespace

from filters.message_filter import MessageFilter
from tests.helpers import FakeMessage


class MessageFilterTest(unittest.TestCase):
    def setUp(self):
        self.filter = MessageFilter()

    def make_rule(self, filter_mode, filter_rules):
        return SimpleNamespace(filter_mode=filter_mode, filter_rules=filter_rules)

    def test_empty_keyword_all_rule_does_not_match(self):
        rule = self.make_rule(
            "include",
            [
                {
                    "type": "keyword",
                    "config": {"words": [], "match_mode": "all"},
                }
            ],
        )

        self.assertFalse(self.filter.should_forward(FakeMessage(text="anything"), rule))

    def test_empty_media_all_rule_does_not_match(self):
        rule = self.make_rule(
            "include",
            [
                {
                    "type": "media",
                    "config": {"types": [], "match_mode": "all"},
                }
            ],
        )

        self.assertFalse(self.filter.should_forward(FakeMessage(text="anything"), rule))

    def test_user_conditional_forward_all_ignores_conditions(self):
        rule = self.make_rule(
            "include",
            [
                {
                    "type": "user_conditional",
                    "config": {
                        "users": [123],
                        "forward_all": True,
                        "conditions": [
                            {
                                "type": "keyword",
                                "config": {"words": ["missing"]},
                            }
                        ],
                    },
                }
            ],
        )

        self.assertTrue(
            self.filter.should_forward(FakeMessage(text="hello", sender_id=123), rule)
        )

    def test_user_conditional_without_conditions_does_not_match_by_default(self):
        rule = self.make_rule(
            "include",
            [
                {
                    "type": "user_conditional",
                    "config": {
                        "users": [123],
                        "forward_all": False,
                        "conditions": [],
                    },
                }
            ],
        )

        self.assertFalse(
            self.filter.should_forward(FakeMessage(text="hello", sender_id=123), rule)
        )

    def test_string_numeric_user_id_matches_sender_id(self):
        rule = self.make_rule(
            "include",
            [
                {
                    "type": "user",
                    "config": {"users": ["123"]},
                }
            ],
        )

        self.assertTrue(
            self.filter.should_forward(FakeMessage(text="hello", sender_id=123), rule)
        )

    def test_regex_uses_precompiled_pattern(self):
        rule = self.make_rule(
            "include",
            [
                {
                    "type": "regex",
                    "config": {
                        "pattern": "SHOULD_NOT_BE_USED",
                        "_compiled_pattern": re.compile("btc", re.IGNORECASE),
                    },
                }
            ],
        )

        self.assertTrue(self.filter.should_forward(FakeMessage(text="BTC"), rule))

    def test_length_rule_matches_text_bounds(self):
        rule = self.make_rule(
            "include",
            [{"type": "length", "config": {"min": 3, "max": 5}}],
        )

        self.assertTrue(self.filter.should_forward(FakeMessage(text="hello"), rule))
        self.assertFalse(self.filter.should_forward(FakeMessage(text="hi"), rule))

    def test_link_rule_matches_urls(self):
        rule = self.make_rule("include", [{"type": "link", "config": {}}])

        self.assertTrue(
            self.filter.should_forward(
                FakeMessage(text="see https://example.com"), rule
            )
        )
        self.assertFalse(self.filter.should_forward(FakeMessage(text="no link"), rule))

    def test_reply_bot_and_channel_post_rules(self):
        reply_rule = self.make_rule("include", [{"type": "reply", "config": {}}])
        bot_rule = self.make_rule("include", [{"type": "bot", "config": {}}])
        post_rule = self.make_rule("include", [{"type": "channel_post", "config": {}}])

        self.assertTrue(
            self.filter.should_forward(
                FakeMessage(text="reply", is_reply=True), reply_rule
            )
        )
        self.assertTrue(
            self.filter.should_forward(
                FakeMessage(text="bot", sender_username="bot", sender_is_bot=True),
                bot_rule,
            )
        )
        self.assertTrue(
            self.filter.should_forward(FakeMessage(text="post", post=True), post_rule)
        )
