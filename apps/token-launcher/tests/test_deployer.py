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
    logger.info("🚀 Four.meme 发币测试启动")

    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(f"配置文件错误: {e}")
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

    # 获取用户输入
    print("\n" + "=" * 50)
    print("📋 请输入代币信息 (直接回车使用默认值)")
    print("=" * 50)

    name = input("代币名称 [Test Token]: ").strip() or "Test Token"
    symbol = input("代币符号 [TEST]: ").strip() or "TEST"
    description = input("代币描述 [A test token]: ").strip() or "A test token"
    image_url = input("图片URL []: ").strip() or ""
    twitter_url = input("Twitter链接 []: ").strip() or ""
    telegram_url = input("Telegram链接 []: ").strip() or ""
    website_url = input("网站链接 []: ").strip() or ""

    buy_amount_str = input("创建时购买金额 BNB [0]: ").strip() or "0"
    try:
        buy_amount = float(buy_amount_str)
    except ValueError:
        buy_amount = 0

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

    # 确认是否继续
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
