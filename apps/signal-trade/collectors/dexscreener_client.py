"""DexScreener WebSocket and REST collector."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Sequence
from urllib.parse import urlencode

import aiohttp

from config import (
    DEXSCREENER_RECONNECT_DELAY_SEC,
    DEXSCREENER_REQUEST_TIMEOUT_SEC,
    DEXSCREENER_WS_HEARTBEAT_SEC,
)
from models.signal_event import SignalAuthor, SignalEvent, SignalToken

logger = logging.getLogger(__name__)

DEXSCREENER_API_BASE = 'https://api.dexscreener.com'
DEXSCREENER_WS_BASE = 'wss://api.dexscreener.com'

DexScreenerSubscription = Literal[
    'token_profiles_latest',
    'community_takeovers_latest',
    'ads_latest',
    'token_boosts_latest',
    'token_boosts_top',
]

SUBSCRIPTION_ENDPOINTS: Dict[DexScreenerSubscription, str] = {
    'token_profiles_latest': f'{DEXSCREENER_WS_BASE}/token-profiles/latest/v1',
    'community_takeovers_latest': f'{DEXSCREENER_WS_BASE}/community-takeovers/latest/v1',
    'ads_latest': f'{DEXSCREENER_WS_BASE}/ads/latest/v1',
    'token_boosts_latest': f'{DEXSCREENER_WS_BASE}/token-boosts/latest/v1',
    'token_boosts_top': f'{DEXSCREENER_WS_BASE}/token-boosts/top/v1',
}

ALL_SUBSCRIPTIONS: List[DexScreenerSubscription] = list(SUBSCRIPTION_ENDPOINTS.keys())


@dataclass
class DexScreenerRuntimeOptions:
    """Runtime settings for the collector."""

    reconnect_delay_sec: float = float(DEXSCREENER_RECONNECT_DELAY_SEC)
    request_timeout_sec: float = float(DEXSCREENER_REQUEST_TIMEOUT_SEC)
    heartbeat_sec: float = float(DEXSCREENER_WS_HEARTBEAT_SEC)
    enrich_events: bool = True
    proxy_url: Optional[str] = None
    event_limit: Optional[int] = None


class DexScreenerClient:
    """Unified DexScreener listener for WebSocket streams and REST enrichment."""

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        options: Optional[DexScreenerRuntimeOptions] = None,
    ) -> None:
        self._session = session
        self._owns_session = session is None
        self._options = options or DexScreenerRuntimeOptions()
        self._running = False
        self._proxy_url = self._options.proxy_url or _resolve_proxy_url()

    async def __aenter__(self) -> 'DexScreenerClient':
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP session when owned by this client."""

        self._running = False
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def listen(
        self,
        subscriptions: Sequence[DexScreenerSubscription],
        on_event: Callable[[SignalEvent], Awaitable[None] | None],
        limit: Optional[int] = None,
    ) -> None:
        """Listen to multiple DexScreener feeds and dispatch normalized events."""

        if not subscriptions:
            raise ValueError('subscriptions cannot be empty')

        await self._ensure_session()
        self._running = True
        tasks = [
            asyncio.create_task(self._consume_subscription(name, on_event, limit=limit))
            for name in subscriptions
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            self._running = False
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def listen_all(
        self,
        on_event: Callable[[SignalEvent], Awaitable[None] | None],
        limit: Optional[int] = None,
    ) -> None:
        """Listen to all documented DexScreener WebSocket feeds."""

        await self.listen(ALL_SUBSCRIPTIONS, on_event, limit=limit)

    async def get_orders(self, chain_id: str, token_address: str) -> List[Dict[str, Any]]:
        """Fetch paid order state for a token."""

        data = await self._request_json(f'/orders/v1/{chain_id}/{token_address}')
        return data if isinstance(data, list) else []

    async def get_token_pairs(
        self,
        chain_id: str,
        token_addresses: Sequence[str],
    ) -> List[Dict[str, Any]]:
        """Fetch market pairs for one or more token addresses."""

        if not token_addresses:
            return []

        joined_addresses = ','.join(token_addresses)
        data = await self._request_json(f'/tokens/v1/{chain_id}/{joined_addresses}')
        return data if isinstance(data, list) else []

    async def get_latest_token_profiles(self) -> List[Dict[str, Any]]:
        """Fetch the latest token profile items."""

        data = await self._request_json('/token-profiles/latest/v1')
        return data if isinstance(data, list) else []

    async def get_latest_community_takeovers(self) -> List[Dict[str, Any]]:
        """Fetch the latest community takeover items."""

        data = await self._request_json('/community-takeovers/latest/v1')
        return data if isinstance(data, list) else []

    async def get_latest_ads(self) -> List[Dict[str, Any]]:
        """Fetch the latest ads items."""

        data = await self._request_json('/ads/latest/v1')
        return data if isinstance(data, list) else []

    async def get_latest_token_boosts(self) -> List[Dict[str, Any]]:
        """Fetch the latest token boosts items."""

        data = await self._request_json('/token-boosts/latest/v1')
        return data if isinstance(data, list) else []

    async def get_top_token_boosts(self) -> List[Dict[str, Any]]:
        """Fetch the top token boosts items."""

        data = await self._request_json('/token-boosts/top/v1')
        return data if isinstance(data, list) else []

    async def enrich_event(self, event: SignalEvent) -> SignalEvent:
        """Attach orders and pair data when the event carries token identity."""

        if not self._options.enrich_events:
            return event

        chain_id = event.chain or event.raw.get('chainId')
        token_address = event.token.address
        if not chain_id or not token_address:
            return event

        orders, pairs = await asyncio.gather(
            self.get_orders(chain_id, token_address),
            self.get_token_pairs(chain_id, [token_address]),
        )

        metadata = dict(event.metadata)
        metadata['orders'] = orders
        metadata['pairs'] = pairs

        metrics = dict(event.metrics)
        if pairs:
            first_pair = pairs[0]
            liquidity_usd = _safe_float(_deep_get(first_pair, 'liquidity', 'usd'))
            volume_24h = _safe_float(_deep_get(first_pair, 'volume', 'h24'))
            price_usd = _safe_float(first_pair.get('priceUsd'))
            if liquidity_usd is not None:
                metrics['liquidityUsd'] = liquidity_usd
            if volume_24h is not None:
                metrics['volume24hUsd'] = volume_24h
            if price_usd is not None:
                metrics['priceUsd'] = price_usd

        event.metadata = metadata
        event.metrics = metrics
        return event

    async def _consume_subscription(
        self,
        subscription: DexScreenerSubscription,
        on_event: Callable[[SignalEvent], Awaitable[None] | None],
        limit: Optional[int] = None,
    ) -> None:
        endpoint = _build_subscription_endpoint(
            subscription,
            limit=limit or self._options.event_limit,
        )
        assert self._session is not None

        while self._running:
            try:
                async with self._session.ws_connect(
                    endpoint,
                    heartbeat=self._options.heartbeat_sec,
                    proxy=self._proxy_url,
                ) as websocket:
                    logger.info('Connected to DexScreener feed %s', subscription)
                    async for message in websocket:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_payload(
                                subscription,
                                message.data,
                                on_event,
                                limit=limit,
                            )
                        elif message.type == aiohttp.WSMsgType.ERROR:
                            raise websocket.exception() or RuntimeError(
                                f'WebSocket error on {subscription}'
                            )
                        elif message.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    'DexScreener feed %s disconnected: %s',
                    subscription,
                    exc,
                )
                await asyncio.sleep(self._options.reconnect_delay_sec)

    async def _handle_ws_payload(
        self,
        subscription: DexScreenerSubscription,
        payload: str,
        on_event: Callable[[SignalEvent], Awaitable[None] | None],
        limit: Optional[int] = None,
    ) -> None:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            logger.debug('Ignored non-JSON payload from %s', subscription)
            return

        items = _limit_items(_extract_items(decoded), limit or self._options.event_limit)
        for item in items:
            event = self._build_event(subscription, item)
            if self._options.enrich_events:
                event = await self.enrich_event(event)
            await _maybe_await(on_event(event))

    def _build_event(
        self,
        subscription: DexScreenerSubscription,
        item: Dict[str, Any],
    ) -> SignalEvent:
        chain_id = _coalesce(item.get('chainId'), item.get('chain'), item.get('network'))
        token_address = _coalesce(
            item.get('tokenAddress'),
            item.get('address'),
            _deep_get(item, 'token', 'address'),
        )
        token = SignalToken(
            symbol=_coalesce(item.get('symbol'), _deep_get(item, 'token', 'symbol')),
            name=_coalesce(item.get('tokenName'), item.get('name'), _deep_get(item, 'token', 'name')),
            address=token_address,
        )
        author_name = _coalesce(
            item.get('author'),
            item.get('projectOwner'),
            item.get('project'),
        )
        author = SignalAuthor(display_name=author_name) if author_name else None
        timestamp = _normalize_timestamp(
            _coalesce(
                item.get('paymentTimestamp'),
                item.get('timestamp'),
                item.get('createdAt'),
                item.get('updatedAt'),
            )
        )
        metrics = _extract_metrics(item)
        event_id = _build_event_id(subscription, chain_id, token_address, item)

        return SignalEvent(
            id=event_id,
            source='dexscreener',
            subtype=subscription,
            timestamp=timestamp,
            chain=chain_id,
            token=token,
            author=author,
            text=_coalesce(item.get('description'), item.get('title')),
            metrics=metrics,
            raw=item,
            metadata={
                'subscription': subscription,
                'dexscreener': {
                    'url': item.get('url'),
                    'icon': item.get('icon'),
                    'header': item.get('header'),
                    'description': item.get('description'),
                    'links': _extract_links(item.get('links')),
                },
            },
        )

    async def fetch_subscription_once(
        self,
        subscription: DexScreenerSubscription,
        limit: Optional[int] = None,
    ) -> List[SignalEvent]:
        """Fetch a subscription once over REST and normalize the result."""

        fetchers = {
            'token_profiles_latest': self.get_latest_token_profiles,
            'community_takeovers_latest': self.get_latest_community_takeovers,
            'ads_latest': self.get_latest_ads,
            'token_boosts_latest': self.get_latest_token_boosts,
            'token_boosts_top': self.get_top_token_boosts,
        }
        items = _limit_items(
            await fetchers[subscription](),
            limit or self._options.event_limit,
        )
        events: List[SignalEvent] = []
        for item in items:
            event = self._build_event(subscription, item)
            if self._options.enrich_events:
                event = await self.enrich_event(event)
            events.append(event)
        return events

    async def _request_json(self, path: str) -> Any:
        await self._ensure_session()
        assert self._session is not None

        async with self._session.get(path, proxy=self._proxy_url) as response:
            response.raise_for_status()
            return await response.json()

    async def _ensure_session(self) -> None:
        if self._session and not self._session.closed:
            return

        timeout = aiohttp.ClientTimeout(total=self._options.request_timeout_sec)
        self._session = aiohttp.ClientSession(
            base_url=DEXSCREENER_API_BASE,
            timeout=timeout,
            headers={'Accept': 'application/json'},
            trust_env=True,
        )
        if self._proxy_url:
            logger.info('DexScreener client using proxy %s', self._proxy_url)


