import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from config import CHATS_FILE
from timezone_utils import format_beijing_time


class ChatStorage:
    def __init__(self):
        self.data: Dict[str, Dict] = self._load()

    def _load(self) -> Dict[str, Dict]:
        if os.path.exists(CHATS_FILE):
            try:
                with open(CHATS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  加载聊天记录失败: {e}")
                return {}
        return {}

    def _save(self):
        try:
            with open(CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存聊天记录失败: {e}")

    def add_chat(self, chat_id: int, chat_info: Dict):
        chat_id_str = str(chat_id)
        chat_data = {
            "chat_id": chat_id,
            "type": chat_info.get("type", "unknown"),
            "title": chat_info.get("title", ""),
            "username": chat_info.get("username", ""),
            "first_name": chat_info.get("first_name", ""),
            "last_name": chat_info.get("last_name", ""),
            "added_at": self.data.get(chat_id_str, {}).get("added_at", format_beijing_time()),
            "updated_at": format_beijing_time(),
            "active": True,
            "message_count": self.data.get(chat_id_str, {}).get("message_count", 0),
        }

        self.data[chat_id_str] = chat_data
        self._save()

        print(f"✅ 已添加聊天: {self._format_chat_name(chat_data)}")

    def remove_chat(self, chat_id: int):
        chat_id_str = str(chat_id)

        if chat_id_str in self.data:
            chat_data = self.data[chat_id_str]
            chat_data["active"] = False
            chat_data["removed_at"] = format_beijing_time()
            self._save()

            print(f"🗑️  已移除聊天: {self._format_chat_name(chat_data)}")
        else:
            print(f"⚠️  聊天不存在: {chat_id}")

    def get_active_chats(self) -> List[Dict]:
        return [
            chat for chat in self.data.values()
            if chat.get("active", True)
        ]

    def get_chat(self, chat_id: int) -> Optional[Dict]:
        return self.data.get(str(chat_id))

    def increment_message_count(self, chat_id: int):
        chat_id_str = str(chat_id)
        if chat_id_str in self.data:
            self.data[chat_id_str]["message_count"] = self.data[chat_id_str].get("message_count", 0) + 1
            self._save()

    def _format_chat_name(self, chat_data: Dict) -> str:
        chat_type = chat_data.get("type", "unknown")

        if chat_type == "channel":
            return f"频道 '{chat_data.get('title', 'Unknown')}' (@{chat_data.get('username', 'N/A')})"
        elif chat_type in ["group", "supergroup"]:
            return f"群组 '{chat_data.get('title', 'Unknown')}'"
        elif chat_type == "private":
            name = chat_data.get("first_name", "")
            if chat_data.get("last_name"):
                name += f" {chat_data.get('last_name')}"
            username = chat_data.get("username", "")
            return f"私聊 '{name}' (@{username})" if username else f"私聊 '{name}'"
        else:
            return f"未知类型 (ID: {chat_data.get('chat_id')})"

    def list_chats(self):
        active_chats = self.get_active_chats()

        if not active_chats:
            print("📭 没有活跃的聊天记录")
            return

        print(f"\n📋 活跃聊天列表 (共 {len(active_chats)} 个):")
        print("=" * 80)

        for chat in active_chats:
            print(f"\n🔹 {self._format_chat_name(chat)}")
            print(f"   ID: {chat['chat_id']}")
            print(f"   类型: {chat['type']}")
            print(f"   添加时间: {chat.get('added_at', 'N/A')}")
            print(f"   已发送消息: {chat.get('message_count', 0)} 条")

        print("\n" + "=" * 80)
