"""Telegram 通知器"""

import logging
from telegram import Bot
from telegram.constants import ParseMode
from deployer.base import TokenInfo, DeployResult

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, config: dict):
        self.bot_token = config.get("bot_token")
        self.chat_id = config.get("chat_id")
        self.bot = Bot(token=self.bot_token) if self.bot_token else None

    async def notify_new_tweet(self, username: str, tweet_text: str):
        """通知发现新推文"""
        message = (
            f"🐦 *发现新推文*\n\n"
            f"用户: @{username}\n"
            f"内容: {self._escape_markdown(tweet_text[:200])}"
        )
        await self._send(message)

    async def notify_token_created(self, token_info: TokenInfo, result: DeployResult):
        """通知代币创建成功"""
        if result.success:
            message = (
                f"🚀 *代币创建成功!*\n\n"
                f"名称: {token_info.name}\n"
                f"符号: ${token_info.symbol}\n"
                f"合约: `{result.token_address}`\n"
                f"交易: `{result.tx_hash}`\n"
            )
            if result.platform_url:
                message += f"\n🔗 [查看详情]({result.platform_url})"
        else:
            message = (
                f"❌ *代币创建失败*\n\n"
                f"名称: {token_info.name}\n"
                f"错误: {result.error}"
            )

        await self._send(message)

    async def notify_error(self, error: str):
        """通知错误"""
        message = f"⚠️ *错误*\n\n{self._escape_markdown(error)}"
        await self._send(message)

    async def _send(self, message: str):
        """发送消息"""
        if not self.bot:
            logger.warning("Telegram bot 未配置")
            return

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"发送 Telegram 消息失败: {e}")

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """转义 Markdown 特殊字符"""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
