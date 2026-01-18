import os
from dotenv import load_dotenv

load_dotenv()

# 基础设置
CHECK_INTERVAL = 10
CHAINS = ["bsc", "sol"]

# 汇总报告配置
SUMMARY_REPORT_HOURS = [0, 4, 8, 12, 16, 20]
SUMMARY_TOP_N = 3
SUMMARY_WIN_THRESHOLD = 5.0

# 白名单配置（空配置表示不过滤）
CHAIN_ALLOWLISTS = {
    "sol": {},
    "bsc": {"launchFrom": ["four", "flap"], "dexName": ["Binance Exclusive"]},
}

# 存储
STORAGE_DIR = os.path.dirname(__file__)
CHATS_FILE = os.path.join(STORAGE_DIR, "telegram_chats.json")

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
