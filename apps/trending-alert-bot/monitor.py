"""监控调度与启动入口。"""

import os
import time
from typing import List, Optional

from chat_storage import ChatStorage
from config import (
    CHAINS,
    CHECK_INTERVAL,
    DRY_RUN,
    ENABLE_TELEGRAM,
    NOTIFICATION_TYPES,
    SILENT_INIT,
    STORAGE_DIR,
    SUMMARY_REPORT_HOURS,
)
from monitor_flow import (
    ensure_chat_storage,
    initialize_storage,
    make_storage_key,
    scan_once,
    send_summary_report,
    should_send_summary_report,
    storage_file_path,
)
from telegram_bot import notifier
from timezone_utils import beijing_now


def normalize_clear_targets(raw_value: Optional[str]) -> List[str]:
    """将用户输入的链名称解析为受支持的链列表。"""
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


def _bootstrap_storages(chain: str, clear_targets: set, storages: dict, active_chats: List[dict]):
    for chat in active_chats:
        chat_id = chat["chat_id"]
        file_path = storage_file_path(chat_id, chain)
        if chain in clear_targets and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ 已清理 {chain.upper()} 本地缓存: {file_path}")

        storage_key = make_storage_key(chat_id, chain)
        storages[storage_key] = ensure_chat_storage(storages, chat_id, chain)
        if SILENT_INIT:
            initialize_storage(storages[storage_key], chain)


def _startup_telegram(chat_storage: ChatStorage):
    if ENABLE_TELEGRAM and not DRY_RUN:
        notifier.start_bot()
        for chat in chat_storage.get_active_chats():
            chat_id = chat["chat_id"]
            mode = chat_storage.get_notification_mode(chat_id)
            mode_map = {"all": "趋势/异动", "trending": "趋势", "anomaly": "异动"}
            mode_desc = mode_map.get(mode, "通知")
            startup_message = f"✅ Bot 已启动，当前群组将接收{mode_desc}通知\n🔔 通知模式: {mode} | 管理员可用 /setmode 切换"
            notifier.send_sync(startup_message, chat_id=chat_id)


def _initial_report_marker() -> int:
    now = beijing_now()
    for hour in SUMMARY_REPORT_HOURS:
        report_hour = (hour - 1) % 24
        if now.hour == report_hour and now.minute == 59:
            return hour
    return -1


def monitor_trending(clear_storage: Optional[List[str]] = None):
    chains = CHAINS
    os.makedirs(STORAGE_DIR, exist_ok=True)

    clear_targets = set(clear_storage or [])
    if "all" in clear_targets:
        clear_targets = set(chains)

    chat_storage = ChatStorage()
    storages = {}

    print(f"🤖 Bot 启动 | 链: {', '.join([c.upper() for c in chains])} | 间隔: {CHECK_INTERVAL}s")
    print(f"🧩 Runtime | data_dir: {STORAGE_DIR}")
    print(f"📊 策略: {', '.join(NOTIFICATION_TYPES)} + 整数倍通知(所有符合条件)")
    print(f"📱 Telegram: {'✓' if ENABLE_TELEGRAM else '✗'}")
    if DRY_RUN:
        print("🧪 Dry-run: 启用（仅扫描一轮，不发送消息）")

    _startup_telegram(chat_storage)
    print()

    active_chats = chat_storage.get_active_chats()
    for chain in chains:
        _bootstrap_storages(chain, clear_targets, storages, active_chats)

    if SILENT_INIT:
        print(f"\n⏳ 等待 {CHECK_INTERVAL} 秒后开始监控...\n")
        time.sleep(CHECK_INTERVAL)

    last_summary_hour = _initial_report_marker()
    last_cleanup_day = beijing_now().day

    while True:
        try:
            scan_time = beijing_now().strftime("%H:%M:%S")
            print(f"\n🔍 [{scan_time}] 扫描趋势榜...")

            chat_storage = ChatStorage()
            active_chats = chat_storage.get_active_chats()
            if not active_chats:
                print("⚠️  当前没有活跃聊天，跳过本轮")
                time.sleep(CHECK_INTERVAL)
                continue

            current_time = beijing_now()
            if current_time.day != last_cleanup_day and current_time.hour == 0 and current_time.minute >= 5:
                print("\n🧹 开始清理旧数据...")
                total_deleted = 0
                for storage_key, storage in storages.items():
                    deleted = storage.cleanup_old_data(days_to_keep=7)
                    if deleted > 0:
                        chain = storage_key.split(":", 1)[0] if ":" in storage_key else (chains[0] if chains else "unknown")
                        print(f"  • {chain.upper()}: 清理 {deleted} 个合约")
                        total_deleted += deleted
                if total_deleted > 0:
                    print(f"✅ 清理完成，共删除 {total_deleted} 个合约\n")
                else:
                    print("✅ 无需清理\n")
                last_cleanup_day = current_time.day

            if should_send_summary_report(last_summary_hour):
                now = beijing_now()
                report_time_hour = -1
                for hour in SUMMARY_REPORT_HOURS:
                    report_hour = (hour - 1) % 24
                    if now.hour == report_hour and now.minute == 59:
                        report_time_hour = hour
                        break
                if report_time_hour != -1:
                    print(f"\n📊 发送 {report_time_hour}:00 汇总报告...")
                    send_summary_report(storages)
                    last_summary_hour = report_time_hour

            found_any_anomaly = False
            for chain in chains:
                print(f"🔎 扫描链: {chain.upper()}")
                found_any_anomaly = scan_once(chain, active_chats, storages, chat_storage) or found_any_anomaly

            print(f"⏳ 等待 {CHECK_INTERVAL}s...")
            if DRY_RUN:
                print("🧪 Dry-run 完成，退出")
                break
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
