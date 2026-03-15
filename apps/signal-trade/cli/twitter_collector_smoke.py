#!/usr/bin/env python3
"""Smoke script for the polling-based Twitter collector."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors.twitter_client import (
    InMemoryTwitterPollingAdapter,
    TwitterCollector,
    TwitterTweet,
    TwitterUser,
    TwitterUserSnapshot,
)


async def main() -> None:
    adapter = InMemoryTwitterPollingAdapter()
    collector = TwitterCollector(adapter)

    monitored_user = TwitterUser(id='1', username='demo_user', display_name='Demo User')

    adapter.push_snapshot(
        TwitterUserSnapshot(
            user=monitored_user,
            tweets=[
                TwitterTweet(
                    id='t1',
                    user_id='1',
                    username='demo_user',
                    text='hello world',
                    created_at=int(time.time()) - 30,
                )
            ],
            following=[
                TwitterUser(id='100', username='alice', display_name='Alice'),
            ],
            followers=[],
        )
    )

    adapter.push_snapshot(
        TwitterUserSnapshot(
            user=monitored_user,
            tweets=[
                TwitterTweet(
                    id='t2',
                    user_id='1',
                    username='demo_user',
                    text='RT interesting thread',
                    created_at=int(time.time()) - 10,
                    is_retweet=True,
                    retweeted_tweet_id='origin_1',
                ),
                TwitterTweet(
                    id='t1',
                    user_id='1',
                    username='demo_user',
                    text='hello world',
                    created_at=int(time.time()) - 30,
                ),
            ],
            following=[
                TwitterUser(id='101', username='bob', display_name='Bob'),
            ],
            followers=[],
        )
    )

    await collector.poll_once('demo_user')
    events = await collector.poll_once('demo_user')
    for event in events:
        print(json.dumps(event.to_dict(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
