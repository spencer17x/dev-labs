"""趋势通知机器人入口"""

import argparse

from bot_app import apply_runtime_env, load_runtime_config, validate_runtime_config


def parse_args():
    parser = argparse.ArgumentParser(description="趋势通知机器人")
    parser.add_argument(
        "--bot-config",
        metavar="PATH",
        required=True,
        help="Bot 配置文件路径（JSON）",
    )
    parser.add_argument(
        "--common-config",
        metavar="PATH",
        default="",
        help="通用配置文件路径（JSON，可选）",
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


if __name__ == "__main__":
    cli_args = parse_args()
    runtime_cfg = load_runtime_config(
        bot_config_path=cli_args.bot_config,
        common_config_path=cli_args.common_config or None,
    )
    validate_runtime_config(runtime_cfg)
    apply_runtime_env(runtime_cfg)
    if cli_args.dry_run:
        import os
        os.environ["BOT_DRY_RUN"] = "1"

    from monitor import monitor_trending, normalize_clear_targets

    clear_targets = normalize_clear_targets(cli_args.clear_storage)
    monitor_trending(clear_targets)
