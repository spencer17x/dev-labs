from __future__ import annotations

import asyncio
import threading
import time
from typing import Optional, List, Dict

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application,
        CommandHandler,
        ChatMemberHandler,
        ContextTypes,
        TypeHandler,
    )
    from telegram.error import BadRequest, ChatMigrated, Forbidden, TelegramError
except ModuleNotFoundError:
    Update = None
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    Application = None
    CommandHandler = None
    ChatMemberHandler = None
    ContextTypes = None
    TypeHandler = None

    class TelegramError(Exception):
        pass

    class BadRequest(TelegramError):
        pass

    class Forbidden(TelegramError):
        pass

    class ChatMigrated(TelegramError):
        def __init__(self, new_chat_id: int):
            self.new_chat_id = new_chat_id


from config import (
    TELEGRAM_BOT_TOKEN,
    ENABLE_TELEGRAM,
    MESSAGE_BUTTONS,
    NOTIFICATION_TYPES,
)
from chat_storage import ChatStorage, VALID_NOTIFICATION_MODES

# Long-poll must stay under HTTP read timeout; leave headroom for Socks proxies.
_GET_UPDATES_TIMEOUT = 20
_GET_UPDATES_READ_TIMEOUT = 35.0
_HTTP_CONNECT_TIMEOUT = 15.0
_HTTP_READ_TIMEOUT = 30.0
_HTTP_WRITE_TIMEOUT = 30.0
_HTTP_POOL_TIMEOUT = 10.0
_BACKLOG_GRACE_SECONDS = 45.0
_BACKLOG_STALE_SECONDS = 90.0
_WORKER_START_TIMEOUT = 45.0


def _require_telegram_sdk():
    if Application is None:
        raise RuntimeError("python-telegram-bot is required to start the Telegram bot")


class TelegramRuntimeError(RuntimeError):
    """Raised when the Telegram worker cannot accept notifications."""


