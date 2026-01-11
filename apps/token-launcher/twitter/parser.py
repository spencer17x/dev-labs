"""推文解析器"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class ParsedTweet:
    """解析后的推文数据"""
    text: str
    hashtags: list[str]
    mentions: list[str]
    urls: list[str]
    cashtags: list[str]  # $符号标记的代币


class TweetParser:
    """解析推文内容，提取关键信息"""

    @staticmethod
    def parse(tweet_text: str) -> ParsedTweet:
        """解析推文"""
        # 提取 hashtags (#xxx)
        hashtags = re.findall(r"#(\w+)", tweet_text)

        # 提取 mentions (@xxx)
        mentions = re.findall(r"@(\w+)", tweet_text)

        # 提取 URLs
        urls = re.findall(r"https?://\S+", tweet_text)

        # 提取 cashtags ($XXX)
        cashtags = re.findall(r"\$([A-Za-z]+)", tweet_text)

        return ParsedTweet(
            text=tweet_text,
            hashtags=hashtags,
            mentions=mentions,
            urls=urls,
            cashtags=cashtags
        )

    @staticmethod
    def extract_token_name(tweet_text: str) -> Optional[str]:
        """
        从推文中提取可能的代币名称
        TODO: 接入AI分析
        """
        # 简单规则：优先使用 cashtag
        cashtags = re.findall(r"\$([A-Za-z]+)", tweet_text)
        if cashtags:
            return cashtags[0].upper()

        # 其次使用 hashtag
        hashtags = re.findall(r"#(\w+)", tweet_text)
        if hashtags:
            return hashtags[0].upper()

        return None
