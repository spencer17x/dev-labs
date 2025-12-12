#!/usr/bin/env python3
"""
Telegram Forwarder Bot
----------------------
Entry point for the bot application
"""
import asyncio
import logging
import os
from config import load_config
from core import TelegramForwarderBot

# 从环境变量获取日志级别，默认为 INFO
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=log_level
)

logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    # 加载配置
    config = load_config()

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
