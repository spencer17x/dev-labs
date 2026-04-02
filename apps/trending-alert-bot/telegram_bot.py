import asyncio
import threading
from typing import Optional, List, Dict
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ChatMemberHandler, ContextTypes, MessageHandler, filters
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, ENABLE_TELEGRAM, MESSAGE_BUTTONS, NOTIFICATION_TYPES
from chat_storage import ChatStorage, VALID_NOTIFICATION_MODES


class TelegramNotifier:
    def __init__(self):
        self.enabled = ENABLE_TELEGRAM
        self.chat_storage = ChatStorage()
        self.app = None
        self.bot_thread = None
        self.bot_loop = None
        self._report_generator = None

    def set_report_generator(self, fn):
        self._report_generator = fn

    def _setup_application(self):
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("mode", self._cmd_mode))
        self.app.add_handler(CommandHandler("setmode", self._cmd_setmode))
        self.app.add_handler(CommandHandler("report", self._cmd_report))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(MessageHandler(filters.ALL, self._handle_any_message))

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
        mode = self.chat_storage.get_notification_mode(chat.id)
        mode_desc = self._format_mode(mode)

        welcome_msg = f"""🤖 Bot 已启动

✅ {self._get_chat_type_name(chat.type)}已添加到通知列表
🔔 当前通知模式: {mode_desc}
命令: /mode /setmode /status /help"""

        await update.message.reply_text(welcome_msg)

    async def _is_admin(self, update: Update) -> bool:
        chat = update.effective_chat
        user = update.effective_user
        if not chat or not user:
            return False
        if chat.type == "private":
            return True
        try:
            member = await update.effective_chat.get_member(user.id)
            return member.status in ("administrator", "creator")
        except TelegramError:
            return False

    def _format_mode(self, mode: str) -> str:
        mode_map = {"all": "📈 趋势 + ⚡️ 异动", "trending": "📈 仅趋势", "anomaly": "⚡️ 仅异动"}
        return mode_map.get(mode, mode)

    async def _cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if not chat:
            return
        mode = self.chat_storage.get_notification_mode(chat.id)
        mode_desc = self._format_mode(mode)
        available = [m for m in VALID_NOTIFICATION_MODES if m == "all" or m in NOTIFICATION_TYPES]
        available_desc = " | ".join(available)
        msg = f"""🔔 当前通知模式: {mode_desc}

可选模式: {available_desc}
管理员可使用 /setmode <模式> 切换"""
        await update.message.reply_text(msg)

    async def _cmd_setmode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if not chat:
            return

        if not await self._is_admin(update):
            await update.message.reply_text("⛔️ 仅管理员可切换通知模式")
            return

        args = context.args
        if not args:
            available = [m for m in VALID_NOTIFICATION_MODES if m == "all" or m in NOTIFICATION_TYPES]
            available_desc = " | ".join(available)
            await update.message.reply_text(f"用法: /setmode <{available_desc}>")
            return

        new_mode = args[0].strip().lower()
        if new_mode not in VALID_NOTIFICATION_MODES:
            await update.message.reply_text(f"❌ 无效模式: {new_mode}\n可选: all | trending | anomaly")
            return

        if new_mode != "all" and new_mode not in NOTIFICATION_TYPES:
            await update.message.reply_text(f"❌ 当前 Bot 实例未启用 {new_mode} 通知类型")
            return

        if not self.chat_storage.get_chat(chat.id):
            chat_info = {
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            }
            self.chat_storage.add_chat(chat.id, chat_info)

        ok = self.chat_storage.set_notification_mode(chat.id, new_mode)
        if ok:
            mode_desc = self._format_mode(new_mode)
            await update.message.reply_text(f"✅ 通知模式已切换为: {mode_desc}")
        else:
            await update.message.reply_text("❌ 切换失败，请先 /start 初始化")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat and not self.chat_storage.get_chat(chat.id):
            chat_info = {
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            }
            self.chat_storage.add_chat(chat.id, chat_info)

        active_count = len(self.chat_storage.get_active_chats())
        mode = self.chat_storage.get_notification_mode(chat.id) if chat else "all"
        mode_desc = self._format_mode(mode)

        msg = f"""📊 状态: 正常
📱 活跃聊天: {active_count}
🔔 通知模式: {mode_desc}"""

        await update.message.reply_text(msg)

    async def _cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if not chat:
            return
        if not self._report_generator:
            await update.message.reply_text("❌ 报告功能暂不可用")
            return
        try:
            msg = self._report_generator(chat.id)
            await update.message.reply_text(msg, parse_mode='HTML', disable_web_page_preview=True)
        except Exception as e:
            await update.message.reply_text(f"❌ 生成报告失败: {e}")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = """🤖 可用命令:
/start - 订阅并初始化
/status - 查看运行状态
/mode - 查看当前通知模式
/setmode <all|trending|anomaly> - 切换通知模式 (管理员)
/report - 查看今日趋势汇总报告
/help - 查看命令说明"""
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

            chat_name = chat.title or chat.first_name or "未知"
            welcome_msg = f"""👋 已添加到 {self._get_chat_type_name(chat.type)} '{chat_name}'

✅ 已启用通知
命令: /status /help"""

            try:
                await context.bot.send_message(chat_id=chat.id, text=welcome_msg)
            except Exception as e:
                print(f"⚠️  发送欢迎消息失败: {e}")

        elif old_status in ["member", "administrator"] and new_status in ["left", "kicked"]:
            self.chat_storage.remove_chat(chat.id)

    async def _handle_any_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """自动恢复群组记录：任意消息触发时补写聊天信息"""
        chat = update.effective_chat
        if not chat:
            return
        if self.chat_storage.get_chat(chat.id):
            return

        chat_info = {
            "type": chat.type,
            "title": chat.title,
            "username": chat.username,
            "first_name": chat.first_name,
            "last_name": chat.last_name,
        }
        self.chat_storage.add_chat(chat.id, chat_info)

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
        if not self.bot_loop:
            return

        try:
            self.bot_loop.call_soon_threadsafe(self.bot_loop.stop)
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
        except Exception as e:
            print(f"⚠️  停止 Bot 时出错: {e}")


notifier = TelegramNotifier()


def send_telegram_notification(message: str, chat_id: Optional[int] = None) -> dict:
    """向后兼容的发送函数，返回 {chat_id: message_id} 字典"""
    return notifier.send_sync(message, chat_id)
