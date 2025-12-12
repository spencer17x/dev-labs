"""
Telegram service - handles Telegram API interactions
"""
import logging
from typing import Union, Dict, Any
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

logger = logging.getLogger(__name__)


class TelegramService:
    """Telegram API 交互服务"""

    def __init__(self, client: TelegramClient):
        self.client = client

    async def get_entity_info(self, entity_id: Union[str, int]) -> Dict[str, Any]:
        """
        获取实体（群组/频道/用户）信息

        Args:
            entity_id: 实体ID（可以是用户名、ID等）

        Returns:
            包含实体信息的字典
        """
        try:
            entity = await self.client.get_entity(entity_id)

            info = {
                "is_valid": True,
                "id": entity.id,
                "type": None,
                "title": None,
                "username": None,
            }

            if isinstance(entity, Channel):
                info["type"] = "频道" if entity.broadcast else "群组"
                info["title"] = entity.title
                info["username"] = entity.username
            elif isinstance(entity, Chat):
                info["type"] = "群组"
                info["title"] = entity.title
            elif isinstance(entity, User):
                info["type"] = "用户"
                info["title"] = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                info["username"] = entity.username
            else:
                info["type"] = "未知"

            return info

        except ValueError as e:
            logger.warning(f"无法获取实体 {entity_id} 的信息: {e}")
            return {
                "is_valid": False,
                "id": entity_id,
                "type": None,
                "title": None,
                "username": None,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"获取实体 {entity_id} 信息时出错: {e}")
            return {
                "is_valid": False,
                "id": entity_id,
                "type": None,
                "title": None,
                "username": None,
                "error": str(e)
            }

    def format_entity_info(self, info: Dict[str, Any]) -> str:
        """
        格式化实体信息为可读字符串

        Args:
            info: 实体信息字典

        Returns:
            格式化的字符串
        """
        if not info.get("is_valid"):
            return f"无效 ({info.get('id')})"

        parts = []
        if info.get("title"):
            parts.append(info["title"])
        if info.get("username"):
            parts.append(f"@{info['username']}")
        if info.get("type"):
            parts.append(f"[{info['type']}]")
        parts.append(f"(ID: {info.get('id')})")

        return " ".join(parts)

    async def start(self) -> bool:
        """
        启动 Telegram 客户端

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            await self.client.start()
            logger.info("✓ Telegram 客户端启动成功")
            return True
        except PermissionError:
            logger.error("✗ 网络权限被拒绝，请检查代理或网络策略")
            return False
        except ConnectionError as e:
            logger.error(f"✗ 无法连接到 Telegram: {e}")
            logger.error("请确认网络可访问 Telegram 或配置代理")
            return False
        except OSError as e:
            logger.error(f"✗ 系统级连接错误: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ 启动客户端失败: {e}", exc_info=True)
            return False

    async def disconnect(self):
        """断开 Telegram 客户端连接"""
        await self.client.disconnect()
        logger.info("Telegram 客户端已断开连接")