class TelegramNotifier:
    def __init__(self):
        self.enabled = ENABLE_TELEGRAM
        self.chat_storage = ChatStorage()
        self.app = None
        self.bot_thread = None
        self.bot_loop = None
        self._report_generator = None
        self._report_tasks = {}
        self._ready_event = threading.Event()
        self._worker_error = None
        self._started_at = 0.0
        self._last_update_at = 0.0
        self._restart_lock = threading.Lock()

    def set_report_generator(self, fn):
        self._report_generator = fn

    async def _generate_report(self, chat_id: int) -> str:
        tasks = getattr(self, "_report_tasks", None)
        if tasks is None:
            tasks = self._report_tasks = {}
        task = tasks.get(chat_id)
        if task is None:
            task = asyncio.create_task(
                asyncio.to_thread(self._report_generator, chat_id)
            )
            tasks[chat_id] = task

            def clear_completed(completed_task):
                if tasks.get(chat_id) is completed_task:
                    tasks.pop(chat_id, None)

            task.add_done_callback(clear_completed)
        return await asyncio.shield(task)

    def _setup_application(self):
        _require_telegram_sdk()
        # Separate getUpdates client timeouts so long-poll survives proxy latency.
        self.app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .concurrent_updates(16)
            .connect_timeout(_HTTP_CONNECT_TIMEOUT)
            .read_timeout(_HTTP_READ_TIMEOUT)
            .write_timeout(_HTTP_WRITE_TIMEOUT)
            .pool_timeout(_HTTP_POOL_TIMEOUT)
            .get_updates_connect_timeout(_HTTP_CONNECT_TIMEOUT)
            .get_updates_read_timeout(_GET_UPDATES_READ_TIMEOUT)
            .get_updates_write_timeout(_HTTP_WRITE_TIMEOUT)
            .get_updates_pool_timeout(_HTTP_POOL_TIMEOUT)
            .build()
        )
        # Heartbeat on every inbound update (commands, membership, etc.).
        self.app.add_handler(TypeHandler(Update, self._track_update), group=-1)
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("mode", self._cmd_mode))
        self.app.add_handler(CommandHandler("setmode", self._cmd_setmode))
        self.app.add_handler(CommandHandler("report", self._cmd_report))
        self.app.add_handler(CommandHandler("help", self._cmd_help))

        # 添加聊天成员状态变化处理器
        self.app.add_handler(
            ChatMemberHandler(
                self._handle_chat_member_updated, ChatMemberHandler.MY_CHAT_MEMBER
            )
        )

    async def _track_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self._last_update_at = time.time()

    def _on_polling_error(self, error: TelegramError):
        print(f"⚠️ Telegram polling error: {error}")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        chat_info = {
            "type": chat.type,
            "title": chat.title,
            "username": chat.username,
            "first_name": chat.first_name,
            "last_name": chat.last_name,
        }
        await asyncio.to_thread(self.chat_storage.add_chat, chat.id, chat_info)
        mode = await asyncio.to_thread(self.chat_storage.get_notification_mode, chat.id)
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
        mode_map = {
            "all": "📈 趋势 + ⚡️ 异动",
            "trending": "📈 仅趋势",
            "anomaly": "⚡️ 仅异动",
        }
        return mode_map.get(mode, mode)

    async def _cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if not chat:
            return
        mode = await asyncio.to_thread(self.chat_storage.get_notification_mode, chat.id)
        mode_desc = self._format_mode(mode)
        available = [
            m for m in VALID_NOTIFICATION_MODES if m == "all" or m in NOTIFICATION_TYPES
        ]
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
            available = [
                m
                for m in VALID_NOTIFICATION_MODES
                if m == "all" or m in NOTIFICATION_TYPES
            ]
            available_desc = " | ".join(available)
            await update.message.reply_text(f"用法: /setmode <{available_desc}>")
            return

        new_mode = args[0].strip().lower()
        if new_mode not in VALID_NOTIFICATION_MODES:
            await update.message.reply_text(
                f"❌ 无效模式: {new_mode}\n可选: all | trending | anomaly"
            )
            return

        if new_mode != "all" and new_mode not in NOTIFICATION_TYPES:
            await update.message.reply_text(
                f"❌ 当前 Bot 实例未启用 {new_mode} 通知类型"
            )
            return

        if not await asyncio.to_thread(self.chat_storage.get_chat, chat.id):
            chat_info = {
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            }
            await asyncio.to_thread(self.chat_storage.add_chat, chat.id, chat_info)

        ok = await asyncio.to_thread(
            self.chat_storage.set_notification_mode, chat.id, new_mode
        )
        if ok:
            mode_desc = self._format_mode(new_mode)
            await update.message.reply_text(f"✅ 通知模式已切换为: {mode_desc}")
        else:
            await update.message.reply_text("❌ 切换失败，请先 /start 初始化")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat and not await asyncio.to_thread(self.chat_storage.get_chat, chat.id):
            chat_info = {
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            }
            await asyncio.to_thread(self.chat_storage.add_chat, chat.id, chat_info)

        active_chats = await asyncio.to_thread(self.chat_storage.get_active_chats)
        active_count = len(active_chats)
        mode = (
            await asyncio.to_thread(self.chat_storage.get_notification_mode, chat.id)
            if chat
            else "all"
        )
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
        started_at = time.monotonic()
        try:
            msg = await self._generate_report(chat.id)
            await update.message.reply_text(
                msg, parse_mode="HTML", disable_web_page_preview=True
            )
        except Exception as e:
            await update.message.reply_text(f"❌ 生成报告失败: {e}")
        finally:
            print(f"ℹ️ /report handled in {time.monotonic() - started_at:.3f}s")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = """🤖 可用命令:
/start - 订阅并初始化
/status - 查看运行状态
/mode - 查看当前通知模式
/setmode <all|trending|anomaly> - 切换通知模式 (管理员)
/report - 查看今日趋势汇总报告
/help - 查看命令说明"""
        await update.message.reply_text(msg)

    async def _handle_chat_member_updated(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        result = update.my_chat_member
        chat = result.chat
        new_status = result.new_chat_member.status
        old_status = result.old_chat_member.status

        if old_status in ["left", "kicked"] and new_status in [
            "member",
            "administrator",
        ]:
            existing_chat = await asyncio.to_thread(self.chat_storage.get_chat, chat.id)
            if not existing_chat:
                chat_name = chat.title or chat.first_name or "未知"
                welcome_msg = f"""👋 已加入 {self._get_chat_type_name(chat.type)} '{chat_name}'

请发送 /start 订阅通知
命令: /start /status /help"""
                try:
                    await context.bot.send_message(chat_id=chat.id, text=welcome_msg)
                except Exception as e:
                    print(f"⚠️  发送欢迎消息失败: {e}")
                return

            chat_info = {
                "type": chat.type,
                "title": chat.title,
                "username": chat.username,
                "first_name": chat.first_name,
                "last_name": chat.last_name,
            }
            await asyncio.to_thread(self.chat_storage.add_chat, chat.id, chat_info)

            chat_name = chat.title or chat.first_name or "未知"
            welcome_msg = f"""👋 已添加到 {self._get_chat_type_name(chat.type)} '{chat_name}'

✅ 已启用通知
命令: /status /help"""

            try:
                await context.bot.send_message(chat_id=chat.id, text=welcome_msg)
            except Exception as e:
                print(f"⚠️  发送欢迎消息失败: {e}")

        elif old_status in ["member", "administrator"] and new_status in [
            "left",
            "kicked",
        ]:
            await asyncio.to_thread(self.chat_storage.remove_chat, chat.id)

    def _get_chat_type_name(self, chat_type: str) -> str:
        type_map = {
            "private": "私聊",
            "group": "群组",
            "supergroup": "超级群组",
            "channel": "频道",
        }
        return type_map.get(chat_type, "聊天")

    def _build_inline_keyboard(
        self, token_address: str = None, chain: str = None
    ) -> Optional[InlineKeyboardMarkup]:
        """根据配置生成内联按钮键盘，支持按链过滤"""
        if not MESSAGE_BUTTONS or not token_address:
            return None
        if InlineKeyboardButton is None or InlineKeyboardMarkup is None:
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
            rows.append(buttons[i : i + 3])

        return InlineKeyboardMarkup(rows)

    @staticmethod
    def _is_permanent_destination_error(error: TelegramError) -> bool:
        if isinstance(error, Forbidden):
            return True
        if not isinstance(error, BadRequest):
            return False
        message = str(error).lower()
        return any(
            marker in message
            for marker in (
                "chat not found",
                "bot was kicked",
                "user is deactivated",
                "channel direct messages topic must be specified",
                "message thread not found",
            )
        )

    async def _send_to_chat(self, send_fn, chat_id: int, **kwargs):
        try:
            return await send_fn(chat_id=chat_id, **kwargs), chat_id
        except ChatMigrated as error:
            new_chat_id = error.new_chat_id
            await asyncio.to_thread(
                self.chat_storage.migrate_chat, chat_id, new_chat_id
            )
            try:
                return await send_fn(chat_id=new_chat_id, **kwargs), new_chat_id
            except TelegramError as retry_error:
                if self._is_permanent_destination_error(retry_error):
                    await asyncio.to_thread(self.chat_storage.remove_chat, new_chat_id)
                raise
        except TelegramError as error:
            if self._is_permanent_destination_error(error):
                await asyncio.to_thread(self.chat_storage.remove_chat, chat_id)
            raise

    async def send_message(
        self,
        message: str,
        chat_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        token_address: str = None,
        chain: str = None,
    ) -> dict:
        """发送消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.app:
            return {}

        try:
            bot = self.app.bot
            message_ids = {}
            reply_markup = self._build_inline_keyboard(token_address, chain)

            if chat_id is not None:
                sent_msg, actual_chat_id = await self._send_to_chat(
                    bot.send_message,
                    chat_id,
                    text=message,
                    disable_web_page_preview=True,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                await asyncio.to_thread(
                    self.chat_storage.increment_message_count, actual_chat_id
                )
                message_ids[chat_id] = sent_msg.message_id
                return message_ids

            active_chats = await asyncio.to_thread(self.chat_storage.get_active_chats)

            if not active_chats:
                print("⚠️  没有活跃的聊天，消息未发送")
                return {}

            success_count = 0
            for i, chat in enumerate(active_chats):
                try:
                    # 每条消息间隔0.5秒，避免频率限制
                    if i > 0:
                        await asyncio.sleep(0.5)

                    sent_msg, actual_chat_id = await self._send_to_chat(
                        bot.send_message,
                        chat["chat_id"],
                        text=message,
                        disable_web_page_preview=True,
                        reply_to_message_id=reply_to_message_id,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                    )
                    await asyncio.to_thread(
                        self.chat_storage.increment_message_count,
                        actual_chat_id,
                    )
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

    async def send_photo(
        self,
        photo_url: str,
        caption: str,
        chat_id: Optional[int] = None,
        token_address: str = None,
        chain: str = None,
    ) -> dict:
        """发送图片消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.app:
            return {}

        try:
            bot = self.app.bot
            message_ids = {}
            reply_markup = self._build_inline_keyboard(token_address, chain)

            if chat_id is not None:
                sent_msg, actual_chat_id = await self._send_to_chat(
                    bot.send_photo,
                    chat_id,
                    photo=photo_url,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                await asyncio.to_thread(
                    self.chat_storage.increment_message_count, actual_chat_id
                )
                message_ids[chat_id] = sent_msg.message_id
                return message_ids

            active_chats = await asyncio.to_thread(self.chat_storage.get_active_chats)

            if not active_chats:
                print("⚠️  没有活跃的聊天，消息未发送")
                return {}

            success_count = 0
            for i, chat in enumerate(active_chats):
                try:
                    # 每条消息间隔0.5秒，避免频率限制
                    if i > 0:
                        await asyncio.sleep(0.5)

                    sent_msg, actual_chat_id = await self._send_to_chat(
                        bot.send_photo,
                        chat["chat_id"],
                        photo=photo_url,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                    )
                    await asyncio.to_thread(
                        self.chat_storage.increment_message_count,
                        actual_chat_id,
                    )
                    message_ids[chat["chat_id"]] = sent_msg.message_id
                    success_count += 1
                except TelegramError as e:
                    if "Flood control" in str(e):
                        print(f"⚠️  频率限制，跳过发送图片到 {chat['chat_id']}")
                    else:
                        print(
                            f"❌ 发送图片到 {chat['chat_id']} 失败: {e} | url={photo_url}"
                        )

            return message_ids

        except Exception as e:
            print(f"❌ 发送图片消息时发生错误: {e} | url={photo_url}")
            return {}

    def send_sync(
        self,
        message: str,
        chat_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        token_address: str = None,
        chain: str = None,
    ) -> dict:
        """同步发送消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.bot_loop:
            return {}

        try:
            return self._run_coroutine_sync(
                self.send_message(
                    message, chat_id, reply_to_message_id, token_address, chain
                )
            )
        except Exception as e:
            print(f"❌ 同步发送失败: {e}")
            return {}

    def _run_coroutine_sync(self, coroutine, timeout: float = 10):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.bot_loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise

    def send_photo_sync(
        self,
        photo_url: str,
        caption: str,
        chat_id: Optional[int] = None,
        token_address: str = None,
        chain: str = None,
    ) -> dict:
        """同步发送图片消息，返回 {chat_id: message_id} 字典"""
        if not self.enabled or not self.bot_loop:
            return {}

        try:
            return self._run_coroutine_sync(
                self.send_photo(photo_url, caption, chat_id, token_address, chain)
            )
        except Exception as e:
            print(f"❌ 同步发送图片失败: {e} | url={photo_url}")
            return {}

    def send_with_reply_sync(
        self,
        message: str,
        token_address: str,
        storage,
        chat_id: Optional[int] = None,
        chain: str = None,
    ) -> bool:
        """发送消息并引用首次通知（如果存在），带按钮"""
        if not self.enabled or not self.bot_loop:
            return False

        try:
            # 获取所有需要发送的聊天
            if chat_id is not None:
                chats = [{"chat_id": chat_id}]
            else:
                chats = self.chat_storage.get_active_chats()

            if not chats:
                return False

            # 为每个聊天分别发送（因为 reply_to_message_id 不同）
            all_sent = True
            for chat in chats:
                cid = chat["chat_id"]
                reply_to_id = storage.get_telegram_message_id(token_address, cid)

                message_ids = self._run_coroutine_sync(
                    self.send_message(message, cid, reply_to_id, token_address, chain)
                )
                if cid not in message_ids:
                    all_sent = False

            return all_sent
        except Exception as e:
            print(f"❌ 同步发送（带引用）失败: {e}")
            return False

    def _updater_running(self) -> bool:
        app = self.app
        if app is None:
            return False
        updater = getattr(app, "updater", None)
        if updater is None:
            return False
        return bool(getattr(updater, "running", False))

    def _is_worker_alive(self) -> bool:
        if self._worker_error is not None:
            return False
        if not self._ready_event.is_set():
            return False
        if not self.bot_thread or not self.bot_thread.is_alive():
            return False
        if self.bot_loop is None:
            return False
        if not self._updater_running():
            return False
        return True

    def _polling_backlog_stale(self) -> bool:
        """Detect getUpdates stuck: Telegram has pending updates but we never receive them."""
        if not self.app or not self.bot_loop:
            return False
        now = time.time()
        if self._started_at <= 0 or (now - self._started_at) < _BACKLOG_GRACE_SECONDS:
            return False
        if (
            self._last_update_at
            and (now - self._last_update_at) < _BACKLOG_STALE_SECONDS
        ):
            return False
        try:
            info = self._run_coroutine_sync(self.app.bot.get_webhook_info(), timeout=15)
            pending = int(getattr(info, "pending_update_count", 0) or 0)
        except Exception as e:
            print(f"⚠️ Telegram backlog check failed: {e}")
            return False
        if pending <= 0:
            return False
        print(
            f"⚠️ Telegram pending updates not draining: pending={pending} "
            f"last_update_age="
            f"{'never' if not self._last_update_at else f'{now - self._last_update_at:.0f}s'}"
        )
        return True

    def start_bot(self):
        if not self.enabled:
            return

        if self.bot_thread and self.bot_thread.is_alive():
            # Already running; let ensure_healthy decide whether to recover.
            return

        self._ready_event.clear()
        self._worker_error = None
        self._last_update_at = 0.0
        self._started_at = 0.0

        def run_bot():
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)

            try:
                self._setup_application()

                self.bot_loop.run_until_complete(self.app.initialize())
                self.bot_loop.run_until_complete(self.app.start())
                self.bot_loop.run_until_complete(
                    self.app.updater.start_polling(
                        allowed_updates=Update.ALL_TYPES,
                        timeout=_GET_UPDATES_TIMEOUT,
                        drop_pending_updates=False,
                        bootstrap_retries=-1,
                        error_callback=self._on_polling_error,
                    )
                )
                self._started_at = time.time()
                self._ready_event.set()
                print("✅ Telegram polling started")
                self.bot_loop.run_forever()
            except Exception as e:
                self._worker_error = e
                self._ready_event.set()
                print(f"❌ Bot 线程错误: {e}")
                import traceback

                traceback.print_exc()
            finally:
                try:
                    if self.app and self.bot_loop and not self.bot_loop.is_closed():
                        if self._updater_running():
                            self.bot_loop.run_until_complete(self.app.updater.stop())
                        self.bot_loop.run_until_complete(self.app.stop())
                        self.bot_loop.run_until_complete(self.app.shutdown())
                except Exception:
                    pass
                try:
                    if self.bot_loop and not self.bot_loop.is_closed():
                        self.bot_loop.close()
                except Exception:
                    pass
                self.bot_loop = None
                self.app = None

        self.bot_thread = threading.Thread(
            target=run_bot, daemon=True, name="telegram-bot-worker"
        )
        self.bot_thread.start()

        if not self._ready_event.wait(timeout=_WORKER_START_TIMEOUT):
            raise TelegramRuntimeError("Telegram worker startup timed out")
        # Startup path: report failure immediately; runtime path self-heals.
        if not self._is_worker_alive():
            err = self._worker_error
            if err is not None:
                raise TelegramRuntimeError("Telegram worker failed") from err
            raise TelegramRuntimeError("Telegram worker is not running")

    def restart_bot(self):
        """Stop and start the Telegram worker to recover from dead polling."""
        with self._restart_lock:
            print("🔄 Restarting Telegram worker...")
            self.stop_bot()
            # Brief pause so Telegram releases getUpdates offset/session cleanly.
            time.sleep(1.0)
            self.start_bot()

    def ensure_healthy(self, *, allow_restart: bool = True) -> None:
        if not self.enabled:
            return

        alive = self._is_worker_alive()
        backlog_stale = alive and self._polling_backlog_stale()
        if alive and not backlog_stale:
            return

        if not allow_restart:
            if self._worker_error is not None:
                raise TelegramRuntimeError(
                    "Telegram worker failed"
                ) from self._worker_error
            if backlog_stale:
                raise TelegramRuntimeError("Telegram polling backlog not draining")
            raise TelegramRuntimeError("Telegram worker is not running")

        reason = "backlog not draining" if backlog_stale else "worker not alive"
        print(f"⚠️ Telegram unhealthy ({reason}); attempting auto-restart")
        try:
            self.restart_bot()
        except TelegramRuntimeError:
            raise
        except Exception as e:
            raise TelegramRuntimeError("Telegram worker restart failed") from e

        if not self._is_worker_alive():
            err = self._worker_error
            if err is not None:
                raise TelegramRuntimeError(
                    "Telegram worker failed after restart"
                ) from err
            raise TelegramRuntimeError("Telegram worker is not running after restart")
        print("✅ Telegram worker recovered")

    def stop_bot(self):
        loop = self.bot_loop
        thread = self.bot_thread
        if not loop and not thread:
            return

        try:
            if loop and not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)
            if thread and thread.is_alive():
                thread.join(timeout=10)
        except Exception as e:
            print(f"⚠️  停止 Bot 时出错: {e}")
        finally:
            self.bot_thread = None
            # Worker finally clears these; force-reset if the thread never did.
            self.bot_loop = None
            self.app = None


notifier = TelegramNotifier()


def send_telegram_notification(message: str, chat_id: Optional[int] = None) -> dict:
    """向后兼容的发送函数，返回 {chat_id: message_id} 字典"""
    return notifier.send_sync(message, chat_id)
