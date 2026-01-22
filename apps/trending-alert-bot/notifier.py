from typing import Dict, List, Optional
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


def _format_kol_amount(amount: str) -> str:
    """格式化KOL持仓数量"""
    try:
        value = float(amount)
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}K"
        else:
            return f"{value:.2f}"
    except:
        return amount


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _risk_marker(value: float) -> str:
    """风险分级: <10% 低, 10-20% 中, >=30% 高 (20-30% 仍按中)"""
    if value >= 30:
        return "🚨"
    if value >= 10:
        return "⚠️"
    return "ℹ️"


def _format_kol_sections(kol_holders=None, kol_leavers=None) -> str:
    holders = kol_holders or []
    leavers = kol_leavers or []

    if not holders and not leavers:
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
            lines.append(f"  ...还有 {len(holders) - 5} 位KOL")

    if leavers:
        lines.append(f"🛬 已下车 ({len(leavers)}):")
        for kol in leavers[:6]:
            kol_name = kol.get("name", "Unknown")
            last_trade = kol.get("lastTradeTime")
            suffix = ""
            if last_trade:
                try:
                    suffix = f" · {_format_time_ago(int(last_trade))}"
                except (TypeError, ValueError):
                    pass
            lines.append(f"  • {kol_name}{suffix}")
        if len(leavers) > 6:
            lines.append(f"  ...还有 {len(leavers) - 6} 位KOL")

    return "\n".join(lines)


def format_initial_notification(
    contract: Dict,
    chain: str = "",
    kol_holders: Optional[List[Dict]] = None,
    kol_leavers: Optional[List[Dict]] = None,
    narrative: Optional[Dict] = None,
) -> str:
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

    # 审计信息
    audit_info = contract.get("auditInfo", {})
    dev_hp = audit_info.get("devHp", 0)  # Dev持仓
    new_hp = audit_info.get("newHp", 0)  # 新钱包持仓
    insider_hp = audit_info.get("insiderHp", 0)  # 老鼠仓持仓
    snipers = audit_info.get("snipers", 0)  # 狙击钱包数
    bundle_hp = audit_info.get("bundleHp", 0)  # 捆绑占比
    dex_paid = audit_info.get("dexPaid", False)  # Dexs付费

    msg = f"""{chain_prefix}🔥 趋势发现 🔥

💎 {symbol} ({name})
📝 CA: <code>{token_address}</code>

💰 价格: <b>${price:.8f}</b>
📊 市值: <b>{_format_market_cap(market_cap)}</b>
👥 Holders: <b>{holders:.2f}</b>
📈 24h 涨跌幅: <b>{price_change_24h}%</b>

🔒 安全:
{_risk_marker(top_holder)} Top Holder: <b>{top_holder:.2f}%</b>
{_risk_marker(dev_hp)} Dev持仓: <b>{dev_hp:.2f}%</b>
{_risk_marker(new_hp)} 新钱包持仓: <b>{new_hp:.2f}%</b>
{_risk_marker(insider_hp)} 老鼠仓持仓: <b>{insider_hp:.2f}%</b>
🎯 狙击钱包数: <b>{snipers}</b>
{_risk_marker(bundle_hp)} 捆绑占比: <b>{bundle_hp:.2f}%</b>
💵 Dexs付费: <b>{"✅" if dex_paid else "❌"}</b>

⏰ 创建时间: {time_ago}
⏰ 推送时间: {push_time}
🏪 DEX: {dex_name}
🎯 Launch From: {launch_from}"""

    # 添加叙事分析
    msg += "\n\n📖 叙事分析:"
    if narrative:
        narrative_type = narrative.get("narrative_type", "")
        rating = narrative.get("rating", {})
        score = rating.get("score", "")
        background = narrative.get("background", {})
        origin_text = background.get("origin", {}).get("text", "")
        distribution = narrative.get("distribution", {})
        celebrity = distribution.get("celebrity_support", {}).get("text", "")
        negative = distribution.get("negative_incidents", {}).get("text", "")

        has_content = False
        if score:
            msg += f"\n⭐ 评分: <b>{score}/5</b>"
            has_content = True
        if narrative_type:
            msg += f"\n📌 类型: <b>{narrative_type}</b>"
            has_content = True
        if celebrity and celebrity != "None":
            msg += f"\n👤 名人支持: {celebrity}"
            has_content = True
        if origin_text:
            # 截取前150个字符
            origin_short = origin_text[:150] + "..." if len(origin_text) > 150 else origin_text
            msg += f"\n📜 背景: {origin_short}"
            has_content = True
        if negative:
            # 截取前100个字符
            negative_short = negative[:100] + "..." if len(negative) > 100 else negative
            msg += f"\n⚠️ 风险: {negative_short}"
            has_content = True

        if not has_content:
            msg += "\n暂无数据"
    else:
        msg += "\n暂无数据"

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
        if not has_links:
            msg += "\n暂无数据"
    else:
        msg += "\n暂无数据"

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
    current_time = format_beijing_time()
    token_address = contract.get("tokenAddress", "N/A")
    chain_prefix = f"[{chain.upper()}] " if chain else ""

    msg = f"""{chain_prefix}🚀 倍数通知 {multiplier:.2f}X 🚀

💎 {symbol}
📝 CA: <code>{token_address}</code>

💰 初始价格: <b>${initial_price:.8f}</b>
💵 当前价格: <b>${current_price:.8f}</b>
📈 涨幅: <b>{multiplier:.2f}X</b>

📊 推送时市值: <b>{_format_market_cap(initial_market_cap)}</b>
💎 当前市值: <b>{_format_market_cap(current_market_cap)}</b>

⏰ 推送时间: {push_time}
⏰ 当前时间: {current_time}
"""
    msg += _format_kol_sections(kol_holders, kol_leavers)
    return msg.strip()


def format_narrative_notification(
    token_address: str,
    symbol: str,
    narrative: Dict,
    chain: str = ""
) -> str:
    """格式化叙事更新通知"""
    chain_prefix = f"[{chain.upper()}] " if chain else ""

    narrative_type = narrative.get("narrative_type", "")
    rating = narrative.get("rating", {})
    score = rating.get("score", "")
    background = narrative.get("background", {})
    origin_text = background.get("origin", {}).get("text", "")
    distribution = narrative.get("distribution", {})
    celebrity = distribution.get("celebrity_support", {}).get("text", "")
    negative = distribution.get("negative_incidents", {}).get("text", "")

    msg = f"""{chain_prefix}📖 叙事更新 📖

💎 {symbol}
📝 CA: <code>{token_address}</code>"""

    if score:
        msg += f"\n\n⭐ 评分: {score}/5"
    if narrative_type:
        msg += f"\n📌 类型: {narrative_type}"
    if celebrity and celebrity != "None":
        msg += f"\n👤 名人支持: {celebrity}"
    if origin_text:
        origin_short = origin_text[:200] + "..." if len(origin_text) > 200 else origin_text
        msg += f"\n\n📜 背景:\n{origin_short}"
    if negative:
        negative_short = negative[:150] + "..." if len(negative) > 150 else negative
        msg += f"\n\n⚠️ 风险提示:\n{negative_short}"

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
