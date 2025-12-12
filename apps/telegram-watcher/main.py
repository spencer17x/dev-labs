#!/usr/bin/env python3
"""
Telegram消息监听服务
使用Telethon库监听所有消息
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
import aiohttp
from typing import Optional, Tuple
from config_loader import load_config


def setup_logging(config):
    """配置日志系统"""
    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 从配置获取日志设置
    log_filename = config.LOG_FILENAME
    log_path_env = config.LOG_PATH
    log_level = config.LOG_LEVEL.upper()

    # 处理日志路径
    if not os.path.isabs(log_path_env):
        log_path = os.path.join(current_dir, log_path_env)
    else:
        log_path = log_path_env

    # 创建日志目录（如果不存在）
    if not os.path.exists(log_path):
        os.makedirs(log_path, exist_ok=True)

    # 构建完整的日志文件路径
    log_file = os.path.join(log_path, log_filename)

    # 配置日志级别
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    log_level_obj = level_map.get(log_level, logging.INFO)

    # 配置日志
    logging.basicConfig(
        level=log_level_obj,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,  # 强制重新配置
    )

    logger = logging.getLogger(__name__)
    logger.info(f"日志文件保存在: {log_file}")
    logger.info(f"日志级别: {log_level}")

    return logger


class TelegramListener:
    def __init__(self, config):
        self.config = config
        self.api_id = config.API_ID
        self.api_hash = config.API_HASH
        self.phone_number = config.PHONE_NUMBER
        self.bot_token = config.BOT_TOKEN

        # 获取当前脚本所在目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 获取会话文件路径配置
        session_file_env = config.SESSION_NAME

        # 如果是相对路径，则相对于项目目录
        if not os.path.isabs(session_file_env):
            self.session_file = os.path.join(current_dir, session_file_env)
        else:
            self.session_file = session_file_env

        # 获取session目录（用于创建目录）
        self.session_path = os.path.dirname(self.session_file)

        # 检查是否使用机器人模式（排除占位符值）
        self.is_bot_mode = bool(self.bot_token and self.bot_token != "your_bot_token")

        # 监听配置 - 从配置文件获取
        self.listen_targets = config.get_listen_targets()
        self.exclude_chats = config.get_exclude_chats()

        # Webhook 配置
        self.webhook_url = config.WEBHOOK_URL
        self.webhook_timeout = config.WEBHOOK_TIMEOUT

        # 代理配置
        self.proxy_url = config.PROXY_URL.strip() if config.PROXY_URL else ""
        self.proxy_host = config.PROXY_HOST.strip() if config.PROXY_HOST else ""
        self.proxy_port = config.PROXY_PORT.strip() if config.PROXY_PORT else ""
        self.proxy_type = config.PROXY_TYPE.strip().lower() if config.PROXY_TYPE else ""

        # Telethon 代理参数（如果配置了）
        self._telethon_proxy = self._build_telethon_proxy()

        # 存储解析后的聊天实体
        self.listen_target_entities = []
        self.exclude_chat_entities = []

        if not all([self.api_id, self.api_hash]):
            raise ValueError("请在.env文件中设置TELEGRAM_API_ID和TELEGRAM_API_HASH")

        # 用户模式下，phone_number 可以为空，Telethon 会在启动时询问

        # 创建session目录（如果不存在）
        if self.session_path and not os.path.exists(self.session_path):
            os.makedirs(self.session_path, exist_ok=True)
            logger.info(f"创建session目录: {self.session_path}")

        # 记录完整的session文件路径
        logger.info(f"Session文件将保存在: {self.session_file}")

        # 记录运行模式
        if self.is_bot_mode:
            logger.info("运行模式: 机器人模式")
        else:
            logger.info("运行模式: 用户模式")
            logger.info("运行模式: 用户模式")

        # 记录监听配置
        self._log_listen_config()

        # 如果配置了代理，将代理传给 Telethon 客户端
        if self._telethon_proxy:
            # 仅用于日志展示的协议名
            scheme_name = "proxy"
            if self.proxy_url:
                try:
                    from urllib.parse import urlparse

                    u = urlparse(self.proxy_url)
                    if u.scheme:
                        scheme_name = u.scheme
                except Exception:
                    pass
            logger.info(
                f"使用代理连接 Telegram: {scheme_name}://{self._telethon_proxy[1]}:{self._telethon_proxy[2]}"
            )
            self.client = TelegramClient(
                self.session_file,
                int(self.api_id),
                self.api_hash,
                proxy=self._telethon_proxy,  # type: ignore[arg-type]
            )
        else:
            logger.info("未配置代理，直连 Telegram")
            self.client = TelegramClient(
                self.session_file, int(self.api_id), self.api_hash
            )

    def _build_telethon_proxy(self) -> Optional[Tuple[int, str, int]]:
        """根据配置构建 Telethon 代理参数。

        Telethon 接受形如 (proxy_type, addr, port) 的三元组，proxy_type 使用 PySocks 常量。
        """
        # 如果未配置代理，直接返回
        if not (self.proxy_url or self.proxy_host or self.proxy_port):
            return None
        # 未安装 PySocks 时，无法构建代理
        try:
            import socks  # type: ignore
        except Exception:
            logger.warning(
                "未安装 PySocks，忽略代理配置。请在 requirements.txt 安装 PySocks"
            )
            return None
        # 优先解析 PROXY_URL，例如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080
        url = self.proxy_url
        host = self.proxy_host
        port = self.proxy_port
        ptype = self.proxy_type

        if url:
            try:
                from urllib.parse import urlparse

                u = urlparse(url)
                if u.scheme and u.hostname and u.port:
                    scheme = u.scheme.lower()
                    if scheme in {"http", "https"}:
                        return (socks.HTTP, u.hostname, int(u.port))
                    if scheme == "socks5":
                        return (socks.SOCKS5, u.hostname, int(u.port))
                    else:
                        logger.warning(f"不支持的代理协议: {scheme}")
                else:
                    logger.warning("PROXY_URL 格式无效，需形如 http://host:port")
            except Exception as e:
                logger.warning(f"解析 PROXY_URL 失败: {e}")

        # 其次尝试独立变量
        if host and port:
            scheme = ptype if ptype in {"http", "https", "socks5"} else "http"
            try:
                proxy_const = (
                    socks.HTTP if scheme in {"http", "https"} else socks.SOCKS5
                )
                return (proxy_const, host, int(port))
            except Exception as e:
                logger.warning(f"解析代理主机/端口失败: {e}")

        return None

    def _log_listen_config(self):
        """记录监听配置"""
        if not self.listen_targets:
            logger.info("监听配置: 未配置监听目标，将监听所有消息")
            if self.exclude_chats:
                logger.info(f"排除聊天: {', '.join(self.exclude_chats)}")
            return

        config_parts = []

        if self.listen_targets:
            target_names = [str(t) for t in self.listen_targets]
            config_parts.append(f"监听目标: {', '.join(target_names)}")

        if self.exclude_chats:
            exclude_names = [str(e) for e in self.exclude_chats]
            config_parts.append(f"排除聊天: {', '.join(exclude_names)}")

        logger.info(f"监听配置: {' | '.join(config_parts)}")
        logger.info("只会处理来自配置目标的消息")

        # 显示 webhook 配置
        if self.webhook_url:
            logger.info(
                f"Webhook 配置: {self.webhook_url} (超时: {self.webhook_timeout}s)"
            )
        else:
            logger.info("Webhook 配置: 未配置")

    async def _try_resolve_chat(self, chat_identifier):
        """尝试解析聊天实体，支持多种ID格式"""
        try:
            # 首先尝试直接解析
            return await self.client.get_entity(chat_identifier)
        except Exception as e1:
            logger.debug(f"直接解析 {chat_identifier} 失败: {e1}")

            # 如果是纯数字，尝试不同的格式
            if chat_identifier.isdigit():
                chat_id = int(chat_identifier)

                # 尝试负数格式（普通群组）
                try:
                    return await self.client.get_entity(-chat_id)
                except Exception as e2:
                    logger.debug(f"负数格式 -{chat_id} 失败: {e2}")

                # 尝试超级群组格式
                try:
                    supergroup_id = -1000000000000 - chat_id
                    return await self.client.get_entity(supergroup_id)
                except Exception as e3:
                    logger.debug(f"超级群组格式 {supergroup_id} 失败: {e3}")

            # 如果是负数字符串，尝试去掉负号
            elif chat_identifier.startswith("-") and chat_identifier[1:].isdigit():
                try:
                    positive_id = chat_identifier[1:]
                    return await self.client.get_entity(positive_id)
                except Exception as e4:
                    logger.debug(f"正数格式 {positive_id} 失败: {e4}")

            return None

    async def _resolve_chat_entities(self):
        """解析聊天实体"""
        try:
            # 解析监听目标
            for target in self.listen_targets:
                entity = await self._try_resolve_chat(target)
                if entity:
                    self.listen_target_entities.append(entity)
                    entity_name = (
                        self.get_chat_title(entity)
                        if hasattr(entity, "title") or not hasattr(entity, "first_name")
                        else self.get_sender_name(entity)
                    )
                    logger.info(f"添加监听目标: {entity_name} ({target})")
                else:
                    logger.warning(f"无法解析监听目标 {target}")

            # 解析排除的聊天
            for chat in self.exclude_chats:
                entity = await self._try_resolve_chat(chat)
                if entity:
                    self.exclude_chat_entities.append(entity)
                    logger.info(f"添加排除聊天: {self.get_chat_title(entity)} ({chat})")
                else:
                    logger.warning(f"无法解析排除聊天 {chat}")

        except Exception as e:
            logger.error(f"解析聊天实体时出错: {e}")

    def _should_process_message(self, sender, chat):
        """检查是否应该处理此消息"""
        # 首先检查排除列表（优先级最高）
        if self.exclude_chat_entities:
            for exclude_entity in self.exclude_chat_entities:
                if chat and chat.id == exclude_entity.id:
                    return False

        # 如果没有设置任何监听条件，处理所有消息（除了排除的）
        if not self.listen_targets:
            return True

        # 检查是否匹配监听目标
        for listen_entity in self.listen_target_entities:
            # 检查聊天匹配
            if chat and chat.id == listen_entity.id:
                return True
            # 检查发送者匹配
            if sender and sender.id == listen_entity.id:
                return True

        return False

    async def send_webhook(self, message_data):
        """发送 webhook 消息"""
        if not self.webhook_url:
            return

        try:
            # 配置 aiohttp 代理（如果有）
            timeout = aiohttp.ClientTimeout(total=self.webhook_timeout)
            # 对于 aiohttp，HTTP/HTTPS 代理通常使用 PROXY_URL；SOCKS 需 aiohttp_socks（此处不启用）
            proxy_arg = None
            if self.proxy_url and self.proxy_url.startswith(("http://", "https://")):
                proxy_arg = self.proxy_url

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.webhook_url,
                    json=message_data,
                    headers={"Content-Type": "application/json"},
                    proxy=proxy_arg,
                ) as response:
                    if response.status == 200:
                        logger.debug("Webhook 发送成功")
                    else:
                        logger.warning(f"Webhook 响应状态: {response.status}")

        except Exception as e:
            logger.warning(f"Webhook 发送失败: {e}")

    def format_message_for_webhook(self, message_info, event):
        """格式化消息为 webhook 数据结构"""
        return {
            "message_id": message_info["message_id"],
            "date": message_info["date"],
            "recv_date": message_info["recv_date"],
            "timestamp": int(event.message.date.timestamp()),
            "text": message_info["text"],
            "sender_id": message_info["sender_id"],
            "sender_name": message_info["sender_name"],
            "chat_id": message_info["chat_id"],
            "chat_title": message_info["chat_title"],
            "chat_type": message_info["chat_type"],
            "media_type": message_info["media_type"],
            "is_reply": message_info["is_reply"],
        }

    async def start(self):
        """启动客户端"""
        try:

            if self.is_bot_mode:
                # 机器人模式
                await self.client.start(bot_token=self.bot_token)
                logger.info("Telegram机器人启动成功")

                # 获取机器人信息
                me = await self.client.get_me()
                logger.info(f"机器人信息: {me.first_name} (@{me.username})")
                logger.info(
                    "注意: 机器人模式只能接收发送给机器人的消息和群组中@机器人的消息"
                )
            else:
                # 用户模式
                if self.phone_number:
                    # 使用预设的手机号码
                    await self.client.start(phone=self.phone_number)
                else:
                    # 交互式登录，让用户输入手机号码
                    logger.info(
                        "请输入你的手机号码（包含国家代码，如：+86138xxxxxxxx）"
                    )

                    def phone_input():
                        return input("手机号码: ")

                    def code_input():
                        return input("验证码: ")

                    await self.client.start(phone=phone_input, code_callback=code_input)
                logger.info("Telegram用户客户端启动成功")

                # 获取当前用户信息
                me = await self.client.get_me()
                logger.info(f"已登录用户: {me.first_name} (@{me.username})")
                logger.info("用户模式可以监听所有可访问的消息")

            # 解析聊天实体
            await self._resolve_chat_entities()

            # 注册事件处理器
            self.client.add_event_handler(self.message_handler, events.NewMessage)

            logger.info("开始监听消息...")
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"启动失败: {e}")
            raise

    async def message_handler(self, event):
        """消息处理器"""
        try:
            message = event.message
            sender = await event.get_sender()
            chat = await event.get_chat()

            # 检查是否应该处理此消息
            if not self._should_process_message(sender, chat):
                return

            # 获取消息基本信息
            message_info = {
                "message_id": message.id,
                "date": message.date.strftime("%Y-%m-%d %H:%M:%S"),
                "recv_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": message.text or "[媒体消息]",
                "sender_id": sender.id if sender else None,
                "sender_name": self.get_sender_name(sender),
                "chat_id": chat.id if chat else None,
                "chat_title": self.get_chat_title(chat),
                "chat_type": self.get_chat_type(event.message.peer_id),
                "is_reply": message.reply_to is not None,
                "media_type": self.get_media_type(message),
            }

            # 记录消息
            self.log_message(message_info)

            # 发送 webhook（如果配置了）
            if self.webhook_url:
                webhook_data = self.format_message_for_webhook(message_info, event)
                await self.send_webhook(webhook_data)

            # 在这里可以添加自定义的消息处理逻辑
            await self.process_message(message_info, event)

        except Exception as e:
            logger.error(f"处理消息时出错: {e}")

    def get_sender_name(self, sender):
        """获取发送者名称"""
        if not sender:
            return "Unknown"

        if hasattr(sender, "first_name"):
            name = sender.first_name or ""
            if hasattr(sender, "last_name") and sender.last_name:
                name += f" {sender.last_name}"
            if hasattr(sender, "username") and sender.username:
                name += f" (@{sender.username})"
            return name
        elif hasattr(sender, "title"):
            return sender.title
        else:
            return str(sender.id)

    def get_chat_title(self, chat):
        """获取聊天标题"""
        if not chat:
            return "Unknown"

        if hasattr(chat, "title"):
            return chat.title
        elif hasattr(chat, "first_name"):
            name = chat.first_name or ""
            if hasattr(chat, "last_name") and chat.last_name:
                name += f" {chat.last_name}"
            return name
        else:
            return str(chat.id)

    def get_chat_type(self, peer_id):
        """获取聊天类型"""
        if isinstance(peer_id, PeerUser):
            return "private"
        elif isinstance(peer_id, PeerChat):
            return "group"
        elif isinstance(peer_id, PeerChannel):
            return "channel"
        else:
            return "unknown"

    def get_media_type(self, message):
        """获取媒体类型"""
        if not message.media:
            return None

        media_type = type(message.media).__name__
        return media_type.replace("MessageMedia", "").lower()

    def log_message(self, message_info):
        """记录消息信息"""
        mode_prefix = "[BOT]" if self.is_bot_mode else "[USER]"
        log_text = (
            f"{mode_prefix} [{message_info['chat_type'].upper()}] "
            f"{message_info['chat_title']} | "
            f"{message_info['sender_name']}: "
            f"{message_info['text'][:100]}{'...' if len(message_info['text']) > 100 else ''}"
        )

        if message_info["media_type"]:
            log_text += f" [{message_info['media_type']}]"

        logger.info(log_text)

    async def process_message(self, message_info, event):
        """
        自定义消息处理逻辑
        在这里添加你的业务逻辑
        """
        # 示例: 处理特定关键词
        if message_info["text"] and "hello" in message_info["text"].lower():
            logger.info(f"检测到问候消息: {message_info['text']}")

        # 示例: 处理媒体消息
        if message_info["media_type"]:
            logger.info(f"收到媒体消息: {message_info['media_type']}")

        # 在这里可以添加更多处理逻辑，比如:
        # - 保存到数据库
        # - 转发到其他服务
        # - 触发特定操作
        pass


async def main():
    """主函数"""
    # 加载配置
    config = load_config()

    # 初始化日志
    global logger
    logger = setup_logging(config)

    # 创建监听器
    listener = TelegramListener(config)
    try:
        await listener.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"运行时错误: {e}")
    finally:
        if listener.client.is_connected():
            await listener.client.disconnect()
        logger.info("服务已停止")


if __name__ == "__main__":
    asyncio.run(main())
