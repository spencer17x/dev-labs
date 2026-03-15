"""X/Twitter GraphQL adapter for the polling collector."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

import aiohttp

from config import (
    TWITTER_AUTH_TOKEN,
    TWITTER_BEARER_TOKEN,
    TWITTER_CT0,
    TWITTER_DEFAULT_RELATION_COUNT,
    TWITTER_DEFAULT_TWEET_COUNT,
    TWITTER_PROXY_URL,
    TWITTER_REQUEST_TIMEOUT_SEC,
)
from .twitter_client import TwitterPollingAdapter, TwitterTweet, TwitterUser, TwitterUserSnapshot
from .twitter_graphql import (
    FOLLOWERS_QUERY_ID,
    FOLLOWING_QUERY_ID,
    TIMELINE_FEATURES,
    USER_BY_SCREEN_NAME_FIELD_TOGGLES,
    USER_BY_SCREEN_NAME_FEATURES,
    USER_BY_SCREEN_NAME_QUERY_ID,
    USER_TWEETS_FIELD_TOGGLES,
    USER_TWEETS_QUERY_ID,
    XGraphqlClient,
    build_user_by_screen_name_variables,
    build_user_relations_variables,
    build_user_tweets_variables,
    extract_first_user_result,
    extract_tweets,
    extract_users,
    to_twitter_user,
)

logger = logging.getLogger(__name__)


@dataclass
class XGraphqlAdapterOptions:
    """Runtime options for the X GraphQL adapter."""

    ct0: str = TWITTER_CT0
    auth_token: str = TWITTER_AUTH_TOKEN
    bearer_token: str = TWITTER_BEARER_TOKEN
    proxy_url: str = TWITTER_PROXY_URL
    request_timeout_sec: int = TWITTER_REQUEST_TIMEOUT_SEC
    tweet_count: int = TWITTER_DEFAULT_TWEET_COUNT
    relation_count: int = TWITTER_DEFAULT_RELATION_COUNT


class XGraphqlPollingAdapter(TwitterPollingAdapter):
    """Fetch user snapshots from X web GraphQL endpoints."""

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        options: Optional[XGraphqlAdapterOptions] = None,
    ) -> None:
        self._options = options or XGraphqlAdapterOptions()
        self._session = session
        self._owns_session = session is None
        self._user_cache: Dict[str, TwitterUser] = {}
        self._graphql_client: Optional[XGraphqlClient] = None

    async def __aenter__(self) -> 'XGraphqlPollingAdapter':
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def fetch_user_snapshot(self, username: str) -> TwitterUserSnapshot:
        await self._ensure_session()

        user = await self._resolve_user(username)
        tweets_payload, following_payload, followers_payload = await asyncio.gather(
            self._fetch_user_tweets_payload(user.id),
            self._fetch_following_payload(user.id),
            self._fetch_followers_payload(user.id),
        )

        return TwitterUserSnapshot(
            user=user,
            tweets=extract_tweets(tweets_payload, user),
            following=extract_users(following_payload),
            followers=extract_users(followers_payload),
        )

    async def _resolve_user(self, username: str) -> TwitterUser:
        normalized = username.strip().lstrip('@').lower()
        if normalized in self._user_cache:
            return self._user_cache[normalized]

        payload = await self._graphql_get(
            USER_BY_SCREEN_NAME_QUERY_ID,
            'UserByScreenName',
            variables=build_user_by_screen_name_variables(normalized),
            features=USER_BY_SCREEN_NAME_FEATURES,
            field_toggles=USER_BY_SCREEN_NAME_FIELD_TOGGLES,
        )

        user_result = extract_first_user_result(payload)
        if not user_result:
            raise RuntimeError(f'failed to resolve user by screen name: {normalized}')

        user = to_twitter_user(user_result)
        self._user_cache[normalized] = user
        return user

    async def _fetch_user_tweets_payload(self, user_id: str) -> Dict[str, Any]:
        return await self._graphql_get(
            USER_TWEETS_QUERY_ID,
            'UserTweets',
            variables=build_user_tweets_variables(user_id, self._options.tweet_count),
            features=TIMELINE_FEATURES,
            field_toggles=USER_TWEETS_FIELD_TOGGLES,
        )

    async def _fetch_following_payload(self, user_id: str) -> Dict[str, Any]:
        return await self._graphql_get(
            FOLLOWING_QUERY_ID,
            'Following',
            variables=build_user_relations_variables(user_id, self._options.relation_count),
            features=TIMELINE_FEATURES,
        )

    async def _fetch_followers_payload(self, user_id: str) -> Dict[str, Any]:
        return await self._graphql_get(
            FOLLOWERS_QUERY_ID,
            'Followers',
            variables=build_user_relations_variables(user_id, self._options.relation_count),
            features=TIMELINE_FEATURES,
        )

    async def _graphql_get(
        self,
        query_id: str,
        operation_name: str,
        variables: Dict[str, Any],
        features: Dict[str, Any],
        field_toggles: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, object]:
        assert self._graphql_client is not None
        return await self._graphql_client.get(
            query_id,
            operation_name,
            variables,
            features,
            field_toggles=field_toggles,
        )

    async def _ensure_session(self) -> None:
        if self._session and not self._session.closed:
            return

        if not self._options.ct0 or not self._options.auth_token:
            raise RuntimeError(
                'missing TWITTER_CT0 or TWITTER_AUTH_TOKEN; see .env.example'
            )

        timeout = aiohttp.ClientTimeout(total=self._options.request_timeout_sec)
        headers = {
            'authorization': self._options.bearer_token,
            'x-csrf-token': self._options.ct0,
            'x-twitter-active-user': 'yes',
            'x-twitter-client-language': 'en',
            'referer': 'https://x.com/',
            'user-agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
        }
        cookies = {
            'ct0': self._options.ct0,
            'auth_token': self._options.auth_token,
        }
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers,
            cookies=cookies,
            trust_env=True,
        )
        self._graphql_client = XGraphqlClient(
            session=self._session,
            proxy_url=self._options.proxy_url or None,
        )
        if self._options.proxy_url:
            logger.info('X GraphQL adapter using proxy %s', self._options.proxy_url)
