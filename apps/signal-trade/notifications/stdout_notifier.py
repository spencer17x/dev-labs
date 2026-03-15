"""Stdout notifier for local verification."""

from __future__ import annotations

import json

from models.notification import NotificationPayload


class StdoutNotifier:
    """Print matched notifications as JSON."""

    async def send(self, payload: NotificationPayload) -> None:
        print(
            json.dumps(
                {
                    'channel': 'stdout',
                    'strategy': payload.strategy.id,
                    'message': payload.message,
                    'event': payload.event.to_dict(),
                    'context': payload.context,
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
