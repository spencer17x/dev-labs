from curl_cffi import requests


def _build_headers(chain: str = "sol", referer: str = "") -> dict:
    """构建统一的请求headers"""
    return {
        "referer": referer or "https://www.xxyy.io",
        "x-chain": chain,
    }


def fetch_trending(period: str = "1M", category: str = "", chain: str = "sol") -> dict:
    resp = requests.post(
        "https://www.xxyy.io/api/data/list/trending",
        headers=_build_headers(chain),
        json={"period": period, "category": category},
        timeout=30,
        impersonate="chrome120",
    )
    resp.raise_for_status()
    return resp.json()


def fetch_kol_holders(
    mint: str,
    pair: str,
    chain: str = "sol",
    authorization: str = "",
    info_token: str = ""
) -> dict:
    """
    获取代币持有的KOL信息

    Args:
        mint: 代币合约地址 (tokenAddress)
        pair: 交易对地址 (pairAddress)
        chain: 链名称 (sol/bsc)
        authorization: 认证token (从cookie中获取)
        info_token: x-info-token (从cookie中获取)

    Returns:
        {
            "code": 0,
            "msg": null,
            "data": [
                {
                    "address": "钱包地址",
                    "name": "KOL名称",
                    "holdAmount": "持仓数量",
                    "holdPercent": "持仓占比%",
                    "holdValueNative": "持仓价值(原生代币)",
                    "holdValueUSD": "持仓价值(USD)",
                    "tags": [],
                    "tradeCount": 交易次数,
                    "buyCount": 买入次数,
                    "sellCount": 卖出次数,
                    "lastTradeTime": 最后交易时间戳(ms),
                    "profitNative": 利润(原生代币),
                    "profitUSD": 利润(USD)
                }
            ]
        }
    """
    headers = _build_headers(chain, f"https://www.xxyy.io/{chain}/{pair}")

    # 如果提供了认证信息则添加
    if authorization:
        headers["authorization"] = authorization
    if info_token:
        headers["x-info-token"] = info_token

    resp = requests.get(
        "https://www.xxyy.io/api/data/holders/kol",
        params={"mint": mint, "pair": pair},
        headers=headers,
        timeout=30,
        impersonate="chrome120",
    )
    resp.raise_for_status()
    return resp.json()
