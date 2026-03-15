#!/usr/bin/env python3
"""Manual smoke runner for the DexScreener collector."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors.dexscreener_client import ALL_SUBSCRIPTIONS, DexScreenerClient
from models.signal_event import SignalEvent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='DexScreener smoke runner')
    parser.add_argument(
        '--mode',
        choices=['rest', 'ws'],
        default='rest',
        help='rest prints one-shot API output, ws prints live feed events',
    )
    parser.add_argument(
        '--subscriptions',
        nargs='*',
        default=list(ALL_SUBSCRIPTIONS),
        choices=list(ALL_SUBSCRIPTIONS),
        help='subscriptions to use in ws mode',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='max items to request/process per feed update',
    )
    return parser


async def run_rest(limit: int | None) -> None:
    async with DexScreenerClient() as client:
        for subscription in ALL_SUBSCRIPTIONS:
            events = await client.fetch_subscription_once(subscription, limit=limit)
            for event in events:
                print(_format_event(event), flush=True)


async def run_ws(subscriptions: Sequence[str], limit: int | None) -> None:
    async def handle_event(event) -> None:
        print(_format_event(event), flush=True)

    async with DexScreenerClient() as client:
        await client.listen(subscriptions, handle_event, limit=limit)


def _format_event(event: SignalEvent) -> str:
    payload: Dict[str, Any] = {
        'chain': event.chain,
        'address': event.token.address,
    }
    return json.dumps(payload, ensure_ascii=False)


async def async_main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )

    if args.mode == 'rest':
        await run_rest(args.limit)
        return

    await run_ws(args.subscriptions, args.limit)


if __name__ == '__main__':
    asyncio.run(async_main())
