from typing import Dict
from datetime import datetime
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


def format_initial_notification(contract: Dict, chain: str = "") -> str:
    symbol = contract.get("symbol", "N/A")
    name = contract.get("name", "N/A")
    price = float(contract.get("priceUSD", 0))
    market_cap = float(contract.get("marketCapUSD", 0))
    token_address = contract.get("tokenAddress", "N/A")
    price_change_24h = contract.get("priceChange24H", "N/A")
    holders = contract.get("holders", 0)
    create_time = contract.get("createTime")
    dex_name = contract.get("dexName", "N/A")
    launch_from = contract.get("launchFrom", "N/A")
    links = contract.get("links", {})
    security = contract.get("security", {})
    top_holder = security.get("topHolder", {}).get("value", 0)

    time_ago = _format_time_ago(int(create_time)) if create_time else "N/A"
    push_time = format_beijing_time()
    chain_prefix = f"[{chain.upper()}] " if chain else ""

    msg = f"""{chain_prefix}🔥 趋势发现 🔥

💎 {symbol} ({name})
📝 CA: <code>{token_address}</code>

💰 价格: ${price:.8f}
📊 市值: {_format_market_cap(market_cap)}
👥 Holders: {holders:.2f}
📈 24h 涨跌幅: {price_change_24h}%

🔒 安全:
📊 Top Holder: {top_holder:.2f}%

⏰ 创建时间: {time_ago}
⏰ 推送时间: {push_time}
🏪 DEX: {dex_name}
🎯 Launch From: {launch_from}"""

    if links:
        msg += "\n\n📱 链接:"
        link_icons = {
            "x": "🐦 Twitter",
            "web": "🌐 Website",
            "telegram": "📱 Telegram",
            "discord": "💬 Discord"
        }
        for key, url in links.items():
            if url:
                icon_text = link_icons.get(key, f"🔗 {key.title()}")
                msg += f"\n{icon_text}: {url}"

    return msg.strip()


def format_multiplier_notification(
    contract: Dict,
    initial_price: float,
    current_price: float,
    multiplier: float,
    initial_market_cap: float,
    push_time: str,
    chain: str = ""
) -> str:
    symbol = contract.get("symbol", "N/A")
    current_market_cap = float(contract.get("marketCapUSD", 0))
    current_time = format_beijing_time()
    token_address = contract.get("tokenAddress", "N/A")
    chain_prefix = f"[{chain.upper()}] " if chain else ""

    msg = f"""{chain_prefix}🚀 倍数通知 {multiplier:.2f}X 🚀

💎 {symbol}
📝 CA: <code>{token_address}</code>

💰 初始价格: ${initial_price:.8f}
💵 当前价格: ${current_price:.8f}
📈 涨幅: {multiplier:.2f}X

📊 推送时市值: {_format_market_cap(initial_market_cap)}
💎 当前市值: {_format_market_cap(current_market_cap)}

⏰ 推送时间: {push_time}
⏰ 当前时间: {current_time}
"""
    return msg.strip()


def format_summary_report(
    chain_stats: Dict[str, Dict],
    next_report_time: str
) -> str:
    current_time = format_beijing_time("%Y-%m-%d %H:%M")

    msg = f"""🏆 4小时趋势汇总报告 🏆

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

        msg += f"""\n━━━━━━━━━━━━━━━━━━━━━━
📊 {chain.upper()} 链统计
━━━━━━━━━━━━━━━━━━━━━━
今日趋势通知: {trend_count}个
有倍数通知: {multiplier_count}个

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


def format_milestone_notification(
    contract: Dict,
    milestone: int,
    initial_market_cap: float,
    push_time: str,
    first_seen_time: str,
    initial_price: float = 0,
    current_price_param: float = 0,
    chain: str = ""
) -> str:
    symbol = contract.get("symbol", "N/A")
    name = contract.get("name", "N/A")
    current_market_cap = float(contract.get("marketCapUSD", 0))
    current_price = current_price_param if current_price_param > 0 else float(contract.get("priceUSD", 0))
    holders = contract.get("holders", 0)
    current_time = format_beijing_time()

    # 计算增长倍数
    growth_multiplier = current_market_cap / initial_market_cap if initial_market_cap > 0 else 0

    # 计算价格倍数
    price_multiplier = current_price / initial_price if initial_price > 0 else 0

    # 计算耗时
    try:
        first_time = datetime.fromisoformat(first_seen_time)
        now = beijing_now().replace(tzinfo=None)
        time_diff = now - first_time
        hours = int(time_diff.total_seconds() // 3600)
        minutes = int((time_diff.total_seconds() % 3600) // 60)
        time_taken = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
    except:
        time_taken = "N/A"

    token_address = contract.get("tokenAddress", "N/A")
    pair_address = contract.get("pairAddress", "")

    chain_prefix = f"[{chain.upper()}] " if chain else ""
    msg = f"""{chain_prefix}🎯 市值里程碑 🎯

💰 {symbol} 突破 {_format_market_cap(milestone)} 市值！

📋 合约地址:
<code>{token_address}</code>

🔄 交易对:
<code>{pair_address}</code>

📊 初始市值: {_format_market_cap(initial_market_cap)}
💎 当前市值: {_format_market_cap(current_market_cap)}
📈 市值增长: {growth_multiplier:.2f}X"""

    if price_multiplier > 0:
        msg += f"\n🚀 价格倍数: {price_multiplier:.2f}X"

    msg += f"""

💵 当前价格: ${current_price:.8f}
👤 持有人: {holders:.2f}

⏱ 推送时间: {push_time}
📅 当前时间: {current_time}
⏳ 耗时: {time_taken}
"""
    return msg.strip()


def format_surge_notification(
    contract: Dict,
    window_seconds: int,
    percentage: float,
    old_price: float,
    new_price: float,
    old_market_cap: float,
    initial_price: float = 0,
    chain: str = ""
) -> str:
    symbol = contract.get("symbol", "N/A")
    name = contract.get("name", "N/A")
    current_market_cap = float(contract.get("marketCapUSD", 0))
    current_time = format_beijing_time()

    # 计算相对于初始价格的倍数
    price_multiplier = new_price / initial_price if initial_price > 0 else 0

    # 格式化时间窗口
    if window_seconds < 60:
        window_str = f"{window_seconds}秒"
    elif window_seconds < 3600:
        window_str = f"{window_seconds // 60}分钟"
    else:
        window_str = f"{window_seconds // 3600}小时"

    price_change = ((new_price - old_price) / old_price * 100) if old_price > 0 else 0

    token_address = contract.get("tokenAddress", "N/A")
    pair_address = contract.get("pairAddress", "")

    chain_prefix = f"[{chain.upper()}] " if chain else ""
    msg = f"""{chain_prefix}⚡️ 短时暴涨 +{percentage:.0f}% ⚡️

🔥 {symbol} {window_str}内暴涨 {price_change:.1f}%！

📋 合约地址:
<code>{token_address}</code>

🔄 交易对:
<code>{pair_address}</code>

💵 起始价格: ${old_price:.8f}
💰 当前价格: ${new_price:.8f}
📈 短时涨幅: +{price_change:.1f}%"""

    if price_multiplier > 0:
        msg += f"\n🚀 总价格倍数: {price_multiplier:.2f}X (从推送时起)"

    msg += f"""

📊 起始市值: {_format_market_cap(old_market_cap)}
💎 当前市值: {_format_market_cap(current_market_cap)}

📅 检测时间: {current_time}
⏱ 时间窗口: {window_str}
"""
    return msg.strip()



