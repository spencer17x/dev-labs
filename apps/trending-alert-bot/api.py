from curl_cffi import requests


def _build_headers(chain: str = "sol", referer: str = "") -> dict:
    """构建统一的请求headers"""
    return {
        "referer": referer or "https://www.xxyy.io",
        "x-chain": chain,
    }


def fetch_trending(period: str = "1M", category: str = "", chain: str = "sol") -> dict:
    """
    获取趋势榜数据

    Args:
        period: 时间周期 (1M等)
        category: 分类筛选
        chain: 链名称 (sol/bsc)

    Returns:
        {
            "code": 0,
            "msg": null,
            "data": [
                {
                    "pairAddress": "交易对地址",
                    "tokenAddress": "代币合约地址",
                    "symbol": "代币符号",
                    "name": "代币名称",
                    "imageUrl": "图片URL",
                    "headerImage": "头图URL",
                    "priceUSD": "价格(USD字符串)",
                    "marketCapUSD": "市值(USD字符串)",
                    "priceChange24H": "24h涨跌幅%",
                    "volume": 交易量(float),
                    "liquid": 流动性(float),
                    "buyCount": 买入次数(int),
                    "sellCount": 卖出次数(int),
                    "holders": 持有人数(int),
                    "createTime": "创建时间戳(ms字符串)",
                    "dexId": "dex ID (pan2/pan3/pfamm/cpmm/amm/dlmm/uni4等)",
                    "dexName": "DEX名称 (Pancake V2/V3, Pump AMM, Raydium等)",
                    "dexIcon": "DEX图标URL",
                    "launchFrom": "发射平台 (pump/four/flap/launchlab等)",
                    "sourceDexIcon": "来源DEX图标",
                    "chainId": "链ID (bsc/sol)",
                    "quoteSymbol": "计价代币符号 (WBNB/USDT/USD1等)",
                    "quoteName": "计价代币名称",
                    "devHoldPercent": "开发者持仓占比%",
                    "listingTime": null,
                    "launchPlatform": {
                        "name": null,
                        "progress": null,
                        "completed": null,
                        "launchedPair": null
                    },
                    "links": {
                        "tg": "Telegram链接",
                        "x": "Twitter链接",
                        "web": "官网链接"
                    },
                    "security": {
                        "freezeAuthority": {"passed": bool, "value": bool},  # SOL链
                        "lpBurned": {"passed": bool, "value": float},        # LP销毁%
                        "mintAuthority": {"passed": bool, "value": bool},    # SOL链
                        "topHolder": {"passed": bool, "value": float},       # 最大持仓%
                        "honeyPot": {"passed": bool, "value": bool},         # BSC链-蜜罐检测
                        "openSource": {"passed": bool, "value": bool},       # BSC链-开源
                        "noOwner": {"passed": bool, "value": bool},          # BSC链-无Owner
                        "locked": {"passed": bool, "value": bool}            # BSC链-锁定
                    },
                    "auditInfo": {
                        "devHp": float,      # 开发者持仓%
                        "snipers": int,      # 狙击手数量
                        "insiderHp": float,  # 内部人持仓%
                        "newHp": float,      # 新钱包持仓%
                        "bundleHp": float,   # 捆绑持仓%
                        "dexPaid": bool      # DEX付费
                    },
                    "extendFlags": {         # SOL链
                        "live": bool
                    },
                    "smartWallets": null,
                    "extra": null
                }
            ]
        }
    """
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
