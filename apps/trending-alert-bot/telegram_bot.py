import asyncio
import threading
from typing import Optional, List, Dict
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ChatMemberHandler, ContextTypes, filters
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, ENABLE_TELEGRAM, MESSAGE_BUTTONS
from chat_storage import ChatStorage, ChatSettingsStore


class TelegramNotifier:
    def __init__(self):
        self.enabled = ENABLE_TELEGRAM
        self.chat_storage = ChatStorage()
        self.chat_settings = ChatSettingsStore()
        self.app = None
        self.bot_thread = None
        self.bot_loop = None

    def _setup_application(self):
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("mode", self._cmd_mode))

        # 添加聊天成员状态变化处理器
        self.app.add_handler(
            ChatMemberHandler(self._handle_chat_member_updated, ChatMemberHandler.MY_CHAT_MEMBER)
        )

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        chat_info = {
            "type": chat.type,
            "title": chat.title,
            "username": chat.username,
            "first_name": chat.first_name,
            "last_name": chat.last_name,
        }
        self.chat_storage.add_chat(chat.id, chat_info)
        if str(chat.id) not in self.chat_settings.get_all():
            self.chat_settings.set_mode(chat.id, "trend")

        # 支持 /start <trend|anomaly|both> 一次性设置模式
        if context.args:
            mode_arg = (context.args[0] or "").lower()
            if mode_arg in ["trend", "anomaly", "both"]:
                if not await self._is_admin(update):
                    await update.message.reply_text("⛔️ 仅管理员可设置通知模式")
                else:
                    self.chat_settings.set_mode(chat.id, mode_arg)

        mode = self.chat_settings.get_mode(chat.id)
        if mode == "trend":
            mode_label = "趋势通知"
        elif mode == "anomaly":
            mode_label = "异动通知"
        else:
            mode_label = "趋势 + 异动通知"

        welcome_msg = f"""🤖 Bot 已启动

✅ {self._get_chat_type_name(chat.type)}已添加到通知列表
📌 当前模式: {mode_label}

命令: /status /mode /help
快速设置: /start trend|anomaly|both"""

        await update.message.reply_text(welcome_msg)

    async def _is_admin(self, update: Update) -> bool:
        chat = update.effective_chat
        user = update.effective_user
        if not chat or not user:
            return False
        if chat.type == "private":
            return True
        try:
            member = await self.app.bot.get_chat_member(chat.id, user.id)
            return member.status in ["administrator", "creator"]
        except Exception as e:
            print(f"⚠️  获取管理员状态失败: {e}")
            return False

    async def _cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if context.args:
            mode_arg = (context.args[0] or "").lower()
            if mode_arg in ["trend", "anomaly", "both"]:
                if not await self._is_admin(update):
                    await update.message.reply_text("⛔️ 仅管理员可设置通知模式")
                else:
                    self.chat_settings.set_mode(chat.id, mode_arg)
        mode = self.chat_settings.get_mode(chat.id)
        if mode == "trend":
            label = "趋势通知"
        elif mode == "anomaly":
            label = "异动通知"
        else:
            label = "趋势 + 异动通知"
        await update.message.reply_text(f"📌 当前模式: {label}")


    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        active_count = len(self.chat_storage.get_active_chats())
        mode = self.chat_settings.get_mode(update.effective_chat.id)
        if mode == "trend":
            mode_label = "趋势通知"
        elif mode == "anomaly":
            mode_label = "异动通知"
        else:
            mode_label = "趋势 + 异动通知"

        msg = f"""📊 状态: 正常
📱 活跃聊天: {active_count}
🔔 通知: 已启用
📌 当前模式: {mode_label}"""

        await update.message.reply_text(msg)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = """🤖 可用命令:
/start - 订阅并初始化
/start trend|anomaly|both - 初始化并设置模式
/status - 查看运行状态
/mode - 查看当前群模式
/mode trend|anomaly|both - 设置当前群模式 (管理员)"""
        await update.message.reply_text(msg)

    async def _handle_chat_member_updated(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = update.my_chat_member
        chat = result.chat
        new_status = result.new_chat_member.status
        old_status = result.old_chat_member.status

        if old_status in ["left", "kicked"] and new_status in ["member", "administrator"]:
            chat_info = {
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            }
            self.chat_storage.add_chat(chat.id, chat_info)
            if str(chat.id) not in self.chat_settings.get_all():
                self.chat_settings.set_mode(chat.id, "trend")

            chat_name = chat.title or chat.first_name or "未知"
            welcome_msg = f"""👋 已添加到 {self._get_chat_type_name(chat.type)} '{chat_name}'

✅ 已启用通知
命令: /chats /status"""

            try:
                await context.bot.send_message(chat_id=chat.id, text=welcome_msg)
            except Exception as e:
                print(f"⚠️  发送欢迎消息失败: {e}")

        elif old_status in ["member", "administrator"] and new_status in ["left", "kicked"]:
            self.chat_storage.remove_chat(chat.id)

    def _get_chat_type_name(self, chat_type: str) -> str:
        type_map = {
            "private": "私聊",
            "group": "群组",
            "supergroup": "超级群组",
            "channel": "频道",
        }
        return type_map.get(chat_type, "聊天")

    def _build_inline_keyboard(self, token_address: str = None, chain: str = None) -> Optional[InlineKeyboardMarkup]:
        """根据配置生成内联按钮键盘，支持按链过滤"""
        if not MESSAGE_BUTTONS or not token_address:
            return None

        buttons = []
        for btn_config in MESSAGE_BUTTONS:
            text = btn_config.get("text", "")
            url = btn_config.get("url", "")
            btn_chain = btn_config.get("chain", "")

            # 如果按钮配置了链，则只在对应链的通知中显示
            if btn_chain and chain and btn_chain.lower() != chain.lower():
                continue

            if text and url:
                # 替换 token_address 占位符
                url = url.replace("{token_address}", token_address)
                buttons.append(InlineKeyboardButton(text=text, url=url))

        if not buttons:
            return None

        # 每行最多3个按钮
        rows = []
        for i in range(0, len(buttons), 3):
            rows.append(buttons[i:i+3])

        return InlineKeyboardMarkup(rows)

    async def send_message(self, message: str, chat_id: Optional[int] = None, reply_to_message_id: Optional[int] = None, token_address: str = None, chain: str = None) -> dict:
        """发送消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.app:
            return {}

        try:
            bot = self.app.bot
            message_ids = {}
            reply_markup = self._build_inline_keyboard(token_address, chain)

            if chat_id is not None:
                sent_msg = await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    disable_web_page_preview=True,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                )
                self.chat_storage.increment_message_count(chat_id)
                message_ids[chat_id] = sent_msg.message_id
                return message_ids

            active_chats = self.chat_storage.get_active_chats()

            if not active_chats:
                print("⚠️  没有活跃的聊天，消息未发送")
                return {}

            success_count = 0
            for i, chat in enumerate(active_chats):
                try:
                    # 每条消息间隔0.5秒，避免频率限制
                    if i > 0:
                        await asyncio.sleep(0.5)

                    sent_msg = await bot.send_message(
                        chat_id=chat["chat_id"],
                        text=message,
                        disable_web_page_preview=True,
                        reply_to_message_id=reply_to_message_id,
                        parse_mode='HTML',
                        reply_markup=reply_markup,
                    )
                    self.chat_storage.increment_message_count(chat["chat_id"])
                    message_ids[chat["chat_id"]] = sent_msg.message_id
                    success_count += 1
                except TelegramError as e:
                    if "Flood control" in str(e):
                        print(f"⚠️  频率限制，跳过发送到 {chat['chat_id']}")
                    else:
                        print(f"❌ 发送到 {chat['chat_id']} 失败: {e}")

            return message_ids

        except Exception as e:
            print(f"❌ 发送消息时发生错误: {e}")
            return {}

    async def send_photo(self, photo_url: str, caption: str, chat_id: Optional[int] = None, token_address: str = None, chain: str = None) -> dict:
        """发送图片消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.app:
            return {}

        try:
            bot = self.app.bot
            message_ids = {}
            reply_markup = self._build_inline_keyboard(token_address, chain)

            if chat_id is not None:
                sent_msg = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_url,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                )
                self.chat_storage.increment_message_count(chat_id)
                message_ids[chat_id] = sent_msg.message_id
                return message_ids

            active_chats = self.chat_storage.get_active_chats()

            if not active_chats:
                print("⚠️  没有活跃的聊天，消息未发送")
                return {}

            success_count = 0
            for i, chat in enumerate(active_chats):
                try:
                    # 每条消息间隔0.5秒，避免频率限制
                    if i > 0:
                        await asyncio.sleep(0.5)

                    sent_msg = await bot.send_photo(
                        chat_id=chat["chat_id"],
                        photo=photo_url,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=reply_markup,
                    )
                    self.chat_storage.increment_message_count(chat["chat_id"])
                    message_ids[chat["chat_id"]] = sent_msg.message_id
                    success_count += 1
                except TelegramError as e:
                    if "Flood control" in str(e):
                        print(f"⚠️  频率限制，跳过发送图片到 {chat['chat_id']}")
                    else:
                        print(f"❌ 发送图片到 {chat['chat_id']} 失败: {e} | url={photo_url}")

            return message_ids

        except Exception as e:
            print(f"❌ 发送图片消息时发生错误: {e} | url={photo_url}")
            return {}

    def send_sync(self, message: str, chat_id: Optional[int] = None, reply_to_message_id: Optional[int] = None, token_address: str = None, chain: str = None) -> dict:
        """同步发送消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.bot_loop:
            return {}

        try:
            future = asyncio.run_coroutine_threadsafe(
                self.send_message(message, chat_id, reply_to_message_id, token_address, chain),
                self.bot_loop
            )
            return future.result(timeout=10)
        except Exception as e:
            print(f"❌ 同步发送失败: {e}")
            return {}

    def send_photo_sync(self, photo_url: str, caption: str, chat_id: Optional[int] = None, token_address: str = None, chain: str = None) -> dict:
        """同步发送图片消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.bot_loop:
            return {}

        try:
            future = asyncio.run_coroutine_threadsafe(
                self.send_photo(photo_url, caption, chat_id, token_address, chain),
                self.bot_loop
            )
            return future.result(timeout=10)
        except Exception as e:
            print(f"❌ 同步发送图片失败: {e} | url={photo_url}")
            return {}

    def send_with_reply_sync(self, message: str, token_address: str, storage, chat_id: Optional[int] = None, chain: str = None) -> bool:
        """发送消息并引用首次通知（如果存在），带按钮"""
        if not self.enabled or not self.bot_loop:
            return False

        try:
            # 获取所有需要发送的聊天
            if chat_id is not None:
                chats = [{'chat_id': chat_id}]
            else:
                chats = self.chat_storage.get_active_chats()

            if not chats:
                return False

            # 为每个聊天分别发送（因为 reply_to_message_id 不同）
            for chat in chats:
                cid = chat['chat_id']
                reply_to_id = storage.get_telegram_message_id(token_address, cid)

                future = asyncio.run_coroutine_threadsafe(
                    self.send_message(message, cid, reply_to_id, token_address, chain),
                    self.bot_loop
                )
                future.result(timeout=10)

            return True
        except Exception as e:
            print(f"❌ 同步发送（带引用）失败: {e}")
            return False

    def start_bot(self):
        if not self.enabled:
            return

        def run_bot():
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)

            try:
                self._setup_application()

                self.bot_loop.run_until_complete(self.app.initialize())
                self.bot_loop.run_until_complete(self.app.start())
                self.bot_loop.run_until_complete(self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES))
                self.bot_loop.run_forever()
            except Exception as e:
                print(f"❌ Bot 线程错误: {e}")
                import traceback
                traceback.print_exc()
            finally:
                try:
                    if self.app:
                        self.bot_loop.run_until_complete(self.app.updater.stop())
                        self.bot_loop.run_until_complete(self.app.stop())
                        self.bot_loop.run_until_complete(self.app.shutdown())
                except:
                    pass
                self.bot_loop.close()
                self.bot_loop = None

        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()

        import time
        time.sleep(1)

    def stop_bot(self):
        if self.app and self.app.updater:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.stop()
            except Exception as e:
                print(f"⚠️  停止 Bot 时出错: {e}")


notifier = TelegramNotifier()


def send_telegram_notification(message: str, chat_id: Optional[int] = None) -> dict:
    """向后兼容的发送函数，返回 {chat_id: message_id} 字典"""
    return notifier.send_sync(message, chat_id)
