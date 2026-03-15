"""Polling-based Twitter collector.

This module focuses on the stable part of the problem:
- polling snapshots
- diffing snapshots
- normalizing to SignalEvent

The upstream fetcher is injected as an adapter because X/Twitter data access
is highly unstable and environment-specific.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Sequence

from config import TWITTER_POLL_INTERVAL_SEC
from models.signal_event import SignalAuthor, SignalEvent

logger = logging.getLogger(__name__)

TwitterEventSubtype = str


@dataclass
class TwitterUser:
    """Minimal user identity for polling and diffing."""

    id: str
    username: str
    display_name: Optional[str] = None


@dataclass
class TwitterTweet:
    """Minimal tweet representation for event normalization."""

    id: str
    user_id: str
    username: str
    text: str
    created_at: int
    is_retweet: bool = False
    retweeted_tweet_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TwitterUserSnapshot:
    """One polling snapshot for a single monitored account."""

    user: TwitterUser
    tweets: List[TwitterTweet] = field(default_factory=list)
    following: List[TwitterUser] = field(default_factory=list)
    followers: List[TwitterUser] = field(default_factory=list)
    fetched_at: int = field(default_factory=lambda: int(time.time()))


class TwitterPollingAdapter(Protocol):
    """Adapter interface used by TwitterCollector."""

    async def fetch_user_snapshot(self, username: str) -> TwitterUserSnapshot:
        """Return the latest snapshot for a monitored user."""


@dataclass
class TwitterCollectorOptions:
    """Runtime settings for TwitterCollector."""

    poll_interval_sec: int = TWITTER_POLL_INTERVAL_SEC
    emit_tweet_created: bool = True
    emit_tweet_retweeted: bool = True
    emit_user_followed: bool = True
    emit_user_unfollowed: bool = True
    emit_follower_added: bool = False
    emit_follower_removed: bool = False


class TwitterCollector:
    """Polling collector that emits tweet/follow diff events."""

    def __init__(
        self,
        adapter: TwitterPollingAdapter,
        options: Optional[TwitterCollectorOptions] = None,
    ) -> None:
        self._adapter = adapter
        self._options = options or TwitterCollectorOptions()
        self._running = False
        self._snapshots: Dict[str, TwitterUserSnapshot] = {}

    async def listen(
        self,
        usernames: Sequence[str],
        on_event: Callable[[SignalEvent], Awaitable[None] | None],
    ) -> None:
        """Continuously poll all usernames and emit normalized events."""

        if not usernames:
            raise ValueError('usernames cannot be empty')

        self._running = True
        normalized_usernames = _dedupe_usernames(usernames)
        logger.info('Twitter collector polling users: %s', ', '.join(normalized_usernames))

        while self._running:
            for username in normalized_usernames:
                try:
                    events = await self.poll_once(username)
                    for event in events:
                        await _maybe_await(on_event(event))
                except Exception as exc:
                    logger.warning('Twitter poll failed for %s: %s', username, exc)

            await asyncio.sleep(max(self._options.poll_interval_sec, 1))

    def stop(self) -> None:
        """Stop the polling loop."""

        self._running = False

    async def poll_once(self, username: str) -> List[SignalEvent]:
        """Poll one user once and return all newly discovered events."""

        current = await self._adapter.fetch_user_snapshot(username)
        previous = self._snapshots.get(current.user.username.lower())
        self._snapshots[current.user.username.lower()] = current

        if previous is None:
            logger.info('Twitter collector initialized snapshot for %s', current.user.username)
            return []

        events: List[SignalEvent] = []
        events.extend(self._diff_tweets(previous, current))
        events.extend(self._diff_following(previous, current))
        events.extend(self._diff_followers(previous, current))
        return events

    def _diff_tweets(
        self,
        previous: TwitterUserSnapshot,
        current: TwitterUserSnapshot,
    ) -> List[SignalEvent]:
        previous_ids = {tweet.id for tweet in previous.tweets}
        new_tweets = [tweet for tweet in current.tweets if tweet.id not in previous_ids]
        events: List[SignalEvent] = []

        for tweet in sorted(new_tweets, key=lambda item: item.created_at):
            if tweet.is_retweet and self._options.emit_tweet_retweeted:
                events.append(_build_tweet_event('tweet_retweeted', current.user, tweet))
            elif not tweet.is_retweet and self._options.emit_tweet_created:
                events.append(_build_tweet_event('tweet_created', current.user, tweet))

        return events

    def _diff_following(
        self,
        previous: TwitterUserSnapshot,
        current: TwitterUserSnapshot,
    ) -> List[SignalEvent]:
        previous_map = {user.id: user for user in previous.following}
        current_map = {user.id: user for user in current.following}
        events: List[SignalEvent] = []

        if self._options.emit_user_followed:
            for user_id, user in current_map.items():
                if user_id not in previous_map:
                    events.append(_build_user_relation_event('user_followed', current.user, user))

        if self._options.emit_user_unfollowed:
            for user_id, user in previous_map.items():
                if user_id not in current_map:
                    events.append(_build_user_relation_event('user_unfollowed', current.user, user))

        return events

    def _diff_followers(
        self,
        previous: TwitterUserSnapshot,
        current: TwitterUserSnapshot,
    ) -> List[SignalEvent]:
        previous_map = {user.id: user for user in previous.followers}
        current_map = {user.id: user for user in current.followers}
        events: List[SignalEvent] = []

        if self._options.emit_follower_added:
            for user_id, user in current_map.items():
                if user_id not in previous_map:
                    events.append(_build_user_relation_event('follower_added', current.user, user))

        if self._options.emit_follower_removed:
            for user_id, user in previous_map.items():
                if user_id not in current_map:
                    events.append(_build_user_relation_event('follower_removed', current.user, user))

        return events


class InMemoryTwitterPollingAdapter:
    """Simple adapter for smoke tests.

    Feed snapshots with `push_snapshot`; each poll consumes one snapshot.
    """

    def __init__(self) -> None:
        self._queues: Dict[str, List[TwitterUserSnapshot]] = {}

    def push_snapshot(self, snapshot: TwitterUserSnapshot) -> None:
        username = snapshot.user.username.lower()
        self._queues.setdefault(username, []).append(snapshot)

    async def fetch_user_snapshot(self, username: str) -> TwitterUserSnapshot:
        key = username.lower()
        queue = self._queues.get(key, [])
        if not queue:
            raise RuntimeError(f'no queued snapshot for {username}')
        return queue.pop(0)


def _build_tweet_event(
    subtype: TwitterEventSubtype,
    user: TwitterUser,
    tweet: TwitterTweet,
) -> SignalEvent:
    return SignalEvent(
        id=f'twitter:{subtype}:{tweet.id}',
        source='twitter',
        subtype=subtype,
        timestamp=tweet.created_at,
        author=SignalAuthor(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
        ),
        text=tweet.text,
        raw=tweet.raw or {
            'tweetId': tweet.id,
            'retweetedTweetId': tweet.retweeted_tweet_id,
        },
        metadata={
            'user': {
                'id': user.id,
                'username': user.username,
                'displayName': user.display_name,
            },
            'tweet': {
                'id': tweet.id,
                'isRetweet': tweet.is_retweet,
                'retweetedTweetId': tweet.retweeted_tweet_id,
            },
        },
    )


def _build_user_relation_event(
    subtype: TwitterEventSubtype,
    user: TwitterUser,
    target_user: TwitterUser,
) -> SignalEvent:
    now_ts = int(time.time())
    return SignalEvent(
        id=f'twitter:{subtype}:{user.id}:{target_user.id}:{now_ts}',
        source='twitter',
        subtype=subtype,
        timestamp=now_ts,
        author=SignalAuthor(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
        ),
        raw={
            'user': {
                'id': user.id,
                'username': user.username,
                'displayName': user.display_name,
            },
            'targetUser': {
                'id': target_user.id,
                'username': target_user.username,
                'displayName': target_user.display_name,
            },
        },
        metadata={
            'user': {
                'id': user.id,
                'username': user.username,
                'displayName': user.display_name,
            },
            'targetUser': {
                'id': target_user.id,
                'username': target_user.username,
                'displayName': target_user.display_name,
            },
        },
    )


async def _maybe_await(result: Awaitable[None] | None) -> None:
    if inspect.isawaitable(result):
        await result


def _dedupe_usernames(usernames: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    results: List[str] = []
    for username in usernames:
        normalized = username.strip().lstrip('@').lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    return results
