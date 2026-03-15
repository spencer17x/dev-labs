"""Fetch Twitter community metrics from X GraphQL."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import aiohttp

from config import (
    TWITTER_AUTH_TOKEN,
    TWITTER_BEARER_TOKEN,
    TWITTER_CT0,
    TWITTER_PROXY_URL,
    TWITTER_REQUEST_TIMEOUT_SEC,
)
from collectors.twitter_graphql import (
    USER_BY_SCREEN_NAME_FIELD_TOGGLES,
    USER_BY_SCREEN_NAME_FEATURES,
    USER_BY_SCREEN_NAME_QUERY_ID,
    XGraphqlClient,
    build_user_by_screen_name_variables,
    extract_first_user_result,
)

logger = logging.getLogger(__name__)


@dataclass
class TwitterCommunityClientOptions:
    """Runtime options for user profile lookups."""

    ct0: str = TWITTER_CT0
    auth_token: str = TWITTER_AUTH_TOKEN
    bearer_token: str = TWITTER_BEARER_TOKEN
    proxy_url: str = TWITTER_PROXY_URL
    request_timeout_sec: int = TWITTER_REQUEST_TIMEOUT_SEC


class TwitterCommunityClient:
    """Resolve Twitter profile metadata for strategy enrichment."""

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        options: Optional[TwitterCommunityClientOptions] = None,
    ) -> None:
        self._options = options or TwitterCommunityClientOptions()
        self._session = session
        self._owns_session = session is None
        self._graphql_client: Optional[XGraphqlClient] = None
        self._cache: Dict[str, Dict[str, Optional[int] | Optional[str]]] = {}

    async def __aenter__(self) -> 'TwitterCommunityClient':
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        self._graphql_client = None

    async def fetch_profile_metrics(self, username: str) -> Dict[str, Optional[int] | Optional[str]]:
        normalized = username.strip().lstrip('@').lower()
        if not normalized:
            return {
                'community_count': None,
                'followers_count': None,
                'friends_count': None,
                'statuses_count': None,
            }
        if normalized in self._cache:
            return dict(self._cache[normalized])

        created_session = self._session is None or self._session.closed
        try:
            await self._ensure_session()
            assert self._graphql_client is not None

            payload = await self._graphql_client.get(
                USER_BY_SCREEN_NAME_QUERY_ID,
                'UserByScreenName',
                variables=build_user_by_screen_name_variables(normalized),
                features=USER_BY_SCREEN_NAME_FEATURES,
                field_toggles=USER_BY_SCREEN_NAME_FIELD_TOGGLES,
            )
            result = extract_first_user_result(payload)
            legacy = result.get('legacy') if isinstance(result, dict) else {}
            metrics = {
                'community_count': _safe_int((legacy or {}).get('followers_count')),
                'followers_count': _safe_int((legacy or {}).get('followers_count')),
                'friends_count': _safe_int((legacy or {}).get('friends_count')),
                'statuses_count': _safe_int((legacy or {}).get('statuses_count')),
            }
            self._cache[normalized] = metrics
            return dict(metrics)
        finally:
            if created_session and self._owns_session:
                await self.close()

    async def _ensure_session(self) -> None:
        if self._session and not self._session.closed:
            return

        if not self._options.ct0 or not self._options.auth_token:
            raise RuntimeError('missing TWITTER_CT0 or TWITTER_AUTH_TOKEN; see .env.example')

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
            logger.info('Twitter community client using proxy %s', self._options.proxy_url)


def _safe_int(value: object) -> Optional[int]:
    try:
        if value in (None, ''):
            return None
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
