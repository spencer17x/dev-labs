import unittest
from types import SimpleNamespace

from core.forwarder import MessageForwarder
from tests.helpers import FakeMessage


class FakeMessageService:
    def __init__(self):
        self.calls = []

    async def forward_message(self, message, targets, **options):
        self.calls.append((message, list(targets), options))
        return len(targets)


class ForwarderTest(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_targets_are_suppressed_across_matching_rules(self):
        service = FakeMessageService()
        forwarder = MessageForwarder(service)
        group = SimpleNamespace(
            id="main",
            rules=[
                SimpleNamespace(
                    enabled=True,
                    filter_mode="all",
                    filter_rules=[],
                    target_ids=["@same", "@unique"],
                    forward_mode="forward",
                    silent=False,
                    dedupe=True,
                ),
                SimpleNamespace(
                    enabled=True,
                    filter_mode="all",
                    filter_rules=[],
                    target_ids=["@same"],
                    forward_mode="forward",
                    silent=False,
                    dedupe=True,
                ),
            ],
        )

        count = await forwarder.process_message(FakeMessage(text="hello"), group)

        self.assertEqual(count, 2)
        self.assertEqual(service.calls[0][1], ["@same", "@unique"])
        self.assertEqual(service.calls[1][1], [])

    async def test_album_uses_first_message_for_filtering(self):
        service = FakeMessageService()
        forwarder = MessageForwarder(service)
        group = SimpleNamespace(
            id="main",
            rules=[
                SimpleNamespace(
                    enabled=True,
                    filter_mode="include",
                    filter_rules=[
                        {
                            "type": "keyword",
                            "config": {"words": ["BTC"]},
                        }
                    ],
                    target_ids=["@target"],
                    forward_mode="forward",
                    silent=False,
                    dedupe=True,
                )
            ],
        )
        messages = [
            FakeMessage(text="BTC chart", message_id=1),
            FakeMessage(text=None, media=object(), message_id=2),
        ]

        count = await forwarder.process_message(messages, group)

        self.assertEqual(count, 1)
        self.assertIs(service.calls[0][0], messages)
