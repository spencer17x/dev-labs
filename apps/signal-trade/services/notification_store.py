"""Local notification persistence for the Signal Trade dashboard."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from models.notification import NotificationPayload


DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent / 'data' / 'notifications.json'


class NotificationStore:
    """Persist a rolling notification feed for the Next.js dashboard."""

    def __init__(self, path: Path | None = None, max_items: int = 250) -> None:
        self._path = path or DEFAULT_STORE_PATH
        self._max_items = max(max_items, 1)

    def append(self, payload: NotificationPayload) -> None:
        records = self._load()
        records.insert(0, self._serialize(payload))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(records[: self._max_items], ensure_ascii=False, indent=2)
        )

    def _load(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text())
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _serialize(self, payload: NotificationPayload) -> Dict[str, Any]:
        context = payload.context if isinstance(payload.context, dict) else {}
        xxyy = context.get('xxyy', {}) if isinstance(context.get('xxyy'), dict) else {}
        twitter = (
            context.get('twitter', {}) if isinstance(context.get('twitter'), dict) else {}
        )
        dexscreener = (
            context.get('dexscreener', {})
            if isinstance(context.get('dexscreener'), dict)
            else {}
        )

        return {
            'id': payload.event.id,
            'notifiedAt': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()),
            'strategyId': payload.strategy.id,
            'channels': payload.channels,
            'message': payload.message,
            'event': payload.event.to_dict(),
            'context': context,
            'summary': {
                'paid': bool(
                    dexscreener.get('paid', payload.event.subtype == 'token_profiles_latest')
                ),
                'marketCap': _safe_number(xxyy.get('market_cap')),
                'holderCount': _safe_number(xxyy.get('holder_count')),
                'communityCount': _safe_number(twitter.get('community_count')),
                'followersCount': _safe_number(twitter.get('followers_count')),
                'twitterUsername': _safe_string(twitter.get('username')),
                'dexscreenerUrl': _safe_string(dexscreener.get('url')),
                'telegramUrl': _safe_string(xxyy.get('project_telegram_url')),
            },
        }


def _safe_number(value: Any) -> float | None:
    try:
        if value in (None, ''):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
