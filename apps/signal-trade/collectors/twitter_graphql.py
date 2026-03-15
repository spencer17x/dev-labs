"""X/Twitter web GraphQL request and parsing helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from .twitter_client import TwitterTweet, TwitterUser

logger = logging.getLogger(__name__)

X_GRAPHQL_BASE_URL = 'https://api.x.com/graphql'

USER_BY_SCREEN_NAME_QUERY_ID = 'pLsOiyHJ1eFwPJlNmLp4Bg'
USER_TWEETS_QUERY_ID = 'Y59DTUMfcKmUAATiT2SlTw'
FOLLOWING_QUERY_ID = '5UpWO9XixjxJgrl-5fXuXA'
FOLLOWERS_QUERY_ID = 'VZ-VvbQB5nUidN73h6d2fg'

USER_BY_SCREEN_NAME_FEATURES = {
    'hidden_profile_subscriptions_enabled': True,
    'profile_label_improvements_pcf_label_in_post_enabled': True,
    'responsive_web_profile_redirect_enabled': False,
    'rweb_tipjar_consumption_enabled': False,
    'verified_phone_label_enabled': False,
    'subscriptions_verification_info_is_identity_verified_enabled': True,
    'subscriptions_verification_info_verified_since_enabled': True,
    'highlights_tweets_tab_ui_enabled': True,
    'responsive_web_twitter_article_notes_tab_enabled': True,
    'subscriptions_feature_can_gift_premium': True,
    'creator_subscriptions_tweet_preview_api_enabled': True,
    'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
    'responsive_web_graphql_timeline_navigation_enabled': True,
}

TIMELINE_FEATURES = {
    'rweb_video_screen_enabled': False,
    'profile_label_improvements_pcf_label_in_post_enabled': True,
    'responsive_web_profile_redirect_enabled': False,
    'rweb_tipjar_consumption_enabled': False,
    'verified_phone_label_enabled': False,
    'creator_subscriptions_tweet_preview_api_enabled': True,
    'responsive_web_graphql_timeline_navigation_enabled': True,
    'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
    'premium_content_api_read_enabled': False,
    'communities_web_enable_tweet_community_results_fetch': True,
    'c9s_tweet_anatomy_moderator_badge_enabled': True,
    'responsive_web_grok_analyze_button_fetch_trends_enabled': False,
    'responsive_web_grok_analyze_post_followups_enabled': False,
    'responsive_web_jetfuel_frame': True,
    'responsive_web_grok_share_attachment_enabled': True,
    'responsive_web_grok_annotations_enabled': True,
    'articles_preview_enabled': True,
    'responsive_web_edit_tweet_api_enabled': True,
    'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
    'view_counts_everywhere_api_enabled': True,
    'longform_notetweets_consumption_enabled': True,
    'responsive_web_twitter_article_tweet_consumption_enabled': True,
    'tweet_awards_web_tipping_enabled': False,
    'content_disclosure_indicator_enabled': True,
    'content_disclosure_ai_generated_indicator_enabled': True,
    'responsive_web_grok_show_grok_translated_post': False,
    'responsive_web_grok_analysis_button_from_backend': True,
    'post_ctas_fetch_enabled': True,
    'creator_subscriptions_quote_tweet_preview_enabled': False,
    'freedom_of_speech_not_reach_fetch_enabled': True,
    'standardized_nudges_misinfo': True,
    'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
    'rweb_video_timestamps_enabled': True,
    'longform_notetweets_rich_text_read_enabled': True,
    'longform_notetweets_inline_media_enabled': False,
    'responsive_web_grok_image_annotation_enabled': True,
    'responsive_web_grok_imagine_annotation_enabled': True,
    'responsive_web_grok_community_note_auto_translation_is_enabled': False,
    'responsive_web_enhance_cards_enabled': False,
}

USER_BY_SCREEN_NAME_FIELD_TOGGLES = {
    'withPayments': False,
    'withAuxiliaryUserLabels': True,
}

USER_TWEETS_FIELD_TOGGLES = {
    'withArticlePlainText': False,
}


@dataclass
class XGraphqlClient:
    """Thin client for X web GraphQL endpoints."""

    session: aiohttp.ClientSession
    proxy_url: Optional[str] = None

    async def get(
        self,
        query_id: str,
        operation_name: str,
        variables: Dict[str, Any],
        features: Dict[str, Any],
        field_toggles: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = {
            'variables': json.dumps(variables, separators=(',', ':')),
            'features': json.dumps(features, separators=(',', ':')),
        }
        if field_toggles:
            params['fieldToggles'] = json.dumps(field_toggles, separators=(',', ':'))
        url = f'{X_GRAPHQL_BASE_URL}/{query_id}/{operation_name}?{urlencode(params)}'
        async with self.session.get(url, proxy=self.proxy_url or None) as response:
            response.raise_for_status()
            return await response.json()


def build_user_by_screen_name_variables(screen_name: str) -> Dict[str, Any]:
    return {
        'screen_name': screen_name,
        'withGrokTranslatedBio': False,
    }


def build_user_tweets_variables(user_id: str, count: int) -> Dict[str, Any]:
    return {
        'userId': user_id,
        'count': count,
        'includePromotedContent': True,
        'withQuickPromoteEligibilityTweetFields': True,
        'withVoice': True,
    }


def build_user_relations_variables(user_id: str, count: int) -> Dict[str, Any]:
    return {
        'userId': user_id,
        'count': count,
        'includePromotedContent': False,
    }


def extract_first_user_result(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for node in walk_dict(payload):
        if not isinstance(node, dict):
            continue
        legacy = node.get('legacy')
        rest_id = node.get('rest_id')
        core = node.get('core')
        screen_name = None
        if isinstance(legacy, dict):
            screen_name = legacy.get('screen_name')
        if not screen_name and isinstance(core, dict):
            screen_name = core.get('screen_name')
        if isinstance(legacy, dict) and rest_id and screen_name:
            return node
    return None


def extract_users(payload: Dict[str, Any]) -> List[TwitterUser]:
    users: List[TwitterUser] = []
    seen_ids: set[str] = set()
    for node in walk_dict(payload):
        if not isinstance(node, dict):
            continue
        legacy = node.get('legacy')
        rest_id = node.get('rest_id')
        if not isinstance(legacy, dict) or not rest_id:
            continue
        core = node.get('core')
        screen_name = legacy.get('screen_name')
        if not screen_name and isinstance(core, dict):
            screen_name = core.get('screen_name')
        if not screen_name or rest_id in seen_ids:
            continue
        seen_ids.add(rest_id)
        users.append(to_twitter_user(node))
    return users


def extract_tweets(payload: Dict[str, Any], user: TwitterUser) -> List[TwitterTweet]:
    tweets: List[TwitterTweet] = []
    seen_ids: set[str] = set()
    for node in walk_dict(payload):
        if not isinstance(node, dict):
            continue
        legacy = node.get('legacy')
        if not isinstance(legacy, dict):
            continue

        tweet_id = legacy.get('id_str')
        if not tweet_id or tweet_id in seen_ids:
            continue

        core_user = extract_user_from_tweet_node(node)
        if core_user and core_user.username.lower() != user.username.lower():
            continue

        seen_ids.add(tweet_id)
        tweets.append(
            TwitterTweet(
                id=tweet_id,
                user_id=user.id,
                username=user.username,
                text=legacy.get('full_text') or legacy.get('text') or '',
                created_at=parse_twitter_timestamp(legacy.get('created_at')),
                is_retweet=bool(
                    legacy.get('retweeted_status_result')
                    or legacy.get('retweeted_status_id_str')
                ),
                retweeted_tweet_id=legacy.get('retweeted_status_id_str'),
                raw={
                    'rest_id': node.get('rest_id'),
                    'legacy': legacy,
                },
            )
        )
    return tweets


def extract_user_from_tweet_node(node: Dict[str, Any]) -> Optional[TwitterUser]:
    core = node.get('core')
    if not isinstance(core, dict):
        return None
    user_results = core.get('user_results')
    if not isinstance(user_results, dict):
        return None
    result = user_results.get('result')
    if not isinstance(result, dict):
        return None
    legacy = result.get('legacy')
    rest_id = result.get('rest_id')
    if not isinstance(legacy, dict) or not rest_id or not legacy.get('screen_name'):
        return None
    return to_twitter_user(result)


def to_twitter_user(user_result: Dict[str, Any]) -> TwitterUser:
    legacy = user_result.get('legacy') or {}
    core = user_result.get('core') or {}
    return TwitterUser(
        id=str(user_result.get('rest_id') or legacy.get('id_str') or ''),
        username=str(legacy.get('screen_name') or core.get('screen_name') or ''),
        display_name=legacy.get('name') or core.get('name'),
    )


def walk_dict(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_dict(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_dict(item)


def parse_twitter_timestamp(value: Any) -> int:
    if not value:
        return 0
    try:
        return int(parsedate_to_datetime(str(value)).timestamp())
    except Exception:
        logger.debug('Failed to parse twitter timestamp: %s', value)
        return 0
