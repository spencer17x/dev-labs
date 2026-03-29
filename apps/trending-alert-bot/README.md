# Trending Alert Bot

支持单链/多链配置的合约通知系统。每个 Bot 可服务一条或多条链，并独立维护自己的群组与通知数据。

## Core Design

- 单 Bot 单链/多链：一个进程可监控 `chain` 或 `chains`
- 配置驱动：仅使用 `configs/common.json` + `configs/bots/*.json`
- 数据隔离：每个 Bot 使用独立 `data_dir`
- 群组隔离：每个群组每条链独立 `contracts_data_{chain}_{chat_id}.json`

## Features

- 趋势通知：符合条件的当日合约（榜一）
- 异动通知：符合条件的非当日合约（榜一）
- 倍数通知：整数倍确认后推送
- 汇总报告：按群组独立统计
- 通知模式：每个群组可独立设置通知模式（趋势/异动/全部）
- Telegram 指令：`/start`、`/status`、`/mode`、`/setmode`、`/help`

## Install

```bash
uv python install
uv venv
uv pip install -r requirements.txt
```

## Config

### 1) Common config

`configs/common.json`

```json
{
  "check_interval": 15,
  "notify_cooldown_hours": 24,
  "multiplier_confirmations": 2
}
```

### 2) Bot config

`configs/bots/bsc.json`（示例）

```json
{
  "chain": "bsc",
  "telegram_bot_token": "REPLACE_WITH_BSC_BOT_TOKEN",
  "data_dir": "data/bsc-bot",
  "chain_allowlists": {
    "bsc": {}
  }
}
```

`configs/bots/multi.example.json`（多链示例）

```json
{
  "chains": ["bsc", "sol", "base"],
  "notification_types": ["trending", "anomaly"],
  "telegram_bot_token": "REPLACE_WITH_MULTI_BOT_TOKEN",
  "data_dir": "data/multi-bot",
  "chain_allowlists": {
    "bsc": {},
    "sol": {},
    "base": {}
  }
}
```

## Run

```bash
# 注意：`run` 必须带 target（如 bsc/sol/base/multi），不能直接 `uv run python run.py run`

# 本地前台运行（单配置）
uv run python run.py run bsc
uv run python run.py run multi

# PM2 启动（单配置）
uv run python run.py start bsc
uv run python run.py start sol
uv run python run.py start base
uv run python run.py start multi

# PM2 一键启动所有（单链 + 多链）
uv run python run.py start all
uv run python run.py all

# 单配置 Dry-run（run/start 均支持）
uv run python run.py run bsc --dry-run
uv run python run.py start bsc --dry-run

# 停止
uv run python run.py stop bsc
uv run python run.py stop multi
uv run python run.py stop all

# 重启
uv run python run.py restart bsc
uv run python run.py restart multi
uv run python run.py restart all

# 查看日志
uv run python run.py logs bsc
uv run python run.py logs multi
uv run python run.py logs all
```

## PM2

```bash
# 单实例（单链）
pm2 start run.py --name trending-alert-bot-bsc --interpreter ./.venv/bin/python -- run bsc

# 单实例（多链，使用 configs/bots/multi.json）
pm2 start run.py --name trending-alert-multi --interpreter ./.venv/bin/python -- run multi

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

`run.py` 和 `ecosystem.*.config.js` 默认优先使用当前目录 `.venv/bin/python`；如需覆盖，可设置 `PYTHON=/custom/python`。

## Validate Config

```bash
uv run python check_config.py --common-config configs/common.json --bot-config configs/bots/bsc.json
```

## Telegram

1. 用 BotFather 创建机器人，拿到 token
2. 写入 `configs/bots/{chain}.json` 的 `telegram_bot_token`
3. 多链模式请额外创建 `configs/bots/multi.json`（参考 `configs/bots/multi.example.json`）
4. 拉机器人进群并执行 `/start`

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

通知模式配置存储在 `data_dir/telegram_chats.json` 中每个群组的 `notification_mode` 字段。

## Project Structure

- `main.py`：CLI 入口
- `bot_app.py`：配置加载与运行时注入
- `monitor.py`：调度层（循环、定时、启动）
- `monitor_flow.py`：业务层（筛选、通知、汇总）
- `chat_storage.py`：群组状态存储
- `storage.py`：合约追踪存储

## Data Files

每个 Bot 的 `data_dir` 下会生成：

- `telegram_chats.json`
- `contracts_data_{chain}_{chat_id}.json`

要求：不同链 Bot 使用不同 `data_dir`，避免数据互相污染。

## License

MIT
