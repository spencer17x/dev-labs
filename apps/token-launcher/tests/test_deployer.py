"""
发币测试
运行: python -m tests.test_deployer
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import load_config
from deployer.four_meme import FourMemeDeployer
from deployer.base import TokenInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 发币测试启动")

    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(f"配置文件错误: {e}")
        return

    four_meme_config = config.get("four_meme", {})

    if not four_meme_config.get("private_key"):
        logger.error("❌ 未配置钱包私钥，请在 .env 中设置 FOUR_MEME_PRIVATE_KEY")
        return

    # 测试代币信息
    test_token = TokenInfo(
        name="Test Token",
        symbol="TEST",
        description="This is a test token created by token-launcher",
        image_url="",
        twitter_url="https://twitter.com/test",
        website_url="https://test.com"
    )

    logger.info("=" * 50)
    logger.info("📋 测试代币信息:")
    logger.info(f"  名称: {test_token.name}")
    logger.info(f"  符号: {test_token.symbol}")
    logger.info(f"  描述: {test_token.description}")
    logger.info(f"  链: {four_meme_config.get('chain', 'bsc')}")
    logger.info("=" * 50)

    # 确认是否继续
    confirm = input("\n⚠️  确认创建测试代币? (yes/no): ").strip().lower()
    if confirm != "yes":
        logger.info("❌ 已取消")
        return

    deployer = FourMemeDeployer(four_meme_config)

    logger.info("正在创建代币...")
    result = await deployer.deploy(test_token)

    if result.success:
        logger.info("✅ 代币创建成功!")
        logger.info(f"  合约地址: {result.token_address}")
        logger.info(f"  交易哈希: {result.tx_hash}")
        if result.platform_url:
            logger.info(f"  查看: {result.platform_url}")
    else:
        logger.error(f"❌ 代币创建失败: {result.error}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 测试结束")
