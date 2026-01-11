"""
Telegram 通知测试
运行: python -m tests.test_telegram
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import load_config
from notifier.telegram import TelegramNotifier
from deployer.base import TokenInfo, DeployResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("📢 Telegram 通知测试启动")

    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(f"配置文件错误: {e}")
        return

    telegram_config = config.get("telegram", {})

    if not telegram_config.get("bot_token"):
        logger.error("❌ 未配置 Telegram Bot Token，请在 .env 中设置 TELEGRAM_BOT_TOKEN")
        return

    if not telegram_config.get("chat_id"):
        logger.error("❌ 未配置 Telegram Chat ID，请在 .env 中设置 TELEGRAM_CHAT_ID")
        return

    notifier = TelegramNotifier(telegram_config)

    print("\n选择测试类型:")
    print("1. 发送测试消息")
    print("2. 模拟新推文通知")
    print("3. 模拟代币创建成功通知")
    print("4. 模拟代币创建失败通知")

    choice = input("\n请选择 (1-4): ").strip()

    if choice == "1":
        await notifier._send("🔔 *测试消息*\n\nToken Launcher 通知测试成功！")
        logger.info("✅ 测试消息已发送")

    elif choice == "2":
        await notifier.notify_new_tweet(
            username="elonmusk",
            tweet_text="Just bought some $DOGE! To the moon! 🚀 #crypto #dogecoin"
        )
        logger.info("✅ 新推文通知已发送")

    elif choice == "3":
        token_info = TokenInfo(
            name="Test Coin",
            symbol="TEST",
            description="A test token"
        )
        result = DeployResult(
            success=True,
            token_address="0x1234567890abcdef1234567890abcdef12345678",
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            platform_url="https://four.meme/token/0x1234"
        )
        await notifier.notify_token_created(token_info, result)
        logger.info("✅ 代币创建成功通知已发送")

    elif choice == "4":
        token_info = TokenInfo(
            name="Failed Coin",
            symbol="FAIL",
            description="A failed token"
        )
        result = DeployResult(
            success=False,
            error="Insufficient balance for gas"
        )
        await notifier.notify_token_created(token_info, result)
        logger.info("✅ 代币创建失败通知已发送")

    else:
        logger.error("无效选择")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 测试结束")
