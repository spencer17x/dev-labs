"""
Event handler - handles Telegram events
"""
import logging
from telethon import events
from telethon.tl.types import Message
from core.forwarder import MessageForwarder
from config.loader import ConfigLoader

logger = logging.getLogger(__name__)


class EventHandler:
    """事件处理器"""

    def __init__(self, config: ConfigLoader, forwarder: MessageForwarder):
        self.config = config
        self.forwarder = forwarder

    async def handle_new_message(self, event: events.NewMessage.Event):
        """
        处理新消息事件

        Args:
            event: Telethon 新消息事件
        """
        try:
            message: Message = event.message
            chat = await event.get_chat()
            sender = await event.get_sender()

            # 获取群组信息
            chat_title = getattr(chat, 'title', 'Unknown')
            chat_id = chat.id
            chat_username = getattr(chat, 'username', None)

            chat_id_info = f"ID: {chat_id}"
            if chat_username:
                chat_id_info += f", @{chat_username}"

            # 获取发送者信息
            sender_id = sender.id if sender else None
            sender_username = getattr(sender, 'username', None) if sender else None
            sender_name = getattr(sender, 'first_name', '') if sender else 'Unknown'
            sender_name = sender_name or sender_username or 'Unknown'

            sender_info = f"{sender_name}"
            if sender_username:
                sender_info += f" (@{sender_username})"
            if sender_id:
                sender_info += f" [ID: {sender_id}]"

            # 获取消息内容
            message_text = message.text or "[无文本内容]"

            # 记录收到消息
            logger.info(f"📨 收到消息 [ID: {message.id}] 来自 [{chat_title}] ({chat_id_info})")
            logger.info(f"   发送者: {sender_info}")
            logger.info(f"   内容: {message_text[:100]}{'...' if len(message_text) > 100 else ''}")

            # 获取该源群组的配置
            group_config = self.config.get_group_config(chat_id)

            if not group_config:
                logger.debug(f"源群组 {chat_id} 没有配置转发规则")
                return

            # 处理消息转发
            await self.forwarder.process_message(message, group_config)

            logger.info("-" * 60)

        except Exception as e:
            logger.error(f"处理群组消息时出错: {e}", exc_info=True)

    def get_event_filter(self):
        """
        获取事件过滤器

        Returns:
            要监听的聊天ID列表
        """
        return self.config.all_source_ids
