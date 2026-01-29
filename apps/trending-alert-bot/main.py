"""趋势通知机器人入口"""

import argparse

from monitor import monitor_trending, normalize_clear_targets


def parse_args():
    parser = argparse.ArgumentParser(description="趋势通知机器人")
    parser.add_argument(
        "-c",
        "--clear-storage",
        metavar="CHAIN[,CHAIN]",
        default="",
        help="启动前清理缓存，可填 'all' 或逗号/空格分隔的链名称",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    clear_targets = normalize_clear_targets(cli_args.clear_storage)
    monitor_trending(clear_targets)
