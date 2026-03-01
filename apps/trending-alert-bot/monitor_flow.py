"""监控业务流程与通知编排。"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from api import fetch_trending, fetch_kol_holders
from config import (
    CHAINS,
    CHAIN_ALLOWLISTS,
    DRY_RUN,
    ENABLE_TELEGRAM,
    MULTIPLIER_CONFIRMATIONS,
    NOTIFICATION_TYPES,
    NOTIFY_COOLDOWN_HOURS,
    STORAGE_DIR,
    SUMMARY_REPORT_HOURS,
    SUMMARY_TOP_N,
)
from notifier import (
    format_initial_notification,
    format_multiplier_notification,
    format_summary_report,
)
from storage import ContractStorage
from telegram_bot import notifier
from timezone_utils import beijing_now, beijing_today_start, parse_time_to_beijing


def make_storage_key(chat_id: int, chain: str = "") -> str:
    if chain:
        return f"{chain}:{chat_id}"
    return str(chat_id)


def storage_file_path(chat_id: int, chain: str = "") -> str:
    if chain:
        return os.path.join(STORAGE_DIR, f"contracts_data_{chain}_{chat_id}.json")
    return os.path.join(STORAGE_DIR, f"contracts_data_{chat_id}.json")


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_dict(value) -> Dict:
    if isinstance(value, dict):
        return value
    return {}


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

    telegram_message_ids = stored_contract.get("telegram_message_ids", {})
    has_real_notification = any(msg_id != -1 for msg_id in telegram_message_ids.values())
    if not has_real_notification:
        return

    initial_price = stored_contract["initial_price"]
    if initial_price <= 0:
        return

    multiplier = current_price / initial_price
    current_integer_multiplier = int(multiplier)

    if current_integer_multiplier < 2:
        storage.clear_pending_multiplier(token_address)
        return

    max_notified_integer = storage.get_max_notified_integer_multiplier(token_address)
    if current_integer_multiplier <= max_notified_integer:
        storage.clear_pending_multiplier(token_address)
        return

    pending = storage.get_pending_multiplier(token_address) or {}
    pending_int = pending.get("multiplier_int")
    pending_count = pending.get("count", 0)

    if pending_int == current_integer_multiplier:
        pending_count += 1
    else:
        pending_int = current_integer_multiplier
        pending_count = 1

    if pending_count < MULTIPLIER_CONFIRMATIONS:
        storage.update_pending_multiplier(token_address, pending_int, pending_count)
        return

    storage.clear_pending_multiplier(token_address)

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

    if ENABLE_TELEGRAM and not DRY_RUN:
        notifier.send_with_reply_sync(msg, token_address, storage, chat_id=chat_id, chain=chain)

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

    for contract in contracts:
        token_address = contract.get("tokenAddress")
        current_price = float(contract.get("priceUSD", 0))

        if not token_address or current_price <= 0:
            continue
        if should_filter_contract(contract, chain):
            continue

        is_new = storage.is_new_contract(token_address)
        if first_contract_address is None:
            first_contract_address = token_address

        if is_new:
            storage.add_contract(token_address, current_price, contract)
            loaded_count += 1

    if first_contract_address:
        stored_contract = storage.get_contract(first_contract_address)
        if stored_contract:
            telegram_message_ids = stored_contract.get("telegram_message_ids", {})
            has_real_notification = any(msg_id != -1 for msg_id in telegram_message_ids.values())
            if not has_real_notification and not telegram_message_ids:
                storage.update_telegram_message_id(first_contract_address, -1, -1)

    if loaded_count > 0:
        print(f"✅ [{chain.upper()}] 初始化完成，加载 {loaded_count} 个新合约")
    else:
        print(f"⚠️  [{chain.upper()}] 未找到新的符合条件的合约")


def _passes_base_filters(contract: dict) -> bool:
    launch_from = contract.get("launchFrom") or ""
    if not launch_from:
        return False
    audit_info = _safe_dict(contract.get("auditInfo"))
    if audit_info.get("newHp", 0) > 30:
        return False
    if audit_info.get("insiderHp", 0) > 30:
        return False
    if audit_info.get("bundleHp", 0) > 30:
        return False
    if audit_info.get("devHp", 0) > 30:
        return False
    security = _safe_dict(contract.get("security"))
    honey_pot = _safe_dict(security.get("honeyPot"))
    if honey_pot.get("value", False):
        return False
    return True


def _pick_trend_and_anomaly_contract(
    contracts: List[dict],
    chain: str,
) -> Tuple[Optional[Tuple[dict, List[dict], List[dict]]], Optional[Tuple[dict, List[dict], List[dict]]]]:
    enable_trending = "trending" in NOTIFICATION_TYPES
    enable_anomaly = "anomaly" in NOTIFICATION_TYPES
    trend_contract = None
    anomaly_contract = None

    for contract in contracts:
        token_address = contract.get("tokenAddress")
        current_price = float(contract.get("priceUSD", 0))
        if not token_address or current_price <= 0:
            continue
        if should_filter_contract(contract, chain):
            continue

        is_anomaly = is_anomaly_contract(contract)
        if is_anomaly:
            if not enable_anomaly or anomaly_contract is not None:
                continue
        else:
            if not enable_trending or trend_contract is not None:
                continue

        if trend_contract is not None and anomaly_contract is not None:
            continue

        kol_list = fetch_kol_list(contract, chain, context="筛选KOL")
        if not kol_list:
            continue

        candidate = (contract, *split_kol_positions(kol_list))
        if is_anomaly:
            anomaly_contract = candidate
        else:
            trend_contract = candidate

        if trend_contract and anomaly_contract:
            break

    return trend_contract, anomaly_contract


def ensure_chat_storage(
    storages: Dict[str, ContractStorage],
    chat_id: int,
    chain: str,
) -> ContractStorage:
    storage_key = make_storage_key(chat_id, chain)
    if storage_key not in storages:
        storages[storage_key] = ContractStorage(storage_file_path(chat_id, chain))
    return storages[storage_key]


def _send_candidate_notification(
    storage: ContractStorage,
    chat_id: int,
    chain: str,
    contract: dict,
    kol_with_positions: List[dict],
    kol_without_positions: List[dict],
    is_anomaly: bool,
) -> int:
    token_address = contract.get("tokenAddress")
    current_price = float(contract.get("priceUSD", 0))
    if not token_address or current_price <= 0:
        return 0

    is_new = storage.is_new_contract(token_address)
    if is_new:
        storage.add_contract(token_address, current_price, contract)

    stored_contract = storage.get_contract(token_address)
    has_trend_notification = stored_contract and stored_contract.get("telegram_message_ids", {})
    if has_trend_notification:
        return 0
    if is_on_cooldown(storage, token_address):
        return 0

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

    if ENABLE_TELEGRAM and not DRY_RUN:
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

    return 1 if is_new else 0


def _process_chat_contracts(
    storage: ContractStorage,
    chat_id: int,
    chain: str,
    contracts: List[dict],
    trend_contract: Optional[Tuple[dict, List[dict], List[dict]]],
    anomaly_contract: Optional[Tuple[dict, List[dict], List[dict]]],
):
    new_contracts_count = 0
    tracked_contracts_count = 0

    if trend_contract:
        contract, kol_with_positions, kol_without_positions = trend_contract
        new_contracts_count += _send_candidate_notification(
            storage,
            chat_id,
            chain,
            contract,
            kol_with_positions,
            kol_without_positions,
            False,
        )
    if anomaly_contract:
        contract, kol_with_positions, kol_without_positions = anomaly_contract
        new_contracts_count += _send_candidate_notification(
            storage,
            chat_id,
            chain,
            contract,
            kol_with_positions,
            kol_without_positions,
            True,
        )

    for contract in contracts:
        token_address = contract.get("tokenAddress")
        current_price = float(contract.get("priceUSD", 0))
        if not token_address or current_price <= 0:
            continue
        if should_filter_contract(contract, chain):
            continue
        if not storage.is_new_contract(token_address):
            check_multipliers(contract, storage, chain, chat_id=chat_id)
            tracked_contracts_count += 1

    if new_contracts_count > 0 or tracked_contracts_count > 0:
        print(f"📊 [{chain.upper()}] 新合约: {new_contracts_count} | 追踪中: {tracked_contracts_count}")


def _next_report_time_str(now: datetime) -> str:
    current_hour = now.hour
    current_minute = now.minute
    next_report_hour = None

    for hour in SUMMARY_REPORT_HOURS:
        if hour > current_hour or (hour == current_hour and current_minute < 59):
            next_report_hour = hour
            break

    if next_report_hour is None:
        next_report_hour = SUMMARY_REPORT_HOURS[0]
        next_report_time = now.replace(hour=next_report_hour, minute=59, second=0, microsecond=0)
        next_report_time += timedelta(days=1)
    else:
        next_report_time = now.replace(hour=next_report_hour, minute=59, second=0, microsecond=0)

    return next_report_time.strftime("%Y-%m-%d %H:%M")


def _load_latest_contract_map(chain: str) -> Dict[str, dict]:
    try:
        latest_contracts = fetch_trending(chain=chain).get("data", [])
        return {c.get("tokenAddress"): c for c in latest_contracts if c.get("tokenAddress")}
    except Exception as e:
        print(f"❌ 获取 {chain} 链合约数据失败: {e}")
        return {}


def _fallback_contract_data(token_address: str, stored_data: dict) -> dict:
    return {
        "tokenAddress": token_address,
        "symbol": stored_data.get("symbol", "N/A"),
        "name": stored_data.get("name", "N/A"),
        "priceUSD": stored_data.get("initial_price", 0),
        "marketCapUSD": stored_data.get("initial_market_cap", 0),
    }


def _build_chain_stats(
    storage: ContractStorage,
    chain: str,
    latest_contract_map: Dict[str, dict],
) -> Dict[str, dict]:
    today_contracts = storage.get_today_trend_contracts()
    stats = {
        "trend_count": len(today_contracts),
        "total_multiplier_contracts": 0,
        "win_count": 0,
        "top_contracts": [],
        "multiplier_distribution": {"2x": 0, "5x": 0, "10x_plus": 0},
    }

    for item in today_contracts:
        token_address = item["token_address"]
        stored_data = item["data"]
        notified_multipliers = stored_data.get("notified_multipliers", [])
        if not notified_multipliers:
            continue

        max_multiplier = max(notified_multipliers)
        stats["total_multiplier_contracts"] += 1
        max_int_multiplier = int(max_multiplier)
        if max_int_multiplier >= 10:
            stats["multiplier_distribution"]["10x_plus"] += 1
            stats["win_count"] += 1
        elif max_int_multiplier >= 5:
            stats["multiplier_distribution"]["5x"] += 1
        elif max_int_multiplier >= 2:
            stats["multiplier_distribution"]["2x"] += 1

        contract_data = latest_contract_map.get(token_address)
        if not contract_data:
            contract_data = _fallback_contract_data(token_address, stored_data)

        stats["top_contracts"].append(
            {
                "contract": contract_data,
                "stored_data": stored_data,
                "multiplier": max_multiplier,
                "chain": chain,
            }
        )

    stats["top_contracts"].sort(key=lambda x: x["multiplier"], reverse=True)
    stats["top_contracts"] = stats["top_contracts"][:SUMMARY_TOP_N]
    return {chain: stats}


def scan_once(chain: str, active_chats: List[dict], storages: Dict[str, ContractStorage]) -> bool:
    response = fetch_trending(chain=chain)
    contracts = response.get("data", [])
    filtered_contracts = [contract for contract in contracts if _passes_base_filters(contract)]
    trend_contract, anomaly_contract = _pick_trend_and_anomaly_contract(filtered_contracts, chain)

    for chat in active_chats:
        chat_id = chat["chat_id"]
        storage = ensure_chat_storage(storages, chat_id, chain)
        _process_chat_contracts(
            storage,
            chat_id,
            chain,
            contracts,
            trend_contract,
            anomaly_contract,
        )

    return anomaly_contract is not None


def send_summary_report(storages: dict):
    if not storages:
        return

    now = beijing_now()
    next_report_time_str = _next_report_time_str(now)
    chain_latest_map: Dict[str, Dict[str, dict]] = {}
    chat_chain_stats: Dict[int, Dict[str, dict]] = {}

    for storage_key, storage in storages.items():
        if ":" in storage_key:
            chain, chat_id_raw = storage_key.split(":", 1)
            chat_id = int(chat_id_raw)
        else:
            chain = CHAINS[0] if CHAINS else "unknown"
            chat_id = int(storage_key)

        if chain not in chain_latest_map:
            chain_latest_map[chain] = _load_latest_contract_map(chain)
        chain_stats = _build_chain_stats(storage, chain, chain_latest_map[chain])
        if chat_id not in chat_chain_stats:
            chat_chain_stats[chat_id] = {}
        chat_chain_stats[chat_id].update(chain_stats)

    for chat_id, chain_stats in chat_chain_stats.items():
        msg = format_summary_report(chain_stats, next_report_time_str)
        print("\n" + "=" * 60)
        print(msg)
        print("=" * 60 + "\n")

        if ENABLE_TELEGRAM and not DRY_RUN:
            notifier.send_sync(msg, chat_id=chat_id)


def should_send_summary_report(last_report_hour: int) -> bool:
    now = beijing_now()
    current_hour = now.hour
    current_minute = now.minute

    for hour in SUMMARY_REPORT_HOURS:
        report_hour = (hour - 1) % 24
        if current_hour == report_hour and current_minute == 59 and hour != last_report_hour:
            return True

    return False
