"""
推特监听测试
运行: python -m tests.test_twitter
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import timezone, timedelta, datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.loader import load_config
from twitter.listener import TwitterListener
from twitter.parser import TweetParser

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 屏蔽第三方库的详细日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("twikit").setLevel(logging.WARNING)


async def on_new_tweet(username: str, tweet):
    """收到新推文的回调"""
    # 转换为北京时间
    created_at = tweet.created_at
    if created_at:
        # twikit 返回的是字符串，需要先解析
        if isinstance(created_at, str):
            # 格式如 "Sat Jan 11 14:15:00 +0000 2026"
            try:
                dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                beijing_time = dt.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                beijing_time = created_at
        else:
            beijing_time = created_at.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    else:
        beijing_time = "未知"

    # 推文链接
    tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"

    logger.info("=" * 50)
    logger.info(f"📢 新推文来自 @{username}")
    logger.info(f"内容: {tweet.text}")
    logger.info(f"时间: {beijing_time} (北京时间)")
    logger.info(f"链接: {tweet_url}")

    # 解析推文
    parsed = TweetParser.parse(tweet.text)
    if parsed.hashtags:
        logger.info(f"Hashtags: {parsed.hashtags}")
    if parsed.cashtags:
        logger.info(f"Cashtags: {parsed.cashtags}")
    if parsed.mentions:
        logger.info(f"Mentions: {parsed.mentions}")

    # 尝试提取代币名称
    token_name = TweetParser.extract_token_name(tweet.text)
    if token_name:
        logger.info(f"🪙 可能的代币名称: {token_name}")

    logger.info("=" * 50)


async def main():
    logger.info("🐦 推特监听测试启动")

    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(f"配置文件错误: {e}")
        return

    twitter_config = config.get("twitter", {})

    if not twitter_config.get("cookies"):
        logger.error("❌ 未配置 Twitter cookies，请在 .env 中设置 TWITTER_AUTH_TOKEN 和 TWITTER_CT0")
        return

    if not twitter_config.get("watch_users"):
        logger.error("❌ 未配置监听用户，请在 config.json 中设置 watch_users")
        return

    logger.info(f"监听用户: {twitter_config['watch_users']}")
    logger.info(f"轮询间隔: {twitter_config.get('poll_interval', 30)} 秒")

    listener = TwitterListener(twitter_config)
    listener.on_new_tweet = on_new_tweet

    logger.info("开始监听，按 Ctrl+C 退出...")
    await listener.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 测试结束")
