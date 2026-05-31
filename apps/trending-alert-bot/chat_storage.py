import threading
from typing import Dict, List, Optional
from db_storage import connect, ensure_schema
from timezone_utils import format_beijing_time


VALID_NOTIFICATION_MODES = {"all", "trending", "anomaly"}
DEFAULT_NOTIFICATION_MODE = "all"


class ChatStorage:
    _FILE_LOCK = threading.RLock()

    def __init__(self):
        ensure_schema()
        self.data: Dict[str, Dict] = self._load()

    def _load_unlocked(self) -> Dict[str, Dict]:
        with connect() as conn:
            rows = conn.execute("SELECT * FROM telegram_chats ORDER BY chat_id").fetchall()
        return {str(row["chat_id"]): self._row_to_chat(row) for row in rows}

    def _save_unlocked(self):
        try:
            with connect() as conn:
                for chat_data in self.data.values():
                    self._upsert_chat(conn, chat_data)
        except Exception as e:
            print(f"❌ 保存聊天记录失败: {e}")

    def _load(self) -> Dict[str, Dict]:
        with self._FILE_LOCK:
            return self._load_unlocked()

    def _save(self):
        with self._FILE_LOCK:
            self._save_unlocked()

    def _row_to_chat(self, row) -> Dict:
        chat = {
            "chat_id": row["chat_id"],
            "type": row["type"],
            "title": row["title"],
            "username": row["username"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "added_at": row["added_at"],
            "updated_at": row["updated_at"],
            "active": bool(row["active"]),
            "message_count": row["message_count"],
            "notification_mode": row["notification_mode"] or DEFAULT_NOTIFICATION_MODE,
        }
        if row["removed_at"]:
            chat["removed_at"] = row["removed_at"]
        return chat

    def _normalize_chat(self, chat_data: Dict) -> Dict:
        chat_id = int(chat_data.get("chat_id", 0))
        notification_mode = chat_data.get("notification_mode") or DEFAULT_NOTIFICATION_MODE
        if notification_mode not in VALID_NOTIFICATION_MODES:
            notification_mode = DEFAULT_NOTIFICATION_MODE

        return {
            "chat_id": chat_id,
            "type": chat_data.get("type") or "unknown",
            "title": chat_data.get("title") or "",
            "username": chat_data.get("username") or "",
            "first_name": chat_data.get("first_name") or "",
            "last_name": chat_data.get("last_name") or "",
            "added_at": chat_data.get("added_at") or format_beijing_time(),
            "updated_at": chat_data.get("updated_at") or format_beijing_time(),
            "active": bool(chat_data.get("active", True)),
            "message_count": int(chat_data.get("message_count", 0) or 0),
            "notification_mode": notification_mode,
            "removed_at": chat_data.get("removed_at") or "",
        }

    def _upsert_chat(self, conn, chat_data: Dict):
        chat = self._normalize_chat(chat_data)
        conn.execute(
            """
            INSERT INTO telegram_chats (
                chat_id, type, title, username, first_name, last_name,
                added_at, updated_at, removed_at, active, message_count,
                notification_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                type=excluded.type,
                title=excluded.title,
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                added_at=excluded.added_at,
                updated_at=excluded.updated_at,
                removed_at=excluded.removed_at,
                active=excluded.active,
                message_count=excluded.message_count,
                notification_mode=excluded.notification_mode
            """,
            (
                chat["chat_id"],
                chat["type"],
                chat["title"],
                chat["username"],
                chat["first_name"],
                chat["last_name"],
                chat["added_at"],
                chat["updated_at"],
                chat.get("removed_at", ""),
                1 if chat.get("active", True) else 0,
                chat["message_count"],
                chat["notification_mode"],
            ),
        )

    def add_chat(self, chat_id: int, chat_info: Dict):
        with self._FILE_LOCK:
            self.data = self._load_unlocked()
            chat_id_str = str(chat_id)
            existing_chat = self.data.get(chat_id_str, {})
            chat_data = {
                "chat_id": chat_id,
                "type": chat_info.get("type", "unknown"),
                "title": chat_info.get("title", ""),
                "username": chat_info.get("username", ""),
                "first_name": chat_info.get("first_name", ""),
                "last_name": chat_info.get("last_name", ""),
                "added_at": existing_chat.get("added_at", format_beijing_time()),
                "updated_at": format_beijing_time(),
                "active": True,
                "message_count": existing_chat.get("message_count", 0),
                "notification_mode": existing_chat.get("notification_mode", DEFAULT_NOTIFICATION_MODE),
            }
            self.data[chat_id_str] = chat_data
            with connect() as conn:
                self._upsert_chat(conn, chat_data)

        print(f"✅ 已添加聊天: {self._format_chat_name(chat_data)}")

    def remove_chat(self, chat_id: int):
        with self._FILE_LOCK:
            self.data = self._load_unlocked()
            chat_id_str = str(chat_id)

            if chat_id_str in self.data:
                chat_data = self.data[chat_id_str]
                chat_data["active"] = False
                chat_data["removed_at"] = format_beijing_time()
                with connect() as conn:
                    self._upsert_chat(conn, chat_data)
                print(f"🗑️  已移除聊天: {self._format_chat_name(chat_data)}")
            else:
                print(f"⚠️  聊天不存在: {chat_id}")

    def get_active_chats(self) -> List[Dict]:
        with self._FILE_LOCK:
            self.data = self._load_unlocked()
            return [chat for chat in self.data.values() if chat.get("active", True)]

    def get_chat(self, chat_id: int) -> Optional[Dict]:
        with self._FILE_LOCK:
            self.data = self._load_unlocked()
            return self.data.get(str(chat_id))

    def increment_message_count(self, chat_id: int):
        with self._FILE_LOCK:
            self.data = self._load_unlocked()
            chat_id_str = str(chat_id)
            if chat_id_str in self.data:
                self.data[chat_id_str]["message_count"] = self.data[chat_id_str].get("message_count", 0) + 1
                with connect() as conn:
                    self._upsert_chat(conn, self.data[chat_id_str])

    def get_notification_mode(self, chat_id: int) -> str:
        with self._FILE_LOCK:
            self.data = self._load_unlocked()
            chat = self.data.get(str(chat_id))
            if chat:
                return chat.get("notification_mode", DEFAULT_NOTIFICATION_MODE)
            return DEFAULT_NOTIFICATION_MODE

    def set_notification_mode(self, chat_id: int, mode: str) -> bool:
        if mode not in VALID_NOTIFICATION_MODES:
            return False
        with self._FILE_LOCK:
            self.data = self._load_unlocked()
            chat_id_str = str(chat_id)
            if chat_id_str in self.data:
                self.data[chat_id_str]["notification_mode"] = mode
                self.data[chat_id_str]["updated_at"] = format_beijing_time()
                with connect() as conn:
                    self._upsert_chat(conn, self.data[chat_id_str])
                return True
            return False

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
