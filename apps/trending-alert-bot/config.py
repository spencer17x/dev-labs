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
_bot_chains_raw = os.getenv("BOT_CHAINS", "").strip()
if _bot_chains_raw:
    parsed_chains = json.loads(_bot_chains_raw)
    if not isinstance(parsed_chains, list):
        raise RuntimeError("BOT_CHAINS must be a JSON list")
    CHAINS = []
    for item in parsed_chains:
        chain = str(item).strip().lower()
        if not chain or chain in CHAINS:
            continue
        CHAINS.append(chain)
    if not CHAINS:
        raise RuntimeError("BOT_CHAINS must contain at least one chain")
else:
    BOT_CHAIN = _required_env("BOT_CHAIN").lower()
    CHAINS = [BOT_CHAIN]
BOT_CHAIN = CHAINS[0]

# 汇总报告配置
SUMMARY_REPORT_HOURS = [0, 4, 8, 12, 16, 20]
SUMMARY_TOP_N = 3

# 通知冷却（小时）
NOTIFY_COOLDOWN_HOURS = int(_required_env("BOT_NOTIFY_COOLDOWN_HOURS"))

# 倍数通知确认次数
MULTIPLIER_CONFIRMATIONS = int(_required_env("BOT_MULTIPLIER_CONFIRMATIONS"))

# 通知类型
_bot_notification_types_raw = os.getenv("BOT_NOTIFICATION_TYPES", "").strip()
if _bot_notification_types_raw:
    parsed_notification_types = json.loads(_bot_notification_types_raw)
    if not isinstance(parsed_notification_types, list):
        raise RuntimeError("BOT_NOTIFICATION_TYPES must be a JSON list")
    NOTIFICATION_TYPES = []
    for item in parsed_notification_types:
        notification_type = str(item).strip().lower()
        if not notification_type or notification_type in NOTIFICATION_TYPES:
            continue
        NOTIFICATION_TYPES.append(notification_type)
else:
    NOTIFICATION_TYPES = ["trending", "anomaly"]

_supported_notification_types = {"trending", "anomaly"}
for notification_type in NOTIFICATION_TYPES:
    if notification_type not in _supported_notification_types:
        raise RuntimeError(f"unsupported notification type: {notification_type}")

# 白名单配置（空配置表示不过滤）
CHAIN_ALLOWLISTS = {chain: {} for chain in CHAINS}
_bot_allowlist_raw = os.getenv("BOT_CHAIN_ALLOWLIST_JSON", "").strip()
if _bot_allowlist_raw:
    try:
        parsed_allowlists = json.loads(_bot_allowlist_raw)
        if isinstance(parsed_allowlists, dict):
            if "launchFrom" in parsed_allowlists or "dexName" in parsed_allowlists:
                CHAIN_ALLOWLISTS[BOT_CHAIN] = parsed_allowlists
            else:
                for chain in CHAINS:
                    chain_allowlist = parsed_allowlists.get(chain, {})
                    if isinstance(chain_allowlist, dict):
                        CHAIN_ALLOWLISTS[chain] = chain_allowlist
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