async def _maybe_await(result: Awaitable[None] | None) -> None:
    if inspect.isawaitable(result):
        await result


def _extract_items(decoded: Any) -> List[Dict[str, Any]]:
    if isinstance(decoded, dict):
        payload = decoded.get('data', decoded)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []

    if isinstance(decoded, list):
        return [item for item in decoded if isinstance(item, dict)]

    return []


def _limit_items(
    items: List[Dict[str, Any]],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    if limit is None:
        return items
    if limit <= 0:
        return []
    return items[:limit]


def _build_subscription_endpoint(
    subscription: DexScreenerSubscription,
    limit: Optional[int] = None,
) -> str:
    endpoint = SUBSCRIPTION_ENDPOINTS[subscription]
    if limit is None:
        return endpoint
    return f'{endpoint}?{urlencode({"limit": max(limit, 0)})}'


def _extract_metrics(item: Dict[str, Any]) -> Dict[str, float]:
    metric_fields = {
        'amount': item.get('amount'),
        'totalAmount': item.get('totalAmount'),
        'activeBoosts': _deep_get(item, 'boosts', 'active'),
    }
    metrics: Dict[str, float] = {}
    for key, value in metric_fields.items():
        converted = _safe_float(value)
        if converted is not None:
            metrics[key] = converted
    return metrics


def _extract_links(raw_links: Any) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    if not isinstance(raw_links, list):
        return links
    for item in raw_links:
        if not isinstance(item, dict):
            continue
        url = _coalesce(item.get('url'))
        if not url:
            continue
        links.append(
            {
                'type': str(item.get('type') or '').strip(),
                'label': str(item.get('label') or '').strip(),
                'url': str(url).strip(),
            }
        )
    return links


def _build_event_id(
    subscription: DexScreenerSubscription,
    chain_id: Optional[str],
    token_address: Optional[str],
    item: Dict[str, Any],
) -> str:
    stable_bits = [
        subscription,
        chain_id or '',
        token_address or '',
        str(item.get('amount', '')),
        str(item.get('totalAmount', '')),
        str(item.get('paymentTimestamp', '')),
    ]
    base = ':'.join(stable_bits).strip(':')
    if base:
        return base

    digest = hashlib.sha1(
        json.dumps(item, sort_keys=True, default=str).encode('utf-8')
    ).hexdigest()
    return f'{subscription}:{digest}'


def _normalize_timestamp(value: Any) -> int:
    if value is None:
        return int(time.time())

    if isinstance(value, (int, float)):
        numeric = int(value)
        return numeric if numeric < 10_000_000_000 else numeric // 1000

    if isinstance(value, str) and value.isdigit():
        numeric = int(value)
        return numeric if numeric < 10_000_000_000 else numeric // 1000

    return int(time.time())


def _coalesce(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deep_get(payload: Dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _resolve_proxy_url() -> Optional[str]:
    for key in ('https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY'):
        value = os.environ.get(key)
        if value:
            return value
    return None
