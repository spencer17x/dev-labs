"""配置加载器"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv


def load_config(config_path: str = None) -> dict:
    """加载配置文件，环境变量优先"""
    # 加载 .env 文件
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.json"

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"配置文件不存在: {config_path}\n"
            "请复制 config.example.json 为 config.json 并填写配置"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 环境变量覆盖配置文件（敏感信息优先从环境变量读取）
    _override_from_env(config)

    return config


def _override_from_env(config: dict):
    """用环境变量注入敏感配置"""
    # Twitter cookies
    if os.getenv("TWITTER_AUTH_TOKEN") or os.getenv("TWITTER_CT0"):
        config.setdefault("twitter", {})
        config["twitter"]["cookies"] = {
            "auth_token": os.getenv("TWITTER_AUTH_TOKEN", ""),
            "ct0": os.getenv("TWITTER_CT0", ""),
        }

    # Four.meme
    if os.getenv("FOUR_MEME_PRIVATE_KEY"):
        config.setdefault("four_meme", {})
        config["four_meme"]["private_key"] = os.getenv("FOUR_MEME_PRIVATE_KEY")

    # Telegram
    if os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_CHAT_ID"):
        config.setdefault("telegram", {})
        config["telegram"]["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "")
        config["telegram"]["chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "")

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        config.setdefault("analyzer", {})
        config["analyzer"]["openai_api_key"] = os.getenv("OPENAI_API_KEY")
