"""
Configuration loader for Telegram Watcher
"""
import json
import os
import logging
from typing import Dict, List, Any, Union, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 加载 .env 文件中的环境变量
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


class TargetConfig:
    """监听目标配置"""

    def __init__(self, target_data: Dict[str, Any]):
        self.id = target_data.get("id", "")
        self.name = target_data.get("name", "")
        self.type = target_data.get("type", "channel")  # channel | group | user
        self.chat_id = target_data.get("chat_id")
        self.enabled = target_data.get("enabled", True)

        if not self.chat_id:
            raise ValueError(f"目标 {self.id} 缺少 chat_id 字段")

    def __repr__(self):
        return f"<TargetConfig id={self.id} chat_id={self.chat_id} enabled={self.enabled}>"


class ExcludeConfig:
    """排除聊天配置"""

    def __init__(self, exclude_data: Dict[str, Any]):
        self.chat_id = exclude_data.get("chat_id")
        self.reason = exclude_data.get("reason", "")

        if not self.chat_id:
            raise ValueError("排除配置缺少 chat_id 字段")

    def __repr__(self):
        return f"<ExcludeConfig chat_id={self.chat_id}>"


class ConfigLoader:
    """配置加载器"""

    def __init__(self, config_path: Optional[str] = None):
        # API 凭据从环境变量获取
        self.API_ID = os.environ.get("TELEGRAM_API_ID")
        self.API_HASH = os.environ.get("TELEGRAM_API_HASH")
        self.PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE_NUMBER")
        self.BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

        # 默认配置
        self.SESSION_NAME = "session/telegram_watcher_session"
        self.LOG_FILENAME = "telegram_listener.log"
        self.LOG_PATH = "logs"
        self.LOG_LEVEL = "INFO"
        self.WEBHOOK_URL = ""
        self.WEBHOOK_TIMEOUT = 5
        self.PROXY_URL = ""
        self.PROXY_HOST = ""
        self.PROXY_PORT = ""
        self.PROXY_TYPE = "http"

        # 监听目标和排除列表
        self.targets: List[TargetConfig] = []
        self.excludes: List[ExcludeConfig] = []

        # 加载配置
        if config_path:
            if os.path.exists(config_path):
                self.load_from_file(config_path)
                logger.info(f"配置已从 {config_path} 加载")
            else:
                logger.warning(f"配置文件未找到: {config_path}")
        else:
            logger.info("未提供配置文件，使用默认配置")

    def load_from_file(self, config_path: str):
        """从 JSON 文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # Session 配置
            self.SESSION_NAME = config_data.get("session_name", self.SESSION_NAME)

            # 日志配置
            log_config = config_data.get("log", {})
            self.LOG_FILENAME = log_config.get("filename", self.LOG_FILENAME)
            self.LOG_PATH = log_config.get("path", self.LOG_PATH)
            self.LOG_LEVEL = log_config.get("level", self.LOG_LEVEL)

            # Webhook 配置
            webhook_config = config_data.get("webhook", {})
            self.WEBHOOK_URL = webhook_config.get("url", self.WEBHOOK_URL)
            self.WEBHOOK_TIMEOUT = webhook_config.get("timeout", self.WEBHOOK_TIMEOUT)

            # 代理配置
            proxy_config = config_data.get("proxy", {})
            self.PROXY_URL = proxy_config.get("url", self.PROXY_URL)
            self.PROXY_HOST = proxy_config.get("host", self.PROXY_HOST)
            self.PROXY_PORT = proxy_config.get("port", self.PROXY_PORT)
            self.PROXY_TYPE = proxy_config.get("type", self.PROXY_TYPE)

            # 加载监听目标
            targets_data = config_data.get("targets", [])
            for target_data in targets_data:
                try:
                    target = TargetConfig(target_data)
                    self.targets.append(target)
                except Exception as e:
                    logger.error(f"加载目标配置失败 {target_data.get('id', 'unknown')}: {e}")

            # 加载排除列表
            excludes_data = config_data.get("exclude", [])
            for exclude_data in excludes_data:
                try:
                    exclude = ExcludeConfig(exclude_data)
                    self.excludes.append(exclude)
                except Exception as e:
                    logger.error(f"加载排除配置失败: {e}")

            # 确保 API_ID 是整数
            if self.API_ID and isinstance(self.API_ID, str):
                self.API_ID = int(self.API_ID)

            # 统计信息
            enabled_targets = sum(1 for t in self.targets if t.enabled)
            logger.info(f"API ID: {'已设置' if self.API_ID else '未设置'}")
            logger.info(f"API Hash: {'已设置' if self.API_HASH else '未设置'}")
            logger.info(f"监听目标数量: {len(self.targets)} (启用: {enabled_targets})")
            logger.info(f"排除聊天数量: {len(self.excludes)}")
            logger.info(f"日志级别: {self.LOG_LEVEL}")
            if self.WEBHOOK_URL:
                logger.info(f"Webhook: {self.WEBHOOK_URL}")
            if self.PROXY_URL or self.PROXY_HOST:
                logger.info(f"代理: 已配置")

        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            raise ValueError(f"Failed to load configuration: {e}")

    def get_listen_targets(self) -> List[str]:
        """获取启用的监听目标 chat_id 列表"""
        return [t.chat_id for t in self.targets if t.enabled]

    def get_exclude_chats(self) -> List[str]:
        """获取排除的聊天 chat_id 列表"""
        return [e.chat_id for e in self.excludes]


def get_default_config_path() -> str:
    """获取默认配置文件路径"""
    root_dir = Path(__file__).parent
    return str(root_dir / "config.json")


def load_config(config_path: Optional[str] = None) -> ConfigLoader:
    """加载配置"""
    if config_path is None:
        config_path = os.environ.get("WATCHER_CONFIG_PATH", get_default_config_path())
    return ConfigLoader(config_path)
