"""
Telegram Forwarder Bot - main bot class
"""

import logging
import os
from telethon import TelegramClient, events
from config.loader import ConfigLoader
from config.validator import ConfigValidator
from services.telegram_service import TelegramService
from services.message_service import MessageService
from core.event_handler import EventHandler
from core.forwarder import MessageForwarder

logger = logging.getLogger(__name__)


class TelegramForwarderBot:
    """Telegram 转发机器人主类"""

    def __init__(self, config: ConfigLoader):
        self.config = config
        self.client = None
        self.telegram_service = None
        self.message_service = None
        self.forwarder = None
        self.event_handler = None

    async def initialize(self) -> bool:
        """
        初始化机器人

        Returns:
            成功返回 True，失败返回 False
        """
        logger.info("=" * 60)
        logger.info("启动 Telegram Forwarder Bot")
        logger.info(f"日志级别: {os.environ.get('LOG_LEVEL', 'INFO')}")
        logger.info("=" * 60)

        # 验证配置
        try:
            ConfigValidator.validate(self.config)
        except Exception as e:
            logger.error(f"✗ 配置验证失败: {e}")
            return False

        # 创建 Telegram 客户端
        try:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            # 处理 session 路径
            session_name = self.config.SESSION_NAME
            if os.path.isabs(session_name):
                # 绝对路径，直接使用
                session_path = session_name
            else:
                # 相对路径，相对于项目根目录
                session_path = os.path.join(current_dir, session_name)

            # 确保会话文件的目录存在
            session_dir = os.path.dirname(session_path)
            if session_dir and not os.path.exists(session_dir):
                os.makedirs(session_dir, exist_ok=True)
                logger.info(f"创建会话目录: {session_dir}")

            logger.info(f"会话文件路径: {session_path}")
            logger.info(
                f"配置文件路径: {getattr(self.config, 'config_path', 'unknown')}"
            )

            self.client = TelegramClient(
                session_path, self.config.API_ID, self.config.API_HASH
            )

            # 初始化服务层
            self.telegram_service = TelegramService(self.client)
            self.message_service = MessageService(
                self.client,
                flood_wait_max_seconds=self.config.FLOOD_WAIT_MAX_SECONDS,
            )

            # 初始化核心业务层
            self.forwarder = MessageForwarder(self.message_service)
            self.event_handler = EventHandler(self.config, self.forwarder)

            # 启动客户端
            if not await self.telegram_service.start():
                return False

            # 注册事件处理器
            self._register_event_handlers()

            return True

        except ValueError as e:
            logger.error(f"创建 Telegram 客户端失败: {e}")
            return False
        except Exception as e:
            logger.error(f"初始化时发生错误: {e}", exc_info=True)
            return False

    def _register_event_handlers(self):
        """注册事件处理器"""

        @self.client.on(events.NewMessage(chats=self.event_handler.get_event_filter()))
        async def handle_message(event):
            await self.event_handler.handle_new_message(event)

        @self.client.on(events.Album(chats=self.event_handler.get_event_filter()))
        async def handle_album(event):
            await self.event_handler.handle_album(event)

    async def validate_configuration(self):
        """验证所有群组和规则配置"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("验证群组和规则配置")
        logger.info("=" * 60)

        for idx, group in enumerate(self.config.groups):
            status = "✓" if group.enabled else "✗"
            logger.info(f"{idx + 1}. [{status}] {group.name}")

            if not group.enabled:
                logger.info(f"   状态: 已禁用")
                logger.info("")
                continue

            # 验证源群组
            source_info = await self.telegram_service.get_entity_info(group.source_id)
            if source_info["is_valid"]:
                logger.info(
                    f"   源: {self.telegram_service.format_entity_info(source_info)}"
                )
            else:
                logger.warning(f"   源: 无效 - {group.source_id}")

            # 显示规则信息
            enabled_rules = [r for r in group.rules if r.enabled]
            logger.info(
                f"   规则: {len(group.rules)} 条 (已启用: {len(enabled_rules)})"
            )

            for rule_idx, rule in enumerate(group.rules):
                rule_status = "✓" if rule.enabled else "✗"
                rule_num = rule_idx + 1
                logger.info(f"     {rule_num}. [{rule_status}] 规则 {rule_num}")

                if not rule.enabled:
                    continue

                # 验证目标群组
                logger.info(f"        目标: {len(rule.target_ids)} 个群组")
                for target_id in rule.target_ids:
                    target_info = await self.telegram_service.get_entity_info(target_id)
                    if target_info["is_valid"]:
                        logger.info(
                            f"          → {self.telegram_service.format_entity_info(target_info)}"
                        )
                    else:
                        logger.warning(f"          → 无效 - {target_id}")

                # 显示过滤规则信息
                logger.info(f"        过滤模式: {rule.filter_mode}")
                if rule.filter_mode != "all":
                    logger.info(f"        过滤规则: {len(rule.filter_rules)} 条")

            logger.info("")

        logger.info("=" * 60)
        logger.info("🚀 机器人正在运行，监听消息中...")
        logger.info("=" * 60)
        logger.info("")

    async def send_startup_notifications(self):
        """向所有转发目标群组发送启动通知"""
        logger.info("发送启动通知到目标群组...")

        summary = ""
        if self.config.STARTUP_NOTIFICATION_DETAILS:
            group_lines, user_lines = self._build_monitor_summary()
            if group_lines:
                summary += "📡 监控群组:\n" + "\n".join(group_lines) + "\n\n"
            if user_lines:
                summary += "👤 监控用户:\n" + "\n".join(user_lines) + "\n\n"

        # 收集所有唯一的目标群组
        notified_targets = set()

        for group in self.config.groups:
            if not group.enabled:
                continue

            for rule in group.rules:
                if not rule.enabled:
                    continue

                for target_id in rule.target_ids:
                    if target_id in notified_targets:
                        continue

                    try:
                        message = (
                            "🤖 **Telegram Forwarder Bot 已启动**\n\n"
                            "📡 正在监听并转发消息到此群组\n\n"
                            f"{summary}"
                            f"⏰ 启动时间: {self._get_current_time()}"
                        )
                        await self.client.send_message(target_id, message)
                        notified_targets.add(target_id)
                        logger.info(f"  ✓ 已通知: {target_id}")
                    except Exception as e:
                        logger.warning(f"  ✗ 通知失败 {target_id}: {e}")

        logger.info(f"启动通知发送完成，共通知 {len(notified_targets)} 个群组")

    def _build_monitor_summary(self):
        """构建监控群组与用户的摘要文本"""
        enabled_groups = [g for g in self.config.groups if g.enabled]

        group_lines = []
        for group in enabled_groups:
            group_lines.append(f"- {group.name} ({group.source_id})")

        user_lines = []
        for group in enabled_groups:
            enabled_rules = [r for r in group.rules if r.enabled]

            # 任何 all 规则都视为全量用户
            if any(r.filter_mode == "all" for r in enabled_rules):
                user_lines.append(f"- {group.name}: 全部用户")
                continue

            users = set()
            for rule in enabled_rules:
                for filter_rule in rule.filter_rules:
                    self._collect_users_from_rule(filter_rule, users)

            if users:
                formatted_users = ", ".join(sorted(self._format_user(u) for u in users))
                user_lines.append(f"- {group.name}: {formatted_users}")
            else:
                user_lines.append(f"- {group.name}: 未设置用户过滤")

        return group_lines, user_lines

    def _collect_users_from_rule(self, rule, users_set):
        """从规则中递归收集 user/user_conditional 过滤的用户"""
        if not isinstance(rule, dict):
            return

        rule_type = rule.get("type")
        config = rule.get("config", {})

        if rule_type in ("user", "user_conditional"):
            for user in config.get("users", []):
                users_set.add(user)

            for condition in config.get("conditions", []):
                self._collect_users_from_rule(condition, users_set)
            return

        if rule_type == "composite":
            for sub_rule in config.get("rules", []):
                self._collect_users_from_rule(sub_rule, users_set)

    def _format_user(self, user) -> str:
        """格式化用户标识"""
        if isinstance(user, str):
            if user.lstrip("-").isdigit():
                return user
            return user if user.startswith("@") else f"@{user}"
        return str(user)

    def _get_current_time(self) -> str:
        """获取当前格式化时间（北京时间 UTC+8）"""
        from datetime import datetime, timezone, timedelta

        beijing_tz = timezone(timedelta(hours=8))
        return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

    async def run(self):
        """运行机器人"""
        try:
            # 验证配置
            await self.validate_configuration()

            # 发送启动通知
            if self.config.SEND_STARTUP_NOTIFICATION:
                await self.send_startup_notifications()

            # 保持运行直到中断
            await self.client.run_until_disconnected()

        except KeyboardInterrupt:
            logger.info("\n收到中断信号，正在退出...")
        except Exception as e:
            logger.error(f"运行时发生错误: {e}", exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """停止机器人"""
        if self.telegram_service:
            await self.telegram_service.disconnect()
        logger.info("机器人已停止")
