"""趋势通知机器人入口"""

import argparse
import os
import sys

from bot_app import apply_runtime_env, load_runtime_config, validate_runtime_config


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


def parse_args():
    parser = argparse.ArgumentParser(description="趋势通知机器人")
    parser.add_argument(
        "target",
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
    return parser.parse_args()


def _run_monitor(clear_storage: str):
    for module_name in _RUNTIME_MODULE_NAMES:
        sys.modules.pop(module_name, None)

    from monitor import monitor_trending, normalize_clear_targets

    monitor_trending(normalize_clear_targets(clear_storage))


def run(cli_args):
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
