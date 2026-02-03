import os
from dotenv import load_dotenv

load_dotenv()

# 基础设置
CHECK_INTERVAL = 15
CHAINS = ["bsc", "sol", "base"]

# 汇总报告配置
SUMMARY_REPORT_HOURS = [0, 4, 8, 12, 16, 20]
SUMMARY_TOP_N = 3
SUMMARY_WIN_THRESHOLD = 5.0

# 通知冷却（小时）
NOTIFY_COOLDOWN_HOURS = 24

# 倍数通知确认次数
MULTIPLIER_CONFIRMATIONS = 2

# 白名单配置（空配置表示不过滤）
CHAIN_ALLOWLISTS = {
    "sol": {},
    "bsc": {},
}

# 存储
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
STORAGE_DIR = DATA_DIR
CHATS_FILE = os.path.join(DATA_DIR, "telegram_chats.json")
CHAT_SETTINGS_FILE = os.path.join(DATA_DIR, "chat_settings.json")

# 运行
SILENT_INIT = True

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ENABLE_TELEGRAM = bool(TELEGRAM_BOT_TOKEN)

# Telegram 消息按钮配置
# 支持 {token_address} 占位符，会自动替换为合约地址
# chain: 指定链，只在该链的通知中显示，不填则所有链都显示
MESSAGE_BUTTONS = [
    {"text": "Pepe BSC", "url": "https://t.me/PepeboostBsc_bot?start=ref_0c9zso_ca_{token_address}", "chain": "bsc"},
    {"text": "Pepe SOL", "url": "https://t.me/pepeboost_sol06_bot?start=ref_0b22dk_ca_{token_address}", "chain": "sol"},
    {"text": "XXYY", "url": "https://pro.xxyy.io/sol/{token_address}?ref=ncuYXE", "chain": "sol"},
    {"text": "XXYY", "url": "https://pro.xxyy.io/bsc/{token_address}?ref=ncuYXE", "chain": "bsc"},
]
