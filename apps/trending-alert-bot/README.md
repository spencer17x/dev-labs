# 趋势通知机器人

多链合约趋势监控与智能通知推送系统。

## 功能特性

- **多链监控**: 支持 Solana 和 BSC 双链趋势榜监控
- **趋势/异动通知**: 榜一合约首次上榜时推送详细信息，按合约创建时间区分趋势与异动
- **倍数通知**: 价格达到整数倍（2X、3X、4X...）时自动推送
- **汇总报告**: 每 4 小时推送当日数据统计和 TOP 合约（按群组独立统计）
- **Telegram 集成**: 支持多群组推送，消息引用回复，群组独立模式
- **白名单过滤**: 精准筛选目标平台和 DEX 的合约

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 Telegram（可选）
cp .env.example .env
# 编辑 .env 填入 TELEGRAM_BOT_TOKEN

# 启动
python main.py
```

## 配置

编辑 `config.py`:

```python
# 基础设置
CHECK_INTERVAL = 10  # 扫描间隔（秒）
CHAINS = ["bsc", "sol"]  # 监控的链

# 汇总报告配置
SUMMARY_REPORT_HOURS = [0, 4, 8, 12, 16, 20]  # 报告时间点（整点）
SUMMARY_TOP_N = 3  # 显示各链 TOP N 合约
SUMMARY_WIN_THRESHOLD = 5.0  # 胜率计算阈值（≥5X 为胜）

# 白名单配置（OR 逻辑：满足任一条件即通过）
CHAIN_ALLOWLISTS = {
    "sol": {"launchFrom": ['pump']},  # SOL: pump 平台
    "bsc": {
        "launchFrom": ['four'],  # BSC: four 平台
        "dexName": ['Binance Exclusive']  # 或 Binance Exclusive DEX
    },
}

# 静默初始化（启动时不主动推送已存在的榜一合约）
SILENT_INIT = True
```

## Telegram 设置

1. 找 [@BotFather](https://t.me/BotFather) 创建 Bot，获取 Token
2. 创建 `.env` 文件：
   ```bash
   cp .env.example .env
   ```
3. 编辑 `.env` 填入 `TELEGRAM_BOT_TOKEN=你的token`
4. 启动 Bot 后，在群组/频道发送 `/start` 订阅通知

### 群组模式命令（仅管理员）

- `/set_trend`：设置为趋势通知
- `/set_anomaly`：设置为异动通知
- `/set_both`：趋势 + 异动通知
- `/mode`：查看当前群组模式

## 运行

```bash
# 前台运行（测试）
python main.py

# 后台运行（生产）
nohup python main.py > bot.log 2>&1 &

# 或使用 PM2
pm2 start main.py --name trending-alert-bot --interpreter python3
pm2 logs trending-alert-bot
```

## 数据目录

运行时数据存放于 `apps/trending-alert-bot/data/`：

- `telegram_chats.json`：活跃聊天列表
- `chat_settings.json`：群组通知模式配置
- `contracts_data_{chain}_{chat_id}.json`：每个群组独立的合约跟踪数据

## 许可

MIT
