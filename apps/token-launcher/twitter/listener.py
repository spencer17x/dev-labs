"""推特监听器 - 使用 twikit 库通过 cookie 登录"""

import asyncio
import logging
from typing import Callable, List
from twikit import Client

logger = logging.getLogger(__name__)


class TwitterListener:
    def __init__(self, config: dict):
        self.config = config
        self.client = Client()
        self.watch_users = config.get("watch_users", [])
        self.poll_interval = config.get("poll_interval", 30)
        self.seen_tweets: set = set()
        self.on_new_tweet: Callable = None

    async def login(self):
        """使用 cookie 登录"""
        cookies = self.config.get("cookies", {})
        self.client.set_cookies(cookies)
        logger.info("Twitter 登录成功 (cookie)")

    async def get_user_tweets(self, username: str, count: int = 10) -> List:
        """获取用户最新推文"""
        try:
            user = await self.client.get_user_by_screen_name(username)
            tweets = await user.get_tweets("Tweets", count=count)
            return tweets
        except Exception as e:
            logger.error(f"获取 @{username} 推文失败: {type(e).__name__}: {e}")
            return []

    async def check_new_tweets(self):
        """检查所有监听用户的新推文"""
        for username in self.watch_users:
            tweets = await self.get_user_tweets(username, count=5)

            for tweet in tweets:
                if tweet.id not in self.seen_tweets:
                    self.seen_tweets.add(tweet.id)
                    logger.info(f"发现新推文 @{username}: {tweet.text[:50]}...")

                    if self.on_new_tweet:
                        await self.on_new_tweet(username, tweet)

    async def start(self):
        """启动监听循环"""
        await self.login()
        logger.info(f"开始监听用户: {self.watch_users}")

        # 首次运行，记录现有推文ID（不触发）
        for username in self.watch_users:
            tweets = await self.get_user_tweets(username, count=20)
            for tweet in tweets:
                self.seen_tweets.add(tweet.id)

        logger.info(f"已记录 {len(self.seen_tweets)} 条现有推文")

        # 开始轮询
        while True:
            await self.check_new_tweets()
            await asyncio.sleep(self.poll_interval)
