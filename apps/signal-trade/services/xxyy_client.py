"""XXYY data client and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from curl_cffi import requests
from config import XXYY_AUTHORIZATION, XXYY_COOKIE, XXYY_INFO_TOKEN


XXYY_BASE_URL = 'https://www.xxyy.io'
XXYY_FOLLOW_BASE_URL = 'https://amazon-ga.xxyy.io'


def _build_headers(chain: str = 'sol', referer: str = '') -> dict:
    return {
        'referer': referer or XXYY_BASE_URL,
        'x-chain': chain,
    }


@dataclass
class XXYYRuntimeOptions:
    """Runtime options for XXYY requests."""

    timeout_sec: int = 30
    authorization: str = XXYY_AUTHORIZATION
    info_token: str = XXYY_INFO_TOKEN
    cookie: str = XXYY_COOKIE


class XXYYClient:
    """Thin wrapper around XXYY endpoints used by Signal Trade."""

    def __init__(self, options: Optional[XXYYRuntimeOptions] = None) -> None:
        self._options = options or XXYYRuntimeOptions()

    def fetch_trending(self, period: str = '1M', category: str = '', chain: str = 'sol') -> dict:
        response = requests.post(
            f'{XXYY_BASE_URL}/api/data/list/trending',
            headers=_build_headers(chain),
            json={'period': period, 'category': category},
            timeout=self._options.timeout_sec,
            impersonate='chrome120',
        )
        response.raise_for_status()
        return response.json()

    def fetch_pair_info(self, pair_address: str, chain: str = 'sol', base_only: int = 0) -> dict:
        """Fetch token detail by pairAddress or mint from XXYY token detail page.

        Despite the parameter name, XXYY accepts a token mint here and will
        resolve the launched pair in the response when available.

        Returns:
            {
                "code": 0,
                "msg": null,
                "data": {
                    "launchPlatform": {"launchedPair": "..."},
                    "priceInfo": {"marketCapUSD": "...", "priceUSD": "..."},
                    "tokenInfo": {"linkInfo": {"x": "...", "tg": "..."}, "symbol": "..."},
                    "holderInfo": {"total": 2887},
                    "assistInfo": {"dexPaid": true, "snipers": 43, ...}
                }
            }
        """
        headers = {
            'accept': 'application/json, text/plain, */*',
            'origin': XXYY_BASE_URL,
            'referer': f'{XXYY_BASE_URL}/{chain}/{pair_address}',
            'user-agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/146.0.0.0 Safari/537.36'
            ),
            'x-chain': chain,
            'x-language': 'zh',
            'x-version': '1',
        }

        response = requests.get(
            f'{XXYY_BASE_URL}/api/data/pair/info',
            params={'pairAddress': pair_address, 'baseOnly': base_only},
            headers=headers,
            timeout=self._options.timeout_sec,
            impersonate='chrome120',
        )
        response.raise_for_status()
        return response.json()

    def fetch_kol_holders(self, mint: str, pair: str, chain: str = 'sol') -> dict:
        headers = _build_headers(chain, f'{XXYY_BASE_URL}/{chain}/{pair}')

        response = requests.get(
            f'{XXYY_BASE_URL}/api/data/holders/kol',
            params={'mint': mint, 'pair': pair},
            headers=headers,
            timeout=self._options.timeout_sec,
            impersonate='chrome120',
        )
        response.raise_for_status()
        return response.json()

    def fetch_follow_holders(self, mint: str, pair: str, chain: str = 'sol') -> dict:
        """Fetch followed-wallet holder data from XXYY.

        Returns:
            {
                "code": 0,
                "msg": null,
                "data": [
                    {
                        "address": "钱包地址",
                        "name": "关注对象名称",
                        "holdAmount": "当前持仓数量",
                        "holdPercent": "当前持仓占比%",
                        "holdValueNative": "当前持仓价值(原生代币)",
                        "holdValueUSD": "当前持仓价值(USD)",
                        "tags": [],
                        "tradeCount": 交易次数,
                        "buyCount": 买入次数,
                        "sellCount": 卖出次数,
                        "buyAmount": 买入总额,
                        "sellAmount": 卖出总额,
                        "lastTradeTime": 最后交易时间戳(ms),
                        "tokenSourceType": 1,
                        "tokenSourceAddress": "pfamm",
                        "tokenSourceName": null,
                        "nativeSourceAddress": "原生币地址",
                        "nativeSourceName": null,
                        "nativeBalance": 原生币余额,
                        "actualHoldPercent": null,
                        "profitNative": 利润(原生代币),
                        "profitUSD": 利润(USD),
                        "profitPercent": 利润率,
                        "avgBuyPrice": 平均买入价格,
                        "avgBuyPriceUsd": 平均买入价格(USD),
                        "avgBuyMarketCap": 平均买入市值,
                        "avgBuyMarketCapUsd": 平均买入市值(USD),
                        "avgSellPrice": 平均卖出价格,
                        "avgSellPriceUsd": 平均卖出价格(USD),
                        "avgSellMarketCap": 平均卖出市值,
                        "avgSellMarketCapUsd": 平均卖出市值(USD)
                    }
                ]
            }
        """
        headers = {
            'accept': 'application/json, text/plain, */*',
            'origin': XXYY_BASE_URL,
            'referer': f'{XXYY_BASE_URL}/',
            'user-agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/146.0.0.0 Safari/537.36'
            ),
            'x-chain': chain,
            'x-language': 'zh',
            'x-version': '1',
        }
        if self._options.authorization:
            headers['authorization'] = self._options.authorization
        if self._options.info_token:
            headers['x-info-token'] = self._options.info_token
        headers = {key: value for key, value in headers.items() if value}

        response = requests.get(
            f'{XXYY_FOLLOW_BASE_URL}/api/data/holders/follow',
            params={'mint': mint, 'pair': pair},
            headers=headers,
            cookies=_parse_cookie_header(self._options.cookie),
            timeout=self._options.timeout_sec,
            impersonate='chrome120',
        )
        response.raise_for_status()
        return response.json()

    def fetch_holder_stat_info(self, mint: str, chain: str = 'sol', only_total: int = 0) -> dict:
        """Fetch holder summary stats for one token.

        Returns:
            {
                "code": 0,
                "msg": null,
                "data": {
                    "totalHolders": 2859,
                    "followedHolders": 9,
                    "kolHolders": 18,
                    "insiderHolders": 0
                }
            }
        """
        headers = {
            'accept': 'application/json, text/plain, */*',
            'origin': XXYY_BASE_URL,
            'referer': f'{XXYY_BASE_URL}/',
            'user-agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/146.0.0.0 Safari/537.36'
            ),
            'x-chain': chain,
            'x-language': 'zh',
            'x-version': '1',
        }
        if self._options.authorization:
            headers['authorization'] = self._options.authorization
        if self._options.info_token:
            headers['x-info-token'] = self._options.info_token

        response = requests.get(
            f'{XXYY_FOLLOW_BASE_URL}/api/data/holders/statInfo',
            params={'mint': mint, 'onlyTotal': only_total},
            headers=headers,
            cookies=_parse_cookie_header(self._options.cookie),
            timeout=self._options.timeout_sec,
            impersonate='chrome120',
        )
        response.raise_for_status()
        return response.json()

    def find_token_snapshot(self, token_address: str, chain: str = 'sol') -> Dict[str, Any]:
        payload = self.fetch_trending(chain=chain)
        for item in payload.get('data', []) or []:
            if str(item.get('tokenAddress', '')).strip().lower() == token_address.strip().lower():
                return item
        return {}


def build_xxyy_context(
    snapshot: Dict[str, Any],
    stat_info: Optional[Dict[str, Any]] = None,
    pair_info: Optional[Dict[str, Any]] = None,
    kol_holders: Optional[List[Dict[str, Any]]] = None,
    follow_holders: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    stats = stat_info or {}
    pair = pair_info or {}
    holders = kol_holders or []
    followed_holders = follow_holders or []
    price_info = _safe_dict(pair.get('priceInfo'))
    token_info = _safe_dict(pair.get('tokenInfo'))
    link_info = _safe_dict(token_info.get('linkInfo'))
    holder_info = _safe_dict(pair.get('holderInfo'))
    security = _safe_dict(pair.get('securityInfo'))
    audit_info = _safe_dict(pair.get('assistInfo'))
    launch_platform = _safe_dict(pair.get('launchPlatform'))
    pair_details = _safe_dict(pair.get('pairInfo'))
    twitter_url = link_info.get('x') or _safe_dict(snapshot.get('links')).get('x')
    telegram_url = link_info.get('tg') or _safe_dict(snapshot.get('links')).get('tg')

    return {
        'market_cap': _safe_float(price_info.get('marketCapUSD')) or _safe_float(snapshot.get('marketCapUSD')),
        'holder_count': (
            _safe_int(stats.get('totalHolders'))
            or _safe_int(holder_info.get('total'))
            or _safe_int(snapshot.get('holders'))
        ),
        'price_usd': _safe_float(price_info.get('priceUSD')) or _safe_float(snapshot.get('priceUSD')),
        'volume': _safe_float(_safe_dict(pair.get('tradeInfo')).get('volume24HUSD')) or _safe_float(snapshot.get('volume')),
        'liquidity': _safe_float(pair_details.get('liquidityUSD')) or _safe_float(snapshot.get('liquid')),
        'buy_count': _safe_int(snapshot.get('buyCount')),
        'sell_count': _safe_int(snapshot.get('sellCount')),
        'follow_buy_count': _safe_int(stats.get('followedHolders')) or _count_follow_buyers(followed_holders),
        'kol_buy_count': _safe_int(stats.get('kolHolders')) or _count_kol_buyers(holders),
        'follow_or_kol_buy_count': (
            (_safe_int(stats.get('followedHolders')) or _count_follow_buyers(followed_holders))
            + (_safe_int(stats.get('kolHolders')) or _count_kol_buyers(holders))
        ),
        'follow_addresses': _extract_unique_values(followed_holders, 'address'),
        'kol_addresses': _extract_unique_values(holders, 'address'),
        'follow_names': _extract_unique_values(followed_holders, 'name'),
        'kol_names': _extract_unique_values(holders, 'name'),
        'insider_holder_count': _safe_int(stats.get('insiderHolders')),
        'project_twitter_url': twitter_url,
        'project_telegram_url': telegram_url,
        'security': {
            'honeypot': _safe_nested_bool(security, 'honeyPot', 'value'),
            'top_holder_percent': _safe_nested_float(security, 'topHolder', 'value'),
        },
        'audit': {
            'dev_hold_percent': _safe_float(audit_info.get('devHp')),
            'snipers': _safe_int(audit_info.get('snipers')),
            'dex_paid': _safe_bool(audit_info.get('dexPaid')),
        },
        'launch_platform': {
            'name': launch_platform.get('name'),
            'completed': _safe_bool(launch_platform.get('completed')),
            'launched_pair': launch_platform.get('launchedPair'),
        },
        'holder_stats': stats,
        'pair_info': pair,
        'raw': snapshot,
        'follow_holders': followed_holders,
        'kol_holders': holders,
    }


def _count_kol_buyers(kol_holders: List[Dict[str, Any]]) -> int:
    count = 0
    for item in kol_holders:
        if not isinstance(item, dict):
            continue
        buy_count = _safe_int(item.get('buyCount'))
        if buy_count is not None:
            if buy_count > 0:
                count += 1
            continue
        if (_safe_float(item.get('holdAmount')) or 0) > 0:
            count += 1
    return count


def _count_follow_buyers(follow_holders: List[Dict[str, Any]]) -> int:
    count = 0
    for item in follow_holders:
        if not isinstance(item, dict):
            continue
        buy_count = _safe_int(item.get('buyCount'))
        if buy_count is not None:
            if buy_count > 0:
                count += 1
            continue
        amount = _safe_float(item.get('holdAmount'))
        if amount is None:
            count += 1
            continue
        if amount > 0:
            count += 1
    return count


def _extract_unique_values(items: List[Dict[str, Any]], key: str) -> List[str]:
    values: List[str] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_value = item.get(key)
        if raw_value in (None, ''):
            continue
        value = str(raw_value).strip()
        if not value:
            continue
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        values.append(value)
    return values


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ''):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ''):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value in (None, ''):
        return None
    return bool(value)


def _safe_nested_bool(payload: Dict[str, Any], *keys: str) -> Optional[bool]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _safe_bool(current)


def _safe_nested_float(payload: Dict[str, Any], *keys: str) -> Optional[float]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _safe_float(current)


def _parse_cookie_header(cookie_header: str) -> Dict[str, str]:
    if not cookie_header:
        return {}
    cookies: Dict[str, str] = {}
    for part in cookie_header.split(';'):
        item = part.strip()
        if not item or '=' not in item:
            continue
        key, value = item.split('=', 1)
        cookies[key.strip()] = value.strip()
    return cookies
