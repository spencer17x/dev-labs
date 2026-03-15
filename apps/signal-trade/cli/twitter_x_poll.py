#!/usr/bin/env python3
"""Run the real X GraphQL polling adapter and print normalized events."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors.twitter_client import TwitterCollector
from collectors.twitter_x_adapter import XGraphqlPollingAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Poll X/Twitter users and print events')
    parser.add_argument('usernames', nargs='+', help='usernames to monitor')
    return parser


async def handle_event(event) -> None:
    print(json.dumps(event.to_dict(), ensure_ascii=False, indent=2), flush=True)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    args = build_parser().parse_args()

    async with XGraphqlPollingAdapter() as adapter:
        collector = TwitterCollector(adapter)
        await collector.listen(args.usernames, handle_event)


if __name__ == '__main__':
    asyncio.run(main())
