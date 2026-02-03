"""趋势通知主流程与监控逻辑"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from api import fetch_trending, fetch_kol_holders
from chat_storage import ChatSettingsStore, ChatStorage
from config import (
    CHAINS,
    CHECK_INTERVAL,
    CHAIN_ALLOWLISTS,
    ENABLE_TELEGRAM,
    SILENT_INIT,
    STORAGE_DIR,
    SUMMARY_REPORT_HOURS,
    SUMMARY_TOP_N,
    NOTIFY_COOLDOWN_HOURS,
)
from notifier import (
    format_initial_notification,
    format_multiplier_notification,
    format_summary_report,
)
from storage import ContractStorage
from telegram_bot import notifier
from timezone_utils import beijing_now, beijing_today_start, parse_time_to_beijing


def normalize_clear_targets(raw_value: Optional[str]) -> List[str]:
    """将用户输入的链名称解析为受支持的链列表"""

    if not raw_value:
        return []

    normalized_input = raw_value.strip().lower()
    if normalized_input == "all":
        return list(CHAINS)

    selections: List[str] = []
    seen = set()

    chunks = normalized_input.replace(",", " ").split()
    for chunk in chunks:
        if chunk not in CHAINS:
            print(f"⚠️ 忽略未知链: {chunk}")
            continue

        if chunk in seen:
            continue

        selections.append(chunk)
        seen.add(chunk)

    return selections


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def split_kol_positions(kol_list: Optional[List[dict]]) -> Tuple[List[dict], List[dict]]:
    """仅保留持仓比例 >= 0.1% 的KOL"""
    holders: list = []
    leavers: list = []

    if not kol_list:
        return holders, leavers

    for kol in kol_list:
        hold_percent = _safe_float(kol.get("holdPercent"))
        if hold_percent >= 0.1:
            holders.append(kol)

    return holders, leavers


def fetch_kol_list(contract: dict, chain: str, context: str = "") -> List[dict]:
    token_address = contract.get("tokenAddress")
    pair_address = contract.get("pairAddress", "")

    if not token_address:
        return []

    try:
        kol_response = fetch_kol_holders(token_address, pair_address, chain)
        return kol_response.get("data", []) or []
    except Exception as e:
        prefix = f"[{chain.upper()}] " if chain else ""
        context_text = f"{context} " if context else ""
        symbol = contract.get("symbol", "N/A")
        print(f"⚠️ {prefix}{symbol} {context_text}获取 KOL 数据失败: {e}")
        return []


def load_kol_status(contract: dict, chain: str, context: str = "") -> Tuple[List[dict], List[dict]]:
    kol_list = fetch_kol_list(contract, chain, context=context)
    return split_kol_positions(kol_list)


def is_anomaly_contract(contract: dict) -> bool:
    """判断是否为异动：合约创建时间早于北京时间当天 00:00 或不可用"""
    create_time = contract.get("createTime")
    if not create_time:
        return True
    try:
        create_dt = datetime.fromtimestamp(int(create_time) / 1000, tz=beijing_now().tzinfo)
        return create_dt.replace(tzinfo=None) < beijing_today_start().replace(tzinfo=None)
    except (TypeError, ValueError):
        return True


def check_multipliers(
    contract: dict,
    storage: ContractStorage,
    chain: str = "",
    chat_id: Optional[int] = None,
):
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
            notifier.send_with_reply_sync(msg, token_address, storage, chat_id=chat_id, chain=chain)

        # 存储实际倍数（带小数），用于汇总报告显示真实最高倍数
        storage.update_notified_multiplier(token_address, multiplier)


def is_on_cooldown(storage: ContractStorage, token_address: str, hours: int = NOTIFY_COOLDOWN_HOURS) -> bool:
    last_notify_time = storage.get_last_notify_time(token_address)
    if not last_notify_time:
        return False
    try:
        last_dt = parse_time_to_beijing(last_notify_time).replace(tzinfo=None)
        now_dt = beijing_now().replace(tzinfo=None)
        return (now_dt - last_dt) < timedelta(hours=hours)
    except Exception:
        return False


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
    if not storages:
        return

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

    # 按 chat_id 分组统计
    chat_map: Dict[int, Dict[str, ContractStorage]] = {}
    for storage_key, storage in storages.items():
        chain, chat_id_str = storage_key.split(":", 1)
        chat_id = int(chat_id_str)
        chat_map.setdefault(chat_id, {})[chain] = storage

    for chat_id, chain_storages in chat_map.items():
        chain_stats = {}

        for chain, storage in chain_storages.items():
            today_contracts = storage.get_today_trend_contracts()

            # 初始化链统计数据
            if chain not in chain_stats:
                chain_stats[chain] = {
                    "trend_count": 0,
                    "total_multiplier_contracts": 0,
                    "win_count": 0,
                    "top_contracts": [],
                    "multiplier_distribution": {
                        "2x": 0,
                        "5x": 0,
                        "10x_plus": 0
                    }
                }
            chain_stats[chain]["trend_count"] += len(today_contracts)

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

                    chain_stats[chain]["top_contracts"].append(contract_item)

            # 对每个链的合约按倍数排序，取前N
            chain_stats[chain]["top_contracts"].sort(key=lambda x: x["multiplier"], reverse=True)
            chain_stats[chain]["top_contracts"] = chain_stats[chain]["top_contracts"][:SUMMARY_TOP_N]

        msg = format_summary_report(chain_stats, next_report_time_str)
        print("\n" + "=" * 60)
        print(msg)
        print("=" * 60 + "\n")

        if ENABLE_TELEGRAM:
            notifier.send_sync(msg, chat_id=chat_id)


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


def monitor_trending(clear_storage: Optional[List[str]] = None):
    chains = CHAINS
    os.makedirs(STORAGE_DIR, exist_ok=True)

    clear_targets = set(clear_storage or [])
    if "all" in clear_targets:
        clear_targets = set(chains)

    chat_storage = ChatStorage()
    chat_settings = ChatSettingsStore()
    storages = {}

    print(f"🤖 Bot 启动 | 链: {', '.join([c.upper() for c in chains])} | 间隔: {CHECK_INTERVAL}s")
    print(f"📊 策略: 趋势通知(榜一) + 整数倍通知(所有符合条件)")
    print(f"📱 Telegram: {'✓' if ENABLE_TELEGRAM else '✗'}")

    if ENABLE_TELEGRAM:
        notifier.start_bot()
        for chat in chat_storage.get_active_chats():
            chat_id = chat["chat_id"]
            mode = chat_settings.get_mode(chat_id, "trend")
            if mode == "trend":
                mode_label = "趋势通知"
            elif mode == "anomaly":
                mode_label = "异动通知"
            else:
                mode_label = "趋势 + 异动通知"
            startup_message = f"✅ Bot 已启动，当前群组模式：{mode_label}"
            notifier.send_sync(startup_message, chat_id=chat_id)

    print()

    active_chats = chat_storage.get_active_chats()
    for chat in active_chats:
        chat_id = chat["chat_id"]
        for chain in chains:
            storage_file = os.path.join(STORAGE_DIR, f"contracts_data_{chain}_{chat_id}.json")
            if chain in clear_targets and os.path.exists(storage_file):
                os.remove(storage_file)
                print(f"🗑️ 已清理 {chain.upper()} 本地缓存: {storage_file}")
            storage_key = f"{chain}:{chat_id}"
            storages[storage_key] = ContractStorage(storage_file)
            if SILENT_INIT:
                initialize_storage(storages[storage_key], chain)

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
            # 重新加载聊天与设置，避免运行中新增群组无法被识别
            chat_storage = ChatStorage()
            chat_settings = ChatSettingsStore()
            active_chats = chat_storage.get_active_chats()
            if not active_chats:
                print("⚠️  当前没有活跃聊天，跳过本轮")
                time.sleep(CHECK_INTERVAL)
                continue

            # 每天 00:05 自动清理旧数据（北京时间）
            current_time = beijing_now()
            if current_time.day != last_cleanup_day and current_time.hour == 0 and current_time.minute >= 5:
                print("\n🧹 开始清理旧数据...")
                total_deleted = 0
                for storage_key, storage in storages.items():
                    deleted = storage.cleanup_old_data(days_to_keep=7)
                    if deleted > 0:
                        chain = storage_key.split(":", 1)[0]
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
                # 汇总报告按群组独立统计
                send_summary_report(storages)
                last_summary_hour = report_time_hour

            found_any_anomaly = False
            for chain in chains:
                response = fetch_trending(chain=chain)
                contracts = response.get("data", [])

                filtered_contracts = []
                for contract in contracts:
                    launch_from = contract.get("launchFrom") or ""
                    if not launch_from:
                        continue
                    audit_info = contract.get("auditInfo", {})
                    new_hp = audit_info.get("newHp", 0)
                    if new_hp > 30:
                        continue
                    insider_hp = audit_info.get("insiderHp", 0)
                    if insider_hp > 30:
                        continue
                    bundle_hp = audit_info.get("bundleHp", 0)
                    if bundle_hp > 30:
                        continue
                    dev_hp = audit_info.get("devHp", 0)
                    if dev_hp > 30:
                        continue
                    security = contract.get("security", {})
                    honey_pot = security.get("honeyPot", {}).get("value", False)
                    if honey_pot:
                        continue
                    filtered_contracts.append(contract)

                trend_contract = None
                anomaly_contract = None
                for contract in filtered_contracts:
                    token_address = contract.get("tokenAddress")
                    current_price = float(contract.get("priceUSD", 0))
                    if not token_address or current_price <= 0:
                        continue
                    if should_filter_contract(contract, chain):
                        continue

                    is_anomaly = is_anomaly_contract(contract)
                    if is_anomaly and anomaly_contract is not None:
                        continue
                    if not is_anomaly and trend_contract is not None:
                        continue

                    kol_list = fetch_kol_list(contract, chain, context="筛选KOL")
                    if not kol_list:
                        continue

                    if is_anomaly:
                        anomaly_contract = (contract, *split_kol_positions(kol_list))
                    else:
                        trend_contract = (contract, *split_kol_positions(kol_list))

                    if trend_contract and anomaly_contract:
                        break

                if anomaly_contract is not None:
                    found_any_anomaly = True

                for chat in active_chats:
                    chat_id = chat["chat_id"]
                    mode = chat_settings.get_mode(chat_id, "trend")
                    storage_key = f"{chain}:{chat_id}"
                    if storage_key not in storages:
                        storage_file = os.path.join(STORAGE_DIR, f"contracts_data_{chain}_{chat_id}.json")
                        storages[storage_key] = ContractStorage(storage_file)
                        if SILENT_INIT:
                            initialize_storage(storages[storage_key], chain)

                    storage = storages[storage_key]
                    new_contracts_count = 0
                    tracked_contracts_count = 0

                    def _send_candidate(contract: dict, kol_with_positions: List[dict], kol_without_positions: List[dict], is_anomaly: bool):
                        nonlocal new_contracts_count
                        token_address = contract.get("tokenAddress")
                        current_price = float(contract.get("priceUSD", 0))
                        if not token_address or current_price <= 0:
                            return
                        is_new = storage.is_new_contract(token_address)
                        if is_new:
                            storage.add_contract(token_address, current_price, contract)
                        stored_contract = storage.get_contract(token_address)
                        has_trend_notification = stored_contract and stored_contract.get("telegram_message_ids", {})
                        if has_trend_notification:
                            return
                        if is_on_cooldown(storage, token_address):
                            return

                        if not is_new:
                            current_market_cap = float(contract.get("marketCapUSD", 0))
                            storage.update_initial_price(token_address, current_price, current_market_cap)

                        msg = format_initial_notification(
                            contract,
                            chain,
                            kol_with_positions,
                            kol_without_positions,
                            is_anomaly,
                        )
                        print(msg)
                        print("\n" + "=" * 60 + "\n")

                        if is_new:
                            new_contracts_count += 1

                        if ENABLE_TELEGRAM:
                            image_url = contract.get("imageUrl")
                            if image_url:
                                print(
                                    f"🖼️ [{chain.upper()}] 发送图片: {contract.get('symbol', 'N/A')} | "
                                    f"{token_address} | url={image_url}"
                                )
                                message_ids = notifier.send_photo_sync(
                                    image_url,
                                    msg,
                                    chat_id=chat_id,
                                    token_address=token_address,
                                    chain=chain,
                                )
                                if not message_ids:
                                    print(
                                        f"↪️ [{chain.upper()}] 图片发送失败，降级为文本: "
                                        f"{contract.get('symbol', 'N/A')} | {token_address}"
                                    )
                                    message_ids = notifier.send_sync(
                                        msg,
                                        chat_id=chat_id,
                                        token_address=token_address,
                                        chain=chain,
                                    )
                            else:
                                message_ids = notifier.send_sync(
                                    msg,
                                    chat_id=chat_id,
                                    token_address=token_address,
                                    chain=chain,
                                )

                            for _, msg_id in message_ids.items():
                                storage.update_telegram_message_id(token_address, chat_id, msg_id)
                            if message_ids:
                                storage.update_last_notify_time(token_address)

                    if mode in ["trend", "both"] and trend_contract:
                        contract, kol_with_positions, kol_without_positions = trend_contract
                        _send_candidate(contract, kol_with_positions, kol_without_positions, False)
                    if mode in ["anomaly", "both"] and anomaly_contract:
                        contract, kol_with_positions, kol_without_positions = anomaly_contract
                        _send_candidate(contract, kol_with_positions, kol_without_positions, True)

                    for contract in contracts:
                        token_address = contract.get("tokenAddress")
                        current_price = float(contract.get("priceUSD", 0))

                        if not token_address or current_price <= 0:
                            continue

                        if should_filter_contract(contract, chain):
                            continue

                        if not storage.is_new_contract(token_address):
                            storage.update_price_history(token_address, current_price)
                            check_multipliers(contract, storage, chain, chat_id=chat_id)
                            tracked_contracts_count += 1

                    if new_contracts_count > 0 or tracked_contracts_count > 0:
                        print(f"📊 [{chain.upper()}] 新合约: {new_contracts_count} | 追踪中: {tracked_contracts_count}")

            print(f"⏳ 等待 {CHECK_INTERVAL}s...")
            time.sleep(CHECK_INTERVAL)

            if not found_any_anomaly:
                print("ℹ️ 本轮未找到异动数据")

        except KeyboardInterrupt:
            print("\n\n👋 机器人已停止")
            if ENABLE_TELEGRAM:
                notifier.stop_bot()
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            print(f"⏳ {CHECK_INTERVAL} 秒后重试...\n")
            time.sleep(CHECK_INTERVAL)
