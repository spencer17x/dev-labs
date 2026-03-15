#!/usr/bin/env python3
"""Signal Trade application entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors.dexscreener_client import ALL_SUBSCRIPTIONS, DexScreenerClient
from collectors.twitter_client import TwitterCollector
from collectors.twitter_x_adapter import XGraphqlPollingAdapter
from core.app import SignalTradeApp, load_strategies
from models.signal_event import SignalEvent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Signal Trade runtime entrypoint',
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='logging verbosity',
    )
    parser.add_argument(
        '--rules',
        default='',
        help='path to strategy rules json',
    )
    parser.add_argument(
        '--config',
        default='',
        help='path to runtime config json',
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    dex_rest = subparsers.add_parser(
        'dex-rest',
        help='fetch DexScreener feed snapshots once over REST',
    )
    dex_rest.add_argument(
        '--subscriptions',
        nargs='*',
        default=list(ALL_SUBSCRIPTIONS),
        choices=list(ALL_SUBSCRIPTIONS),
        help='subscriptions to fetch',
    )
    dex_rest.add_argument(
        '--limit',
        type=int,
        default=None,
        help='max items per subscription',
    )

    dex_ws = subparsers.add_parser(
        'dex-ws',
        help='stream DexScreener feeds over WebSocket',
    )
    dex_ws.add_argument(
        '--subscriptions',
        nargs='*',
        default=list(ALL_SUBSCRIPTIONS),
        choices=list(ALL_SUBSCRIPTIONS),
        help='subscriptions to listen to',
    )
    dex_ws.add_argument(
        '--limit',
        type=int,
        default=None,
        help='max items processed from each payload',
    )

    twitter = subparsers.add_parser(
        'twitter',
        help='poll X/Twitter users through the web GraphQL adapter',
    )
    twitter.add_argument(
        'usernames',
        nargs='+',
        help='usernames to monitor',
    )

    return parser


async def run_dex_rest(
    subscriptions: Sequence[str],
    limit: int | None,
    app: SignalTradeApp | None,
) -> int:
    async with DexScreenerClient() as client:
        for subscription in subscriptions:
            events = await client.fetch_subscription_once(subscription, limit=limit)
            await _emit_events(events, app)
    return 0


async def run_dex_ws(
    subscriptions: Sequence[str],
    limit: int | None,
    app: SignalTradeApp | None,
) -> int:
    async def handle_event(event: SignalEvent) -> None:
        await _emit_event(event, app)

    async with DexScreenerClient() as client:
        await client.listen(subscriptions, handle_event, limit=limit)
    return 0


async def run_twitter(usernames: Sequence[str], app: SignalTradeApp | None) -> int:
    async with XGraphqlPollingAdapter() as adapter:
        collector = TwitterCollector(adapter)
        await collector.listen(usernames, lambda event: _emit_event(event, app))
    return 0


async def _emit_events(events: Iterable[SignalEvent], app: SignalTradeApp | None) -> None:
    for event in events:
        await _emit_event(event, app)


async def _emit_event(event: SignalEvent, app: SignalTradeApp | None) -> None:
    if app is None:
        print(_format_event(event), flush=True)
        return
    await app.process_event(event)


def _format_event(event: SignalEvent) -> str:
    return json.dumps(event.to_dict(), ensure_ascii=False, indent=2)


async def async_main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    app = _build_app(args.rules, args.config)

    if args.command == 'dex-rest':
        return await run_dex_rest(args.subscriptions, args.limit, app)
    if args.command == 'dex-ws':
        return await run_dex_ws(args.subscriptions, args.limit, app)
    if args.command == 'twitter':
        return await run_twitter(args.usernames, app)

    parser.error(f'unsupported command: {args.command}')
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(async_main(argv))
    except KeyboardInterrupt:
        return 130


def _build_app(rules_path: str, config_path: str) -> SignalTradeApp | None:
    normalized_rules = rules_path.strip()
    if not normalized_rules:
        return None

    runtime_config = _load_runtime_config(config_path)
    strategies = load_strategies(normalized_rules)
    return SignalTradeApp(
        strategies=strategies,
        webhook_url=str(runtime_config.get('webhookUrl', '')),
    )


def _load_runtime_config(config_path: str) -> dict:
    normalized = config_path.strip()
    if not normalized:
        return {}
    return json.loads(Path(normalized).read_text())


if __name__ == '__main__':
    raise SystemExit(main())
