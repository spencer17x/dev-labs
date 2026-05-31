#!/usr/bin/env python3
"""
Telegram Forwarder Bot
----------------------
Entry point for the bot application
"""

import asyncio
import argparse
import logging
import os
from config import load_config, ConfigValidator
from core import TelegramForwarderBot

# 从环境变量获取日志级别，默认为 INFO
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=log_level
)

logger = logging.getLogger(__name__)


def parse_args(argv=None):
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Telegram 消息转发机器人")
    parser.add_argument("--config", help="转发规则配置文件路径")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="只校验配置文件，不连接 Telegram、不启动监听",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="覆盖 LOG_LEVEL 环境变量",
    )
    return parser.parse_args(argv)


async def main(argv=None):
    """主函数"""
    args = parse_args(argv)
    if args.log_level:
        logging.getLogger().setLevel(getattr(logging, args.log_level))

    # 加载配置
    config = load_config(args.config)

    if args.check_config:
        ConfigValidator.validate(config, require_credentials=False)
        logger.info("配置校验通过: %s", config.config_path)
        return

    # 创建机器人实例
    bot = TelegramForwarderBot(config)

    # 初始化
    if not await bot.initialize():
        logger.error("机器人初始化失败")
        return

    # 运行
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在退出...")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
