"""趋势通知机器人"""

import time
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from api import fetch_trending, fetch_kol_holders, fetch_narrative
from storage import ContractStorage
from notifier import (
    format_initial_notification,
    format_multiplier_notification,
    format_summary_report,
    format_narrative_notification,
)
from config import (
    CHECK_INTERVAL,
    SILENT_INIT,
    CHAINS,
    ENABLE_TELEGRAM,
    STORAGE_DIR,
    CHAIN_ALLOWLISTS,
    SUMMARY_REPORT_HOURS,
    SUMMARY_TOP_N,
)
from telegram_bot import notifier
from timezone_utils import beijing_now


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def split_kol_positions(kol_list: Optional[List[dict]]) -> Tuple[List[dict], List[dict]]:
    """将KOL按是否仍持仓拆分"""
    holders: list = []
    leavers: list = []

    if not kol_list:
        return holders, leavers

    for kol in kol_list:
        hold_amount = _safe_float(kol.get("holdAmount"))
        hold_percent = _safe_float(kol.get("holdPercent"))
        hold_value = _safe_float(kol.get("holdValueUSD"))

        if hold_amount > 0 or hold_percent > 0 or hold_value > 0:
            holders.append(kol)
        else:
            leavers.append(kol)

    return holders, leavers


def load_kol_status(contract: dict, chain: str, context: str = "") -> Tuple[List[dict], List[dict]]:
    token_address = contract.get("tokenAddress")
    pair_address = contract.get("pairAddress", "")

    if not token_address:
        return [], []

    try:
        kol_response = fetch_kol_holders(token_address, pair_address, chain)
        kol_list = kol_response.get("data", []) or []
        return split_kol_positions(kol_list)
    except Exception as e:
        prefix = f"[{chain.upper()}] " if chain else ""
        context_text = f"{context} " if context else ""
        symbol = contract.get("symbol", "N/A")
        print(f"⚠️ {prefix}{symbol} {context_text}获取 KOL 数据失败: {e}")
        return [], []


def check_multipliers(contract: dict, storage: ContractStorage, chain: str = ""):
    token_address = contract.get("tokenAddress")
    current_price = float(contract.get("priceUSD", 0))

    if not token_address or current_price <= 0:
        return

    stored_contract = storage.get_contract(token_address)
    if not stored_contract:
        return

    # 检查是否有真实的趋势通知（排除虚拟ID -1）
    telegram_message_ids = stored_contract.get("telegram_message_ids", {})
    has_real_notification = any(
        msg_id != -1 for msg_id in telegram_message_ids.values()
    )
    if not has_real_notification:
        return

    initial_price = stored_contract["initial_price"]
    if initial_price <= 0:
        return


    multiplier = current_price / initial_price
    current_integer_multiplier = int(multiplier)

    if current_integer_multiplier < 2:
        return

    # 获取已通知的最高整数倍数
    max_notified_integer = storage.get_max_notified_integer_multiplier(token_address)

    # 只在达到新的整数倍数时通知，避免价格回落或在整数边界反复通知
    if current_integer_multiplier > max_notified_integer:
        kol_with_positions, kol_without_positions = load_kol_status(
            contract,
            chain,
            context="倍数通知",
        )

        msg = format_multiplier_notification(
            contract,
            initial_price,
            current_price,
            multiplier,
            stored_contract.get("initial_market_cap", 0),
            stored_contract.get("push_time", "N/A"),
            chain,
            kol_with_positions,
            kol_without_positions,
        )
        print(msg)
        print("\n" + "=" * 60 + "\n")

        if ENABLE_TELEGRAM:
            notifier.send_with_reply_sync(msg, token_address, storage, chain=chain)

        # 存储实际倍数（带小数），用于汇总报告显示真实最高倍数
        storage.update_notified_multiplier(token_address, multiplier)

        # 新增：如果叙事未获取且未通知，尝试获取叙事并发送叙事更新
        if not storage.get_narrative(token_address):
            try:
                narrative_response = fetch_narrative(token_address, chain)
                if narrative_response.get("success"):
                    history = narrative_response.get("data", {}).get("history", {})
                    if history:
                        narrative_data = history.get("story", {})
                        if narrative_data:
                            storage.update_narrative(token_address, narrative_data)
                            symbol = contract.get("symbol", "N/A")
                            msg_narr = format_narrative_notification(token_address, symbol, narrative_data, chain)
                            print(f"📖 [{chain.upper()}] {symbol} 叙事更新 (倍数通知)")
                            print(msg_narr)
                            print("\n" + "=" * 60 + "\n")
                            if ENABLE_TELEGRAM:
                                notifier.send_with_reply_sync(msg_narr, token_address, storage, chain=chain)
                        else:
                            storage.mark_narrative_pending(token_address)
                    else:
                        storage.mark_narrative_pending(token_address)
                else:
                    storage.mark_narrative_pending(token_address)
            except Exception as e:
                print(f"⚠️ 倍数通知叙事获取失败 {contract.get('symbol', 'N/A')}: {e}")
                storage.mark_narrative_pending(token_address)


