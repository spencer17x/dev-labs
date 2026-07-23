"""趋势通知机器人入口"""

import argparse
import os
import sys

from bot_app import apply_runtime_env, load_runtime_config, validate_runtime_config
from storage_admin import clear_all_notification_data

_RUNTIME_MODULE_NAMES = (
    "monitor",
    "monitor_flow",
    "telegram_bot",
    "storage",
    "chat_storage",
    "db_storage",
    "narrative_service",
    "narrative_storage",
    "narrative_provider",
    "notifier",
    "config",
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="趋势通知机器人")
    parser.add_argument(
        "target",
        nargs="?",
        choices=["bsc", "sol", "base", "eth", "robin", "multi"],
        help="Bot 目标（bsc/sol/base/eth/robin/multi）",
    )
    parser.add_argument(
        "-c",
        "--clear-storage",
        metavar="CHAIN[,CHAIN]",
        default="",
        help="启动前清理缓存，可填 'all' 或逗号/空格分隔的链名称",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只执行一轮扫描并打印，不发送 Telegram 消息",
    )
    parser.add_argument(
        "--clear-all-notification-data",
        action="store_true",
        help="备份并清理所有单链 Bot 与 multi Bot 的合约通知跟踪数据后退出",
    )
    args = parser.parse_args(argv)

    if args.clear_all_notification_data:
        if args.target or args.clear_storage or args.dry_run:
            parser.error(
                "--clear-all-notification-data 不能与 target、--clear-storage "
                "或 --dry-run 同时使用"
            )
    elif not args.target:
        parser.error("必须提供 target，或使用 --clear-all-notification-data")

    return args


def _run_monitor(clear_storage: str):
    for module_name in _RUNTIME_MODULE_NAMES:
        sys.modules.pop(module_name, None)

    from monitor import monitor_trending, normalize_clear_targets

    monitor_trending(normalize_clear_targets(clear_storage))


def _run_clear_all_notification_data():
    print("⚠️ 请先停止所有 trending-alert Bot，避免运行中重新写入数据")
    print("🧹 清理所有单链 Bot 与 multi Bot 的合约通知跟踪数据...")
    results = clear_all_notification_data()
    total_deleted = 0
    cleared_databases = 0

    for result in results:
        if result.status == "missing":
            print(f"↪️  {result.target}: 数据库不存在，跳过")
            continue
        if result.status == "missing_schema":
            print(f"↪️  {result.target}: contracts 表不存在，跳过")
            continue
        if result.status == "empty":
            print(f"✓ {result.target}: 无合约通知数据")
            continue

        total_deleted += result.deleted_contracts
        cleared_databases += 1
        print(
            f"✅ {result.target}: 清理 {result.deleted_contracts} 条合约记录 | "
            f"备份: {result.backup_path}"
        )

    print(
        f"✅ 清理完成：{cleared_databases} 个数据库，"
        f"{total_deleted} 条合约记录"
    )


def run(cli_args):
    if getattr(cli_args, "clear_all_notification_data", False):
        _run_clear_all_notification_data()
        return

    runtime_cfg = load_runtime_config(cli_args.target)
    validate_runtime_config(runtime_cfg)
    apply_runtime_env(runtime_cfg)
    os.environ["BOT_DRY_RUN"] = "1" if cli_args.dry_run else "0"

    if cli_args.dry_run:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="trending-alert-dry-run-") as data_dir:
            os.environ["BOT_DATA_DIR"] = data_dir
            _run_monitor(cli_args.clear_storage)
        return

    _run_monitor(cli_args.clear_storage)


if __name__ == "__main__":
    run(parse_args())
