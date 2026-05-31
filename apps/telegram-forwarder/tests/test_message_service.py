import unittest
from unittest.mock import AsyncMock, patch

from telethon.errors.rpcerrorlist import FloodWaitError

from services.message_service import MessageService
from tests.helpers import FakeMessage


class FakeClient:
    def __init__(self, forward_error=None):
        self.forward_error = forward_error
        self.forward_calls = []
        self.send_message_calls = []
        self.send_file_calls = []

    async def forward_messages(self, target, message, silent=False):
        self.forward_calls.append((target, message, silent))
        if self.forward_error:
            raise self.forward_error

    async def send_message(self, target, text, silent=False):
        self.send_message_calls.append((target, text, silent))

    async def send_file(self, target, file, caption=None, silent=False):
        self.send_file_calls.append((target, file, caption, silent))


class MessageServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_prefers_media_with_caption_over_text_only(self):
        client = FakeClient(forward_error=RuntimeError("cannot forward"))
        service = MessageService(client)
        message = FakeMessage(text="caption", media=object())

        count = await service.forward_message(message, ["@target"], silent=True)

        self.assertEqual(count, 1)
        self.assertEqual(len(client.send_file_calls), 1)
        self.assertEqual(client.send_file_calls[0][2], "caption")
        self.assertEqual(client.send_file_calls[0][3], True)
        self.assertEqual(client.send_message_calls, [])

    async def test_copy_mode_skips_native_forward(self):
        client = FakeClient()
        service = MessageService(client)
        message = FakeMessage(text="hello")

        count = await service.forward_message(
            message,
            ["@target"],
            forward_mode="copy",
        )

        self.assertEqual(count, 1)
        self.assertEqual(client.forward_calls, [])
        self.assertEqual(client.send_message_calls[0][1], "hello")

    async def test_unsupported_fallback_message_is_not_counted_successful(self):
        client = FakeClient(forward_error=RuntimeError("cannot forward"))
        service = MessageService(client)
        message = FakeMessage()

        count = await service.forward_message(message, ["@target"])

        self.assertEqual(count, 0)
        self.assertEqual(client.send_message_calls, [])
        self.assertEqual(client.send_file_calls, [])

    async def test_bounded_flood_wait_retries_once(self):
        class FloodThenSuccessClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.attempts = 0

            async def forward_messages(self, target, message, silent=False):
                self.attempts += 1
                self.forward_calls.append((target, message, silent))
                if self.attempts == 1:
                    raise FloodWaitError(request=None, capture=1)

        client = FloodThenSuccessClient()
        service = MessageService(client, flood_wait_max_seconds=1)

        with patch("services.message_service.asyncio.sleep", new=AsyncMock()) as sleep:
            count = await service.forward_message(
                FakeMessage(text="hello"), ["@target"]
            )

        self.assertEqual(count, 1)
        self.assertEqual(client.attempts, 2)
        sleep.assert_awaited_once_with(1)

    async def test_copy_mode_sends_album_items(self):
        client = FakeClient()
        service = MessageService(client)
        messages = [
            FakeMessage(text="caption", media=object(), message_id=1),
            FakeMessage(media=object(), message_id=2),
        ]

        count = await service.forward_message(
            messages,
            ["@target"],
            forward_mode="copy",
        )

        self.assertEqual(count, 1)
        self.assertEqual(client.forward_calls, [])
        self.assertEqual(len(client.send_file_calls), 2)
        self.assertEqual(client.send_file_calls[0][2], "caption")
