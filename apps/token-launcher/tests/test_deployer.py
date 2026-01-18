"""
发币脚本
运行: python -m tests.test_deployer
配置: 编辑 token.json 文件设置代币信息
"""

import asyncio
import logging
import json
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
    logger.info("🚀 Four.meme 发币脚本启动")

    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(f"配置文件错误: {e}")
        return

    # 从 config.json 读取代币配置
    token_config = config.get("token", {})
    if not token_config.get("name"):
        logger.error("❌ 未配置代币信息，请在 config.json 中设置 token 字段")
        return

    four_meme_config = config.get("four_meme", {})
    if not four_meme_config.get("private_key"):
        logger.error("❌ 未配置钱包私钥，请在 .env 中设置 FOUR_MEME_PRIVATE_KEY")
        return

    deployer = FourMemeDeployer(four_meme_config)

    # 检查连接和余额
    if not deployer._check_connection():
        logger.error("❌ 无法连接到 BSC 网络")
        return

    balance = deployer._get_balance()
    logger.info(f"钱包地址: {deployer.address}")
    logger.info(f"BNB 余额: {balance:.4f} BNB")

    if balance < 0.01:
        logger.error(f"❌ BNB 余额不足，至少需要 0.01 BNB")
        return

    # 从配置文件读取代币信息
    name = token_config.get("name", "Test Token")
    symbol = token_config.get("symbol", "TEST")
    description = token_config.get("description", "")
    image_url = token_config.get("image_url", "")
    twitter_url = token_config.get("twitter_url", "")
    telegram_url = token_config.get("telegram_url", "")
    website_url = token_config.get("website_url", "")
    buy_amount = float(four_meme_config.get("buy_amount", 0))

    test_token = TokenInfo(
        name=name,
        symbol=symbol,
        description=description,
        image_url=image_url,
        twitter_url=twitter_url,
        telegram_url=telegram_url,
        website_url=website_url,
    )

    print("\n" + "=" * 50)
    logger.info("📋 代币信息确认:")
    logger.info(f"  名称: {test_token.name}")
    logger.info(f"  符号: {test_token.symbol}")
    logger.info(f"  描述: {test_token.description}")
    logger.info(f"  图片: {test_token.image_url or '无'}")
    logger.info(f"  Twitter: {test_token.twitter_url or '无'}")
    logger.info(f"  Telegram: {test_token.telegram_url or '无'}")
    logger.info(f"  网站: {test_token.website_url or '无'}")
    logger.info(f"  购买金额: {buy_amount} BNB")
    logger.info(f"  网络: BSC {four_meme_config.get('network', 'mainnet')}")
    print("=" * 50)

    # 检查是否跳过确认 (--yes 参数)
    skip_confirm = "--yes" in sys.argv or "-y" in sys.argv

    if not skip_confirm:
        confirm = input("\n⚠️  确认创建代币? 这将消耗 Gas 费用! (yes/no): ").strip().lower()
        if confirm != "yes":
            logger.info("❌ 已取消")
            return

    logger.info("正在创建代币...")
    result = await deployer.deploy(test_token, buy_amount=buy_amount)

    print("\n" + "=" * 50)
    if result.success:
        logger.info("✅ 代币创建成功!")
        logger.info(f"  合约地址: {result.token_address}")
        logger.info(f"  交易哈希: {result.tx_hash}")
        if result.platform_url:
            logger.info(f"  Four.meme: {result.platform_url}")
        logger.info(f"  BscScan: https://bscscan.com/tx/{result.tx_hash}")
    else:
        logger.error(f"❌ 代币创建失败: {result.error}")
    print("=" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 测试结束")
