"""
Message service - handles message forwarding logic
"""
import logging
from typing import List, Union
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors.rpcerrorlist import (
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    ChannelPrivateError,
    FloodWaitError
)

logger = logging.getLogger(__name__)


class MessageService:
    """消息处理服务"""

    def __init__(self, client: TelegramClient):
        self.client = client

    async def forward_message(self, message: Message, target_groups: List[Union[int, str]]) -> int:
        """
        转发消息到指定目标群组

        Args:
            message: 要转发的消息
            target_groups: 目标群组ID或用户名列表

        Returns:
            成功转发的目标数量
        """
        if not target_groups:
            logger.warning("没有指定转发目标群组")
            return 0

        success_count = 0
        for target in target_groups:
            try:
                await self._forward_to_target(message, target)
                success_count += 1
                logger.info(f"✓ 消息 [ID: {message.id}] 已转发到: {target}")

            except FloodWaitError as e:
                logger.warning(f"✗ 触发频率限制，需等待 {e.seconds} 秒: {target}")

            except (ChatWriteForbiddenError, UserBannedInChannelError):
                logger.error(f"✗ 无权限发送消息到: {target}")

            except ChannelPrivateError:
                logger.error(f"✗ 频道/群组为私有或不存在: {target}")

            except Exception as e:
                logger.error(f"✗ 转发消息到 {target} 失败: {e.__class__.__name__}: {e}")

        if success_count > 0:
            logger.debug(f"成功转发到 {success_count}/{len(target_groups)} 个目标")

        return success_count

    async def _forward_to_target(self, message: Message, target: Union[int, str]):
        """
        转发消息到单个目标

        Args:
            message: 要转发的消息
            target: 目标群组ID或用户名
        """
        try:
            # 尝试直接转发
            await self.client.forward_messages(
                target,
                message,
                silent=False
            )
        except Exception:
            # 如果转发失败，尝试作为新消息发送
            await self._send_as_new_message(message, target)

    async def _send_as_new_message(self, message: Message, target: Union[int, str]):
        """
        作为新消息发送（而不是转发）

        Args:
            message: 原始消息
            target: 目标群组ID或用户名
        """
        # 发送文本
        if message.text:
            await self.client.send_message(
                target,
                message.text,
                silent=False
            )

        # 发送媒体
        elif message.media:
            await self.client.send_file(
                target,
                file=message.media,
                caption=message.text if message.text else None,
                silent=False
            )