def check_pending_narratives(storage: ContractStorage, chain: str = ""):
    """检查待更新叙事的合约"""
    pending_contracts = storage.get_pending_narrative_contracts()

    for token_address in pending_contracts:
        stored = storage.get_contract(token_address)
        if not stored:
            continue

        symbol = stored.get("symbol", "N/A")

        try:
            narrative_response = fetch_narrative(token_address, chain)
            if narrative_response.get("success"):
                history = narrative_response.get("data", {}).get("history", {})
                if history:
                    narrative_data = history.get("story", {})
                    if narrative_data:
                        # 存储叙事并发送通知
                        storage.update_narrative(token_address, narrative_data)

                        msg = format_narrative_notification(token_address, symbol, narrative_data, chain)
                        print(f"📖 [{chain.upper()}] {symbol} 叙事更新")
                        print(msg)
                        print("\n" + "=" * 60 + "\n")

                        if ENABLE_TELEGRAM:
                            notifier.send_with_reply_sync(msg, token_address, storage, chain=chain)
        except Exception as e:
            print(f"⚠️ 检查叙事失败 {symbol}: {e}")
            # 如果是 HTTP 错误，打印请求 URL
            if hasattr(e, 'response') and e.response is not None:
                print(f"[check_pending_narratives] 请求URL: {e.response.url}")


def should_filter_contract(contract: dict, chain: str) -> bool:
    chain_allow = CHAIN_ALLOWLISTS.get(chain, {})
    allow_launch_from = [f for f in chain_allow.get("launchFrom", []) if f]
    allow_dex = [f for f in chain_allow.get("dexName", []) if f]

    if not allow_launch_from and not allow_dex:
        return False

    launch_from = contract.get("launchFrom") or ""
    dex_name = contract.get("dexName") or ""

    if allow_launch_from and launch_from in allow_launch_from:
        return False
    if allow_dex and dex_name in allow_dex:
        return False

    return True


def initialize_storage(storage: ContractStorage, chain: str):
    response = fetch_trending(chain=chain)
    contracts = response.get("data", [])

    loaded_count = 0
    first_contract_address = None
    first_is_new = False

    for contract in contracts:
        token_address = contract.get("tokenAddress")
        current_price = float(contract.get("priceUSD", 0))

        if not token_address or current_price <= 0:
            continue

        if should_filter_contract(contract, chain):
            continue

        is_new = storage.is_new_contract(token_address)

        # 记录第一个符合条件的合约
        if first_contract_address is None:
            first_contract_address = token_address
            first_is_new = is_new

        # 只添加新合约，跳过已存在的合约以保留历史数据
        if is_new:
            storage.add_contract(token_address, current_price, contract)
            loaded_count += 1

    # 只为榜一合约标记虚拟ID，且仅当榜一是新合约或没有真实通知时
    if first_contract_address:
        stored_contract = storage.get_contract(first_contract_address)
        if stored_contract:
            telegram_message_ids = stored_contract.get("telegram_message_ids", {})
            # 检查是否已有真实通知（非-1的message_id）
            has_real_notification = any(
                msg_id != -1 for msg_id in telegram_message_ids.values()
            )
            # 只在没有真实通知且没有任何message_id时标记虚拟ID
            if not has_real_notification and not telegram_message_ids:
                storage.update_telegram_message_id(first_contract_address, -1, -1)

    if loaded_count > 0:
        print(f"✅ [{chain.upper()}] 初始化完成，加载 {loaded_count} 个新合约")
    else:
        print(f"⚠️  [{chain.upper()}] 未找到新的符合条件的合约")


