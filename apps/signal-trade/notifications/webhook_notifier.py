"""Webhook notifier for Signal Trade."""

from __future__ import annotations

import json

import aiohttp

from models.notification import NotificationPayload


class WebhookNotifier:
    """POST matched notifications to a configured webhook endpoint."""

    def __init__(self, webhook_url: str = '') -> None:
        self._webhook_url = webhook_url.strip()

    async def send(self, payload: NotificationPayload) -> None:
        if not self._webhook_url:
            return

        body = {
            'strategy': payload.strategy.id,
            'message': payload.message,
            'event': payload.event.to_dict(),
            'context': payload.context,
            'metadata': payload.metadata,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._webhook_url,
                data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            ) as response:
                response.raise_for_status()
