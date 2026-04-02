from typing import Dict, List, Optional
from urllib.parse import quote
from timezone_utils import beijing_now, format_beijing_time


def _format_time_ago(timestamp_ms: int) -> str:
    if not timestamp_ms:
        return "N/A"

    now = beijing_now().timestamp() * 1000
    diff_ms = now - timestamp_ms
    diff_seconds = diff_ms / 1000

    if diff_seconds < 60:
        return f"{int(diff_seconds)} sec ago"
    elif diff_seconds < 3600:
        return f"{int(diff_seconds / 60)} min ago"
    elif diff_seconds < 86400:
        return f"{int(diff_seconds / 3600)} hour ago"
    else:
        return f"{int(diff_seconds / 86400)} day ago"


def _format_market_cap(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value / 1_000:.2f}K"
    else:
        return f"${value:.2f}"


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_kol_sections(kol_holders=None, kol_leavers=None) -> str:
    holders = kol_holders or []

    if not holders:
        return ""

    lines = ["", "", "👑 KOL 状态:"]

    if holders:
        lines.append(f"🚀 已上车 ({len(holders)}):")
        for kol in holders[:5]:
            kol_name = kol.get("name", "Unknown")
            hold_value_usd = _safe_float(kol.get("holdValueUSD"))
            hold_percent = _safe_float(kol.get("holdPercent"))
            buy_count = kol.get("buyCount") or 0
            sell_count = kol.get("sellCount") or 0
            lines.append(
                f"  • {kol_name}: {_format_market_cap(hold_value_usd)} ({hold_percent:.2f}%) | 买{buy_count}/卖{sell_count}"
            )
        if len(holders) > 5:
            lines.append("  ...")

    return "\n".join(lines)


def format_initial_notification(
    contract: Dict,
    chain: str = "",
    kol_holders: Optional[List[Dict]] = None,
    kol_leavers: Optional[List[Dict]] = None,
    is_anomaly: bool = False,
) -> str:
    symbol = contract.get("symbol", "N/A")
    name = contract.get("name", "N/A")
    price = float(contract.get("priceUSD", 0))
    market_cap = float(contract.get("marketCapUSD", 0))
    volume_24h = float(contract.get("volume", 0))
    token_address = contract.get("tokenAddress", "N/A")
    price_change_24h = contract.get("priceChange24H", "N/A")
    holders = contract.get("holders", 0)
    create_time = contract.get("createTime")
    dex_name = contract.get("dexName", "N/A")
    launch_from = contract.get("launchFrom", "N/A")
    links = contract.get("links", {})

    time_ago = _format_time_ago(int(create_time)) if create_time else "N/A"
    push_time = format_beijing_time()
    chain_prefix = f"[{chain.upper()}] " if chain else ""

    title = "⚡️ 异动通知" if is_anomaly else "📈 趋势通知"
    msg = f"""{chain_prefix}{title}

💎 {symbol} ({name})
📝 CA: <code>{token_address}</code>

💰 价格: ${price:.8f}
📊 市值: {_format_market_cap(market_cap)}
👥 Holders: {holders:.2f}
🔁 24h 交易量: {_format_market_cap(volume_24h)}
📈 24h 涨跌幅: {price_change_24h}%

⏰ 创建时间: {time_ago}
⏰ 推送时间: {push_time}
🏪 DEX: {dex_name}
🎯 Launch From: {launch_from}"""

    msg += _format_kol_sections(kol_holders, kol_leavers)

    msg += "\n\n📱 链接:"
    if links:
        link_icons = {
            "x": "🐦 Twitter",
            "web": "🌐 Website",
            "telegram": "📱 Telegram",
            "discord": "💬 Discord"
        }
        has_links = False
        for key, url in links.items():
            if url:
                icon_text = link_icons.get(key, f"🔗 {key.title()}")
                msg += f"\n{icon_text}: {url}"
                has_links = True
        search_url = f"https://x.com/search?q={quote(token_address)}"
        msg += f"\n🔎 搜索合约: {search_url}"
        has_links = True
        if not has_links:
            msg += "\n暂无数据"
    else:
        search_url = f"https://x.com/search?q={quote(token_address)}"
        msg += f"\n🔎 搜索合约: {search_url}"

    return msg.strip()