def send_summary_report(storages: dict):
    chain_stats = {}
    all_trend_contracts = []

    for chain, storage in storages.items():
        today_contracts = storage.get_today_trend_contracts()

        # 初始化链统计数据
        chain_stats[chain] = {
            "trend_count": len(today_contracts),
            "total_multiplier_contracts": 0,
            "win_count": 0,
            "top_contracts": [],
            "multiplier_distribution": {
                "2x": 0,
                "5x": 0,
                "10x_plus": 0
            }
        }

        for item in today_contracts:
            token_address = item["token_address"]
            stored_data = item["data"]

            notified_multipliers = stored_data.get("notified_multipliers", [])
            if notified_multipliers:
                # 使用最高倍数通知，而不是当前实时倍数
                max_multiplier = max(notified_multipliers)

                # 统计有倍数通知的合约
                chain_stats[chain]["total_multiplier_contracts"] += 1

                # 统计倍数分布（按最高倍数归类：2x, 5x, 10x+）
                max_int_multiplier = int(max_multiplier)
                if max_int_multiplier >= 10:
                    chain_stats[chain]["multiplier_distribution"]["10x_plus"] += 1
                    chain_stats[chain]["win_count"] += 1
                elif max_int_multiplier >= 5:
                    chain_stats[chain]["multiplier_distribution"]["5x"] += 1
                elif max_int_multiplier >= 2:
                    chain_stats[chain]["multiplier_distribution"]["2x"] += 1

                # 尝试获取最新数据，如果失败则使用存储的数据
                contract_data = None
                try:
                    response = fetch_trending(chain=chain)
                    contracts = response.get("data", [])

                    for contract in contracts:
                        if contract.get("tokenAddress") == token_address:
                            contract_data = contract
                            break
                except Exception as e:
                    print(f"❌ 获取 {chain} 链合约数据失败: {e}")

                # 如果获取不到最新数据，使用存储的基本信息构造
                if not contract_data:
                    contract_data = {
                        "tokenAddress": token_address,
                        "symbol": stored_data.get("symbol", "N/A"),
                        "name": stored_data.get("name", "N/A"),
                        "priceUSD": stored_data.get("initial_price", 0),
                        "marketCapUSD": stored_data.get("initial_market_cap", 0)
                    }

                contract_item = {
                    "contract": contract_data,
                    "stored_data": stored_data,
                    "multiplier": max_multiplier,
                    "chain": chain
                }

                all_trend_contracts.append(contract_item)
                chain_stats[chain]["top_contracts"].append(contract_item)

        # 对每个链的合约按倍数排序，取前3
        chain_stats[chain]["top_contracts"].sort(key=lambda x: x["multiplier"], reverse=True)
        chain_stats[chain]["top_contracts"] = chain_stats[chain]["top_contracts"][:SUMMARY_TOP_N]

    now = beijing_now()
    current_hour = now.hour
    current_minute = now.minute
    next_report_hour = None

    # 找到下一个报告时间点（整点前1分钟，即59分）
    for hour in SUMMARY_REPORT_HOURS:
        # 如果当前时间还没到这个小时的59分，就用这个时间
        if hour > current_hour or (hour == current_hour and current_minute < 59):
            next_report_hour = hour
            break

    if next_report_hour is None:
        next_report_hour = SUMMARY_REPORT_HOURS[0]
        next_report_time = now.replace(hour=next_report_hour, minute=59, second=0, microsecond=0)
        next_report_time += timedelta(days=1)
    else:
        next_report_time = now.replace(hour=next_report_hour, minute=59, second=0, microsecond=0)

    next_report_time_str = next_report_time.strftime("%Y-%m-%d %H:%M")

    msg = format_summary_report(chain_stats, next_report_time_str)

    print("\n" + "=" * 60)
    print(msg)
    print("=" * 60 + "\n")

    if ENABLE_TELEGRAM:
        notifier.send_sync(msg)


