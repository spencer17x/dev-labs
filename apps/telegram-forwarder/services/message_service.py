"""
Message service - handles message forwarding logic
"""

import asyncio
import logging
from typing import List, Union
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors.rpcerrorlist import (
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    ChannelPrivateError,
    FloodWaitError,
)

logger = logging.getLogger(__name__)


class MessageService:
    """消息处理服务"""

    def __init__(self, client: TelegramClient, flood_wait_max_seconds: int = 0):
        self.client = client
        self.flood_wait_max_seconds = flood_wait_max_seconds

    async def forward_message(
        self,
        message: Union[Message, List[Message]],
        target_groups: List[Union[int, str]],
        forward_mode: str = "forward",
        silent: bool = False,
        flood_wait_max_seconds: int | None = None,
    ) -> int:
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
        max_wait = (
            self.flood_wait_max_seconds
            if flood_wait_max_seconds is None
            else flood_wait_max_seconds
        )
        for target in target_groups:
            try:
                sent = await self._forward_to_target(
                    message, target, forward_mode, silent
                )
                if sent:
                    success_count += 1
                    logger.info(
                        f"✓ 消息 [ID: {self._format_message_id(message)}] 已转发到: {target}"
                    )
                else:
                    logger.warning(
                        f"✗ 消息 [ID: {self._format_message_id(message)}] 不支持 fallback 发送: {target}"
                    )

            except FloodWaitError as e:
                if e.seconds <= max_wait:
                    logger.warning(f"触发频率限制，等待 {e.seconds} 秒后重试: {target}")
                    await asyncio.sleep(e.seconds)
                    try:
                        sent = await self._forward_to_target(
                            message, target, forward_mode, silent
                        )
                        if sent:
                            success_count += 1
                            logger.info(
                                f"✓ 消息 [ID: {self._format_message_id(message)}] 重试后已转发到: {target}"
                            )
                    except Exception as retry_error:
                        logger.error(f"✗ 重试转发到 {target} 失败: {retry_error}")
                else:
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

    async def _forward_to_target(
        self,
        message: Union[Message, List[Message]],
        target: Union[int, str],
        forward_mode: str = "forward",
        silent: bool = False,
    ) -> bool:
        """
        转发消息到单个目标

        Args:
            message: 要转发的消息
            target: 目标群组ID或用户名
        """
        if forward_mode == "copy":
            return await self._send_as_new_message(message, target, silent)

        try:
            # 尝试直接转发
            await self.client.forward_messages(target, message, silent=silent)
            return True
        except FloodWaitError:
            raise
        except Exception as e:
            logger.debug(
                f"原生转发到 {target} 失败，尝试作为新消息发送: {e.__class__.__name__}: {e}"
            )
            # 如果转发失败，尝试作为新消息发送
            return await self._send_as_new_message(message, target, silent)

    async def _send_as_new_message(
        self,
        message: Union[Message, List[Message]],
        target: Union[int, str],
        silent: bool = False,
    ) -> bool:
        """
        作为新消息发送（而不是转发）

        Args:
            message: 原始消息
            target: 目标群组ID或用户名
        """
        if isinstance(message, list):
            sent_any = False
            for item in message:
                sent_any = (
                    await self._send_as_new_message(item, target, silent) or sent_any
                )
            return sent_any

        # 优先发送媒体，避免带 caption 的媒体在 fallback 时丢失文件。
        if message.media:
            await self.client.send_file(
                target,
                file=message.media,
                caption=message.text if message.text else None,
                silent=silent,
            )
            return True

        # 发送文本
        if message.text:
            await self.client.send_message(target, message.text, silent=silent)
            return True

        return False

    def _format_message_id(self, message: Union[Message, List[Message]]) -> str:
        if isinstance(message, list):
            return ",".join(str(getattr(item, "id", "?")) for item in message)
        return str(getattr(message, "id", "?"))