def format_multiplier_notification(
    contract: Dict,
    initial_price: float,
    current_price: float,
    multiplier: float,
    initial_market_cap: float,
    push_time: str,
    chain: str = "",
    kol_holders: Optional[List[Dict]] = None,
    kol_leavers: Optional[List[Dict]] = None,
) -> str:
    symbol = contract.get("symbol", "N/A")
    current_market_cap = float(contract.get("marketCapUSD", 0))
    token_address = contract.get("tokenAddress", "N/A")
    chain_prefix = f"[{chain.upper()}] " if chain else ""

    msg = f"""{chain_prefix}🚀 倍数通知 {multiplier:.2f}X

💎 {symbol}
📝 CA: <code>{token_address}</code>

📈 涨幅: {multiplier:.2f}X
💵 当前价格: ${current_price:.8f}
💎 当前市值: {_format_market_cap(current_market_cap)}

"""
    msg += _format_kol_sections(kol_holders, kol_leavers)
    return msg.strip()


def format_summary_report(
    chain_stats: Dict[str, Dict],
    next_report_time: str
) -> str:
    current_time = format_beijing_time("%Y-%m-%d %H:%M")

    msg = f"""📊 今日趋势汇总报告

📅 报告时间: {current_time}\n"""

    rank_emojis = ["🥇", "🥈", "🥉"]

    # 按链分开显示统计
    for chain in sorted(chain_stats.keys()):
        stats = chain_stats[chain]
        trend_count = stats["trend_count"]
        multiplier_count = stats["total_multiplier_contracts"]
        win_count = stats["win_count"]
        top_contracts = stats["top_contracts"]

        # 计算胜率
        win_rate = (win_count / multiplier_count * 100) if multiplier_count > 0 else 0

        # 获取倍数分布
        dist = stats.get("multiplier_distribution", {})
        count_2x = dist.get("2x", 0)
        count_5x = dist.get("5x", 0)
        count_10x_plus = dist.get("10x_plus", 0)

        # 计算百分比（基于趋势通知总数）
        pct_2x = (count_2x / trend_count * 100) if trend_count > 0 else 0
        pct_5x = (count_5x / trend_count * 100) if trend_count > 0 else 0
        pct_10x_plus = (count_10x_plus / trend_count * 100) if trend_count > 0 else 0

        gain_dist = stats.get("gain_distribution", {})
        gain_lines = ""
        for label in ["20%", "30%", "50%", "80%"]:
            cnt = gain_dist.get(label, 0)
            pct = (cnt / trend_count * 100) if trend_count > 0 else 0
            gain_lines += f"  • >{label}: {cnt}个 ({pct:.1f}%)\n"

        msg += f"""\n━━━━━━━━━━━━━━━━━━━━━━
📊 {chain.upper()} 链统计
━━━━━━━━━━━━━━━━━━━━━━
今日趋势通知: {trend_count}个
有倍数通知: {multiplier_count}个

📈 涨幅胜率:
{gain_lines.rstrip()}

📈 倍数分布:
  • 2X: {count_2x}个 ({pct_2x:.1f}%)
  • 5X: {count_5x}个 ({pct_5x:.1f}%)
  • ≥10X: {count_10x_plus}个 ({pct_10x_plus:.1f}%)\n"""

        if not top_contracts:
            msg += "暂无倍数通知数据\n"
        else:
            msg += "\n🎯 倍数TOP3:\n"

            for idx, item in enumerate(top_contracts):
                contract = item["contract"]
                stored_data = item["stored_data"]
                multiplier = item["multiplier"]

                symbol = contract.get("symbol", "N/A")
                name = contract.get("name", "N/A")
                token_address = contract.get("tokenAddress", "N/A")
                initial_price = stored_data.get("initial_price", 0)
                # 最高倍数通知时的价格 = 初始价格 * 最高倍数
                max_multiplier_price = initial_price * multiplier
                # 最高倍数通知时的市值 = 初始市值 * 最高倍数
                initial_market_cap = stored_data.get("initial_market_cap", 0)
                max_multiplier_market_cap = initial_market_cap * multiplier
                push_time = stored_data.get("push_time", "N/A")

                rank_emoji = rank_emojis[idx] if idx < len(rank_emojis) else f"{idx + 1}."

                msg += f"""
{rank_emoji} {symbol} ({name})
  CA: <code>{token_address}</code>
  倍数: {multiplier:.2f}X
  首次趋势通知价格: ${initial_price:.8f}
  最高倍数通知价格: ${max_multiplier_price:.8f}
  最高倍数通知市值: {_format_market_cap(max_multiplier_market_cap)}
  推送: {push_time}
"""

    msg += f"\n⏰ 下次汇总: {next_report_time}"

    return msg.strip()