def should_send_summary_report(last_report_hour: int) -> bool:
    now = beijing_now()
    current_hour = now.hour
    current_minute = now.minute

    # 在整点前1分钟（59分）触发报告
    # 例如：0点报告在23:59触发，4点报告在3:59触发
    for hour in SUMMARY_REPORT_HOURS:
        report_hour = (hour - 1) % 24  # 前1小时
        report_minute = 59

        # 只要在 report_hour:59 这一分钟内，并且还没发送过这个小时的报告
        if current_hour == report_hour and current_minute == report_minute and hour != last_report_hour:
            return True

    return False


def monitor_trending():
    chains = CHAINS

    storages = {}
    for chain in chains:
        storage_file = os.path.join(STORAGE_DIR, f"contracts_data_{chain}.json")
        storages[chain] = ContractStorage(storage_file)

    print(f"🤖 Bot 启动 | 链: {', '.join([c.upper() for c in chains])} | 间隔: {CHECK_INTERVAL}s")
    print(f"📊 策略: 趋势通知(榜一) + 整数倍通知(所有符合条件)")
    print(f"📱 Telegram: {'✓' if ENABLE_TELEGRAM else '✗'}")

    if ENABLE_TELEGRAM:
        notifier.start_bot()

    print()

    for chain in chains:
        if SILENT_INIT:
            initialize_storage(storages[chain], chain)
        else:
            print(f"⚠️  {chain.upper()} 将在第一次扫描时初始化")

    if SILENT_INIT:
        print(f"\n⏳ 等待 {CHECK_INTERVAL} 秒后开始监控...\n")
        time.sleep(CHECK_INTERVAL)

    # 初始化 last_summary_hour，避免启动时立即发送报告
    now = beijing_now()
    current_hour = now.hour
    current_minute = now.minute

    # 检查是否刚好在报告时间点（某个整点的前1分钟，即59分）
    last_summary_hour = -1
    for hour in SUMMARY_REPORT_HOURS:
        report_hour = (hour - 1) % 24
        if current_hour == report_hour and current_minute == 59:
            last_summary_hour = hour
            break

    # 用于跟踪上次清理时间
    last_cleanup_day = beijing_now().day

    while True:
        try:
            scan_time = beijing_now().strftime('%H:%M:%S')
            print(f"\n🔍 [{scan_time}] 扫描趋势榜...")

            # 每天 00:05 自动清理旧数据（北京时间）
            current_time = beijing_now()
            if current_time.day != last_cleanup_day and current_time.hour == 0 and current_time.minute >= 5:
                print("\n🧹 开始清理旧数据...")
                total_deleted = 0
                for chain, storage in storages.items():
                    deleted = storage.cleanup_old_data(days_to_keep=7)
                    if deleted > 0:
                        print(f"  • {chain.upper()}: 清理 {deleted} 个合约")
                        total_deleted += deleted
                if total_deleted > 0:
                    print(f"✅ 清理完成，共删除 {total_deleted} 个合约\n")
                else:
                    print("✅ 无需清理\n")
                last_cleanup_day = current_time.day

            if should_send_summary_report(last_summary_hour):
                # 获取对应的报告整点时间
                now = beijing_now()
                for hour in SUMMARY_REPORT_HOURS:
                    report_hour = (hour - 1) % 24
                    if now.hour == report_hour and now.minute == 59:
                        report_time_hour = hour
                        break
                print(f"\n📊 发送 {report_time_hour}:00 汇总报告...")
                send_summary_report(storages)
                last_summary_hour = report_time_hour

            for chain in chains:
                storage = storages[chain]
                response = fetch_trending(chain=chain)
                contracts = response.get("data", [])

                # 审计过滤：大于30%跳过
                filtered_contracts = []
                for contract in contracts:
                    audit_info = contract.get("auditInfo", {})
                    new_hp = audit_info.get("newHp", 0)
                    if new_hp > 30:
                        print(f"⏭️ [{chain.upper()}] {contract.get('symbol', 'N/A')} 新钱包持仓 {new_hp:.2f}% > 30%，跳过通知")
                        continue
                    insider_hp = audit_info.get("insiderHp", 0)
                    if insider_hp > 30:
                        print(f"⏭️ [{chain.upper()}] {contract.get('symbol', 'N/A')} 老鼠仓持仓 {insider_hp:.2f}% > 30%，跳过通知")
                        continue
                    bundle_hp = audit_info.get("bundleHp", 0)
                    if bundle_hp > 30:
                        print(f"⏭️ [{chain.upper()}] {contract.get('symbol', 'N/A')} 捆绑占比 {bundle_hp:.2f}% > 30%，跳过通知")
                        continue
                    dev_hp = audit_info.get("devHp", 0)
                    if dev_hp > 30:
                        print(f"⏭️ [{chain.upper()}] {contract.get('symbol', 'N/A')} Dev持仓 {dev_hp:.2f}% > 30%，跳过通知")
                        continue
                    security = contract.get("security", {})
                    top_holder = security.get("topHolder", {}).get("value", 0)
                    if top_holder > 30:
                        print(f"⏭️ [{chain.upper()}] {contract.get('symbol', 'N/A')} Top10持仓 {top_holder:.2f}% > 30%，跳过通知")
                        continue
                    filtered_contracts.append(contract)

                new_contracts_count = 0
                tracked_contracts_count = 0
                first_contract_notified = False

                for contract in filtered_contracts:
                    token_address = contract.get("tokenAddress")
                    current_price = float(contract.get("priceUSD", 0))
                    if not token_address or current_price <= 0:
                        continue
                    if should_filter_contract(contract, chain):
                        continue
                    is_new = storage.is_new_contract(token_address)
                    if is_new:
                        storage.add_contract(token_address, current_price, contract)
                    stored_contract = storage.get_contract(token_address)
                    has_trend_notification = stored_contract and stored_contract.get("telegram_message_ids", {})
                    if not has_trend_notification:
                        kol_with_positions, kol_without_positions = load_kol_status(
                            contract,
                            chain,
                            context="趋势通知",
                        )

                        # 获取叙事分析数据（仅首次趋势通知时获取）
                        narrative_data = storage.get_narrative(token_address)
                        if narrative_data is None:
                            try:
                                narrative_response = fetch_narrative(token_address, chain)
                                if narrative_response.get("success"):
                                    history = narrative_response.get("data", {}).get("history", {})
                                    if history:
                                        narrative_data = history.get("story", {})
                                        if narrative_data:
                                            storage.update_narrative(token_address, narrative_data)
                                        else:
                                            storage.mark_narrative_pending(token_address)
                                    else:
                                        storage.mark_narrative_pending(token_address)
                                else:
                                    storage.mark_narrative_pending(token_address)
                            except Exception as e:
                                print(f"⚠️ 获取叙事数据失败: {e}")
                                storage.mark_narrative_pending(token_address)

                        if not is_new:
                            current_market_cap = float(contract.get("marketCapUSD", 0))
                            storage.update_initial_price(token_address, current_price, current_market_cap)

                        msg = format_initial_notification(
                            contract,
                            chain,
                            kol_with_positions,
                            kol_without_positions,
                            narrative_data,
                        )
                        print(msg)
                        print("\n" + "=" * 60 + "\n")

                        if is_new:
                            new_contracts_count += 1

                        if ENABLE_TELEGRAM:
                            image_url = contract.get("imageUrl")
                            if image_url:
                                message_ids = notifier.send_photo_sync(image_url, msg, token_address=token_address, chain=chain)
                            else:
                                message_ids = notifier.send_sync(msg, token_address=token_address, chain=chain)

                            for chat_id, msg_id in message_ids.items():
                                storage.update_telegram_message_id(token_address, chat_id, msg_id)

                        first_contract_notified = True

                    break

                for contract in contracts:
                    token_address = contract.get("tokenAddress")
                    current_price = float(contract.get("priceUSD", 0))

                    if not token_address or current_price <= 0:
                        continue

                    if should_filter_contract(contract, chain):
                        continue

                    if not storage.is_new_contract(token_address):
                        storage.update_price_history(token_address, current_price)
                        check_multipliers(contract, storage, chain)
                        tracked_contracts_count += 1

                # 检查待更新的叙事
                check_pending_narratives(storage, chain)

                if new_contracts_count > 0 or tracked_contracts_count > 0:
                    print(f"📊 [{chain.upper()}] 新合约: {new_contracts_count} | 追踪中: {tracked_contracts_count}")

            print(f"⏳ 等待 {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n👋 机器人已停止")
            if ENABLE_TELEGRAM:
                notifier.stop_bot()
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            print(f"⏳ {CHECK_INTERVAL} 秒后重试...\n")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    monitor_trending()
