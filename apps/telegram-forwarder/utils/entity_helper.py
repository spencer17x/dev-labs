"""
Entity information utility for Telegram entities
"""
import logging
from typing import Union, Dict, Any, Optional
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

logger = logging.getLogger(__name__)


class EntityInfoHelper:
    """Helper class for getting Telegram entity information"""

    def __init__(self, client: TelegramClient):
        self.client = client

    async def get_entity_info(self, entity_id: Union[str, int]) -> Dict[str, Any]:
        """
        获取实体信息（群组/频道/用户）

        Args:
            entity_id: Entity ID or username

        Returns:
            Dict with entity information
        """
        try:
            entity = await self.client.get_entity(entity_id)

            if isinstance(entity, (Channel, Chat)):
                title = getattr(entity, 'title', 'Unknown')
                username = getattr(entity, 'username', None)
                is_private = username is None
                access_type = "私有" if is_private else "公开"

                # Determine if it's a channel or group
                if isinstance(entity, Channel):
                    entity_type = "频道" if getattr(entity, 'broadcast', False) else "超级群组"
                else:
                    entity_type = "群组"

                return {
                    "id": entity.id,
                    "title": title,
                    "username": username,
                    "access_type": access_type,
                    "entity_type": entity_type,
                    "is_valid": True
                }
            elif isinstance(entity, User):
                first_name = getattr(entity, 'first_name', '')
                last_name = getattr(entity, 'last_name', '')
                username = getattr(entity, 'username', None)
                full_name = f"{first_name} {last_name}".strip() or 'Unknown User'

                return {
                    "id": entity.id,
                    "title": full_name,
                    "username": username,
                    "entity_type": "用户",
                    "is_valid": False  # Users are not valid for forwarding
                }
            else:
                return {
                    "id": entity_id,
                    "title": "Unknown",
                    "entity_type": "未知",
                    "is_valid": False
                }

        except Exception as e:
            logger.error(f"获取实体信息出错 {entity_id}: {e}")
            return {
                "id": entity_id,
                "error": str(e),
                "is_valid": False
            }

    def format_entity_info(self, entity_info: Dict[str, Any]) -> str:
        """
        Format entity information for display

        Args:
            entity_info: Entity information dict

        Returns:
            Formatted string
        """
        if not entity_info.get("is_valid"):
            return f"无效实体 - {entity_info.get('id')}"

        parts = [
            f"[{entity_info['entity_type']}]",
            entity_info['title'],
            f"(ID: {entity_info['id']}"
        ]

        if entity_info.get('username'):
            parts[-1] += f", @{entity_info['username']}"

        if entity_info.get('access_type'):
            parts[-1] += f", {entity_info['access_type']}"

        parts[-1] += ")"

        return " ".join(parts)
