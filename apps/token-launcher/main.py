"""
Token Launcher - 监听推特并自动在BSC上创建代币
"""

import asyncio
import logging
from config.loader import load_config
from twitter.listener import TwitterListener
from deployer.four_meme import FourMemeDeployer
from notifier.telegram import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    config = load_config()

    # 初始化组件
    twitter_listener = TwitterListener(config["twitter"])
    deployer = FourMemeDeployer(config["four_meme"])
    notifier = TelegramNotifier(config["telegram"])

    logger.info("Token Launcher started")

    # TODO: 主循环逻辑
    # 1. 监听推特
    # 2. 分析推文提取关键词
    # 3. 调用 four.meme 创建代币
    # 4. 发送通知

    await twitter_listener.start()


if __name__ == "__main__":
    asyncio.run(main())
