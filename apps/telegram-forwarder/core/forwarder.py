"""
Message forwarder - core business logic for message forwarding
"""
import logging
from telethon.tl.types import Message
from filters.message_filter import MessageFilter
from services.message_service import MessageService
from config.loader import GroupConfig

logger = logging.getLogger(__name__)


class MessageForwarder:
    """消息转发核心逻辑"""

    def __init__(self, message_service: MessageService):
        self.message_service = message_service
        self.message_filter = MessageFilter()

    async def process_message(self, message: Message, group_config: GroupConfig) -> int:
        """
        处理消息转发

        Args:
            message: 收到的消息
            group_config: 群组配置

        Returns:
            成功转发的目标数量
        """
        # 获取启用的规则
        enabled_rules = [r for r in group_config.rules if r.enabled]
        if not enabled_rules:
            logger.debug(f"群组 {group_config.id} 没有启用的规则")
            return 0

        logger.info(f"   匹配到 {len(enabled_rules)} 条已启用规则")

        # 处理每条规则
        forwarded_count = 0
        for idx, rule in enumerate(enabled_rules):
            try:
                # 检查规则是否匹配
                should_forward = self.message_filter.should_forward(message, rule)

                if should_forward:
                    # 转发到该规则的所有目标群组
                    logger.info(f"   ✓ 规则 {idx+1} 匹配 (模式: {rule.filter_mode})")
                    logger.info(f"     转发到 {len(rule.target_ids)} 个目标群组...")

                    count = await self.message_service.forward_message(
                        message,
                        rule.target_ids
                    )
                    forwarded_count += count
                else:
                    logger.debug(f"   ✗ 规则 {idx+1} 不匹配 (模式: {rule.filter_mode})")

            except Exception as e:
                logger.error(f"   处理规则 {idx+1} 时出错: {e}", exc_info=True)

        if forwarded_count > 0:
            logger.info(f"   ✅ 消息已转发到 {forwarded_count} 个目标")
        else:
            logger.info(f"   ⊘ 消息未匹配任何规则，未转发")

        return forwarded_count
