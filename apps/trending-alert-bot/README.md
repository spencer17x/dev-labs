# Trending Alert Bot

支持单链/多链配置的合约通知系统。每个 Bot 可服务一条或多条链，并独立维护自己的群组与通知数据。

## Core Design

- 单 Bot 单链/多链：一个进程可监控 `chain` 或 `chains`
- 配置简化：固定 target 写在代码中，Telegram token 只放 `.env`
- 数据隔离：每个 Bot 使用独立 `data_dir`
- 群组隔离：SQLite 中按 `chain + chat_id + token_address` 隔离合约追踪数据

## Features

- 趋势通知：符合条件的当日合约（榜一）
- 异动通知：符合条件的非当日合约（榜一）
- 倍数通知：整数倍确认后推送
- 汇总报告：按群组独立统计
- 通知模式：每个群组可独立设置通知模式（趋势/异动/全部）
- Telegram 指令：`/start`、`/status`、`/mode`、`/setmode`、`/help`

## Install

```bash
cd apps/trending-alert-bot
uv python install
uv sync --locked
```

依赖由 `pyproject.toml` 声明，并通过 `uv.lock` 锁定版本；`uv sync` 会创建/更新当前 app 的 `.venv`。

## Config

项目不再使用 `configs/`。支持的 target、链、数据目录和默认参数固定在 `bot_app.py`：

| target | chains | data_dir |
|--------|--------|----------|
| `bsc` | `bsc` | `data/bsc-bot` |
| `sol` | `sol` | `data/sol-bot` |
| `base` | `base` | `data/base-bot` |
| `eth` | `eth` | `data/eth-bot` |
| `multi` | `bsc, sol, base, eth` | `data/multi-bot` |

默认参数：

| 参数 | 值 |
|------|----|
| `check_interval` | `15` 秒 |
| `notify_cooldown_hours` | `24` 小时 |
| `multiplier_confirmations` | `2` |
| `notification_types` | `trending, anomaly` |

复制 `.env.example` 为 `.env`，只填写 Telegram token：

```bash
cp .env.example .env
```

```env
BSC_TELEGRAM_BOT_TOKEN=
SOL_TELEGRAM_BOT_TOKEN=
BASE_TELEGRAM_BOT_TOKEN=
ETH_TELEGRAM_BOT_TOKEN=
MULTI_TELEGRAM_BOT_TOKEN=
```

## Run

```bash
# 本地前台运行
uv run python main.py bsc
uv run python main.py multi

# 单次 Dry-run，不发送 Telegram 消息
uv run python main.py bsc --dry-run
```

## PM2

```bash
# 多实例（单链 bots）
pm2 start ecosystem.bots.config.js

# 多链单实例
pm2 start ecosystem.multi.config.js

# 全量（一键：单链 + 多链）
pm2 start ecosystem.all.config.js

# 首次配置开机自启（仅需一次）
pm2 startup

# 启动后持久化当前进程列表（每次变更后建议执行）
pm2 save
```

`ecosystem.*.config.js` 默认优先使用当前目录 `.venv/bin/python`；如需覆盖，可设置 `PYTHON=/custom/python`。

## Validate Env

```bash
uv run python check_config.py bsc
```

## Telegram

1. 用 BotFather 创建机器人，拿到 token
2. 写入 `.env` 中对应的 `{TARGET}_TELEGRAM_BOT_TOKEN`
3. 拉机器人进群并执行 `/start`

### 通知模式

每个群组可独立设置通知模式，默认接收全部通知：

| 模式 | 说明 |
|------|------|
| `all` | 接收趋势 + 异动通知（默认） |
| `trending` | 仅接收趋势通知 |
| `anomaly` | 仅接收异动通知 |

**Bot 命令：**

| 命令 | 权限 | 说明 |
|------|------|------|
| `/mode` | 所有人 | 查看当前通知模式 |
| `/setmode <mode>` | 管理员 | 切换通知模式（all / trending / anomaly） |
| `/start` | 所有人 | 订阅并初始化 |
| `/status` | 所有人 | 查看运行状态及通知模式 |
| `/help` | 所有人 | 查看命令说明 |

通知模式配置存储在 `data_dir/trending_alert_bot.sqlite` 的 `telegram_chats` 表中。

## Project Structure

- `main.py`：CLI 入口
- `bot_app.py`：固定 target 元数据、`.env` 加载与运行时注入
- `monitor.py`：调度层（循环、定时、启动）
- `monitor_flow.py`：业务层（筛选、通知、汇总）
- `db_storage.py`：SQLite 连接与 schema 初始化
- `chat_storage.py`：群组状态存储
- `storage.py`：合约追踪存储

## Data Files

每个 Bot 的 `data_dir` 下会生成：

- `trending_alert_bot.sqlite`

SQLite 中包含：

| 表 | 用途 | 隔离方式 |
|----|------|----------|
| `telegram_chats` | 群组订阅状态、通知模式、消息计数 | `chat_id` |
| `contracts` | 合约初始价格、名称、符号、最后通知时间 | `chain + chat_id + token_address` |
| `contract_message_ids` | 合约首次通知的 Telegram 消息 ID | `chain + chat_id + token_address + telegram_chat_id` |
| `contract_notified_multipliers` | 已通知过的倍数 | `chain + chat_id + token_address + multiplier` |
| `contract_pending_multipliers` | 等待确认的整数倍状态 | `chain + chat_id + token_address` |
| `runtime_state` | 汇总报告 marker 等运行状态 | `key` |

### Clear storage

`--clear-storage` 会清理 SQLite 中指定链、指定群组的合约追踪记录，并通过外键级联清理对应消息 ID、倍数通知和 pending 倍数状态。群组订阅状态保留在 `telegram_chats` 中。

### Inspect data

```bash
sqlite3 data/bsc-bot/trending_alert_bot.sqlite ".tables"
sqlite3 data/bsc-bot/trending_alert_bot.sqlite "select chat_id,title,notification_mode,active from telegram_chats;"
```

要求：不同链 Bot 使用不同 `data_dir`，避免数据互相污染。

## License

MIT
