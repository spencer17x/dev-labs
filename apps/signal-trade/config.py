"""Shared configuration for Signal Trade."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv


BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / '.env'
DEFAULT_RUNTIME_CONFIG_PATH = BASE_DIR / 'config.json'

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


def _load_runtime_config() -> Dict[str, Any]:
    if not DEFAULT_RUNTIME_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(DEFAULT_RUNTIME_CONFIG_PATH.read_text())
    except Exception:
        return {}


RUNTIME_CONFIG = _load_runtime_config()


def _get_config_value(*keys: str, default: Any) -> Any:
    current: Any = RUNTIME_CONFIG
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _int_from_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, '').strip()
    if not raw_value:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _str_from_env(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()


# DexScreener
DEXSCREENER_POLL_INTERVAL_SEC = max(
    int(_get_config_value('dexscreener', 'pollIntervalSec', default=15)),
    1,
)

DEXSCREENER_REQUEST_TIMEOUT_SEC = max(
    int(_get_config_value('dexscreener', 'requestTimeoutSec', default=15)),
    1,
)

DEXSCREENER_WS_HEARTBEAT_SEC = max(
    int(_get_config_value('dexscreener', 'wsHeartbeatSec', default=30)),
    1,
)

DEXSCREENER_RECONNECT_DELAY_SEC = max(
    int(_get_config_value('dexscreener', 'reconnectDelaySec', default=3)),
    1,
)

# Twitter runtime
TWITTER_POLL_INTERVAL_SEC = max(
    int(_get_config_value('twitter', 'pollIntervalSec', default=30)),
    1,
)

TWITTER_REQUEST_TIMEOUT_SEC = max(
    int(_get_config_value('twitter', 'requestTimeoutSec', default=20)),
    1,
)

TWITTER_DEFAULT_TWEET_COUNT = max(
    int(_get_config_value('twitter', 'defaultTweetCount', default=20)),
    1,
)

TWITTER_DEFAULT_RELATION_COUNT = max(
    int(_get_config_value('twitter', 'defaultRelationCount', default=50)),
    1,
)

# Twitter/X auth
TWITTER_BEARER_TOKEN = _str_from_env(
    'TWITTER_BEARER_TOKEN',
    'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5I8xn5QHj0XuCw'
    '%3D1Zv7ttfk8qXzN8kzY5xq9uxZ3sJY8N6t4QeqA',
)
TWITTER_CT0 = _str_from_env('TWITTER_CT0')
TWITTER_AUTH_TOKEN = _str_from_env('TWITTER_AUTH_TOKEN')
TWITTER_PROXY_URL = _str_from_env('TWITTER_PROXY_URL')

# XXYY protected endpoints
XXYY_AUTHORIZATION = _str_from_env('XXYY_AUTHORIZATION')
XXYY_INFO_TOKEN = _str_from_env('XXYY_INFO_TOKEN')
XXYY_COOKIE = _str_from_env('XXYY_COOKIE')
