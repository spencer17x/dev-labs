"""Build strategy context from normalized events."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from models.signal_event import SignalEvent
from services.twitter_community_client import TwitterCommunityClient
from services.xxyy_client import XXYYClient, build_xxyy_context

logger = logging.getLogger(__name__)


@dataclass
class EnricherOptions:
    """Runtime flags for context enrichment."""

    xxyy_enabled: bool = True
    twitter_enabled: bool = True


class SignalContextEnricher:
    """Enrich a SignalEvent into the strategy context object."""

    def __init__(
        self,
        xxyy_client: Optional[XXYYClient] = None,
        twitter_client: Optional[TwitterCommunityClient] = None,
        options: Optional[EnricherOptions] = None,
    ) -> None:
        self._xxyy_client = xxyy_client or XXYYClient()
        self._twitter_client = twitter_client or TwitterCommunityClient()
        self._options = options or EnricherOptions()

    async def enrich(self, event: SignalEvent) -> Dict[str, Any]:
        context = {
            'token': {
                'chain': event.chain,
                'address': event.token.address,
                'symbol': event.token.symbol,
                'name': event.token.name,
            },
            'dexscreener': {
                'source': event.subtype,
                'paid': event.subtype == 'token_profiles_latest',
                'timestamp': event.timestamp,
                'url': _deep_get(event.metadata, 'dexscreener', 'url'),
                'icon': _deep_get(event.metadata, 'dexscreener', 'icon'),
                'header': _deep_get(event.metadata, 'dexscreener', 'header'),
                'description': _deep_get(event.metadata, 'dexscreener', 'description'),
                'links': _deep_get(event.metadata, 'dexscreener', 'links') or [],
            },
            'xxyy': {},
            'twitter': {},
        }

        if self._options.xxyy_enabled and event.source == 'dexscreener' and event.token.address:
            xxyy_snapshot = {}
            pair_info_payload = {}
            stat_info_payload = {}
            kol_payload = {}
            follow_payload = {}
            pair_address = event.token.address
            try:
                pair_info_payload = self._xxyy_client.fetch_pair_info(
                    pair_address=event.token.address,
                    chain=event.chain or 'sol',
                    base_only=0,
                )
            except Exception as exc:
                logger.warning('failed to fetch XXYY pair info for %s: %s', event.id, exc)
                try:
                    xxyy_snapshot = self._xxyy_client.find_token_snapshot(
                        event.token.address,
                        chain=event.chain or 'sol',
                    )
                except Exception as fallback_exc:
                    logger.warning('failed to fetch XXYY trending fallback for %s: %s', event.id, fallback_exc)
            try:
                stat_info_payload = self._xxyy_client.fetch_holder_stat_info(
                    mint=event.token.address,
                    chain=event.chain or 'sol',
                )
            except Exception as exc:
                logger.warning('failed to fetch XXYY holder stats for %s: %s', event.id, exc)
            launched_pair = (
                pair_info_payload.get('data', {}).get('launchPlatform', {}).get('launchedPair')
                if isinstance(pair_info_payload, dict)
                else None
            )
            if launched_pair:
                pair_address = str(launched_pair).strip()
            elif xxyy_snapshot:
                pair_address = str(xxyy_snapshot.get('pairAddress', '')).strip() or pair_address
            if pair_address:
                try:
                    kol_payload = self._xxyy_client.fetch_kol_holders(
                        mint=event.token.address,
                        pair=pair_address,
                        chain=event.chain or 'sol',
                    )
                except Exception as exc:
                    logger.warning('failed to fetch XXYY kol holders for %s: %s', event.id, exc)
                try:
                    follow_payload = self._xxyy_client.fetch_follow_holders(
                        mint=event.token.address,
                        pair=pair_address,
                        chain=event.chain or 'sol',
                    )
                except Exception as exc:
                    logger.warning('failed to fetch XXYY follow holders for %s: %s', event.id, exc)
            context['xxyy'] = build_xxyy_context(
                xxyy_snapshot,
                stat_info=(
                    stat_info_payload.get('data', {})
                    if isinstance(stat_info_payload, dict)
                    else {}
                ),
                pair_info=(
                    pair_info_payload.get('data', {})
                    if isinstance(pair_info_payload, dict)
                    else {}
                ),
                kol_holders=kol_payload.get('data', []) if isinstance(kol_payload, dict) else [],
                follow_holders=(
                    follow_payload.get('data', []) if isinstance(follow_payload, dict) else []
                ),
            )

        if self._options.twitter_enabled:
            dexs_links = context['dexscreener'].get('links') if isinstance(context['dexscreener'], dict) else []
            twitter_url = _find_social_link(dexs_links, {'twitter', 'x'})
            telegram_url = _find_social_link(dexs_links, {'telegram'})
            if not twitter_url:
                twitter_url = (
                    context['xxyy'].get('project_twitter_url')
                    if isinstance(context['xxyy'], dict)
                    else None
                )
            if (
                telegram_url
                and isinstance(context['xxyy'], dict)
                and not context['xxyy'].get('project_telegram_url')
            ):
                context['xxyy']['project_telegram_url'] = telegram_url
            username = _extract_twitter_username(twitter_url)
            profile_metrics = {}
            if username:
                profile_metrics = await self._twitter_client.fetch_profile_metrics(username)
            context['twitter'] = {
                'profile_url': twitter_url,
                'username': username,
                'community_count': profile_metrics.get('community_count'),
                'followers_count': profile_metrics.get('followers_count'),
                'friends_count': profile_metrics.get('friends_count'),
                'statuses_count': profile_metrics.get('statuses_count'),
            }

        return context


def _extract_twitter_username(profile_url: Any) -> Optional[str]:
    if not profile_url:
        return None
    try:
        parsed = urlparse(str(profile_url))
    except Exception:
        return None
    parts = [part for part in parsed.path.split('/') if part]
    if not parts:
        return None
    if parts[:2] == ['i', 'communities']:
        return None
    if len(parts) >= 3 and parts[1] == 'status':
        return parts[0].lstrip('@') or None
    return parts[0].lstrip('@') or None


def _find_social_link(links: Any, types: set[str]) -> Optional[str]:
    if not isinstance(links, list):
        return None
    for item in links:
        if not isinstance(item, dict):
            continue
        link_type = str(item.get('type') or '').strip().lower()
        if link_type not in types:
            continue
        url = item.get('url')
        if url:
            return str(url).strip()
    return None


def _deep_get(payload: Dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
