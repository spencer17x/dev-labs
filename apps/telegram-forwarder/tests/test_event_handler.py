import unittest
from types import SimpleNamespace

from core.event_handler import EventHandler


class FakeConfig:
    def __init__(self):
        self.calls = []
        self.group = object()
        self.all_source_ids = ["@source_channel"]

    def get_group_config(self, source_id, username=None):
        self.calls.append((source_id, username))
        if source_id == 1234567890 and username == "source_channel":
            return self.group
        return None


class FakeForwarder:
    def __init__(self):
        self.processed = []

    async def process_message(self, message, group_config):
        self.processed.append((message, group_config))
        return 1


class FakeEvent:
    def __init__(self, grouped_id=None):
        self.message = SimpleNamespace(id=1, text="hello", grouped_id=grouped_id)

    async def get_chat(self):
        return SimpleNamespace(id=1234567890, title="Source", username="source_channel")

    async def get_sender(self):
        return SimpleNamespace(id=10, username="alice", first_name="Alice")


class EventHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_handle_new_message_uses_chat_username_fallback(self):
        config = FakeConfig()
        forwarder = FakeForwarder()
        handler = EventHandler(config, forwarder)

        await handler.handle_new_message(FakeEvent())

        self.assertEqual(config.calls, [(1234567890, "source_channel")])
        self.assertEqual(forwarder.processed[0][1], config.group)

    async def test_grouped_new_message_waits_for_album_event(self):
        config = FakeConfig()
        forwarder = FakeForwarder()
        handler = EventHandler(config, forwarder)

        await handler.handle_new_message(FakeEvent(grouped_id=555))

        self.assertEqual(config.calls, [])
        self.assertEqual(forwarder.processed, [])

    async def test_handle_album_forwards_message_list(self):
        class FakeAlbumEvent(FakeEvent):
            def __init__(self):
                super().__init__()
                self.messages = [
                    SimpleNamespace(id=1, text="hello", grouped_id=555),
                    SimpleNamespace(id=2, text=None, grouped_id=555),
                ]

        config = FakeConfig()
        forwarder = FakeForwarder()
        handler = EventHandler(config, forwarder)

        await handler.handle_album(FakeAlbumEvent())

        self.assertEqual(config.calls, [(1234567890, "source_channel")])
        self.assertEqual(forwarder.processed[0][0][0].id, 1)
        self.assertEqual(forwarder.processed[0][1], config.group)
