import os
import json


def _as_bool(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required env: {name}")
    return value


# 基础设置
CHECK_INTERVAL = int(_required_env("BOT_CHECK_INTERVAL"))
BOT_CHAIN = _required_env("BOT_CHAIN").lower()
CHAINS = [BOT_CHAIN]

# 汇总报告配置
SUMMARY_REPORT_HOURS = [0, 4, 8, 12, 16, 20]
SUMMARY_TOP_N = 3

# 通知冷却（小时）
NOTIFY_COOLDOWN_HOURS = int(_required_env("BOT_NOTIFY_COOLDOWN_HOURS"))

# 倍数通知确认次数
MULTIPLIER_CONFIRMATIONS = int(_required_env("BOT_MULTIPLIER_CONFIRMATIONS"))

# 白名单配置（空配置表示不过滤）
CHAIN_ALLOWLISTS = {BOT_CHAIN: {}}
_bot_allowlist_raw = os.getenv("BOT_CHAIN_ALLOWLIST_JSON", "").strip()
if _bot_allowlist_raw:
    try:
        CHAIN_ALLOWLISTS[BOT_CHAIN] = json.loads(_bot_allowlist_raw)
    except json.JSONDecodeError:
        pass

# 存储
DATA_DIR = _required_env("BOT_DATA_DIR")
STORAGE_DIR = DATA_DIR
CHATS_FILE = os.path.join(DATA_DIR, "telegram_chats.json")

# 运行
SILENT_INIT = True
DRY_RUN = _as_bool(os.getenv("BOT_DRY_RUN", "0"))

# Telegram
TELEGRAM_BOT_TOKEN = _required_env("BOT_TELEGRAM_TOKEN")
ENABLE_TELEGRAM = True

# Telegram 消息按钮配置
# 支持 {token_address} 占位符，会自动替换为合约地址
# chain: 指定链，只在该链的通知中显示，不填则所有链都显示
MESSAGE_BUTTONS = [
    {"text": "Pepe BSC", "url": "https://t.me/PepeboostBsc_bot?start=ref_0c9zso_ca_{token_address}", "chain": "bsc"},
    {"text": "Pepe SOL", "url": "https://t.me/pepeboost_sol06_bot?start=ref_0b22dk_ca_{token_address}", "chain": "sol"},
    {"text": "XXYY", "url": "https://pro.xxyy.io/sol/{token_address}?ref=ncuYXE", "chain": "sol"},
    {"text": "XXYY", "url": "https://pro.xxyy.io/bsc/{token_address}?ref=ncuYXE", "chain": "bsc"},
]
