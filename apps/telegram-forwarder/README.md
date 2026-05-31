# Telegram 消息转发机器人

基于 Telethon 的 Telegram 用户客户端转发服务。它会监听配置里的源群组/频道，把符合规则的消息转发或复制到目标群组/频道。

## 核心能力

- 一源多目标：同一个源可以按不同规则分发到多个目标
- 简化配置：简单场景只需要 `from`、`to`、`keywords`
- 严格校验：坏规则、空关键词、坏正则会在启动前暴露
- 相册友好：组合媒体按相册事件处理，避免重复转发单条 grouped 消息
- 安全默认值：默认不打印消息正文，默认不发送启动通知
- 运维友好：支持 `--check-config`、PM2、绝对路径规则文件

## 安装

```bash
cd /Users/17a/projects/dev-labs/apps/telegram-forwarder
uv sync
```

如果服务器没有 `uv`，也可以用 Python 3.11+ 创建虚拟环境后安装依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## 环境变量

创建 `.env`：

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

TELEGRAM_SESSION_PATH=telegram_forwarder_session
FORWARD_RULES_PATH=./forward_rules.json
LOG_LEVEL=INFO

SEND_STARTUP_NOTIFICATION=false
STARTUP_NOTIFICATION_DETAILS=false
LOG_MESSAGE_CONTENT=false
SILENT_FORWARD=false
FORWARD_MODE=forward
FLOOD_WAIT_MAX_SECONDS=0
```

`TELEGRAM_API_ID` 和 `TELEGRAM_API_HASH` 来自 [my.telegram.org](https://my.telegram.org)。这是用户账号客户端，不是 Bot Token。首次启动会要求输入手机号和验证码，之后复用 session 文件。

服务器上建议使用绝对路径，避免项目目录移动或删除后 PM2 找不到数据：

```env
TELEGRAM_SESSION_PATH=/data/telegram-forwarder/session/telegram_forwarder_session
FORWARD_RULES_PATH=/data/telegram-forwarder/forward_rules.json
```

## 最小规则

`forward_rules.json` 最简单可以只写：

```json
{
  "forwards": [
    {
      "from": "@source_channel",
      "to": "@target_channel"
    }
  ]
}
```

这会全量转发 `@source_channel` 的消息到 `@target_channel`。

## 常用规则

关键词过滤：

```json
{
  "forwards": [
    {
      "from": "@crypto_news",
      "to": "@btc_digest",
      "keywords": ["BTC", "Bitcoin", "比特币"]
    }
  ]
}
```

多个目标：

```json
{
  "forwards": [
    {
      "from": "@source_channel",
      "to": ["@target_a", "@target_b"]
    }
  ]
}
```

只转发特定用户：

```json
{
  "forwards": [
    {
      "from": "@trading_group",
      "to": "@expert_signals",
      "users": ["@expert_1", 123456789]
    }
  ]
}
```

复杂规则仍支持原来的 `groups/rules/filters` 结构，详见 [RULES.md](RULES.md)。

## 校验和运行

先离线校验配置：

```bash
uv run python main.py --check-config --config forward_rules.json
```

启动服务：

```bash
uv run python main.py --config forward_rules.json
```

临时覆盖日志级别：

```bash
uv run python main.py --config forward_rules.json --log-level DEBUG
```

## PM2

```bash
pm2 start ecosystem.config.js
pm2 status
pm2 logs telegram-forwarder
pm2 restart telegram-forwarder
pm2 stop telegram-forwarder
```

`ecosystem.config.js` 默认使用当前目录 `.venv/bin/python`。如果 Python 在别处：

```bash
PYTHON=/custom/python pm2 start ecosystem.config.js
```

PM2 排查规则文件路径：

```bash
pm2 show telegram-forwarder
pm2 env <id> | grep FORWARD_RULES_PATH
pm2 logs telegram-forwarder --lines 200
```

长期运行建议安装 PM2 日志轮转：

```bash
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 14
```

## 获取群组和用户 ID

列出当前账号可见的频道/群组，并输出可直接写入配置的 ID：

```bash
uv run python cli/list_my_groups.py
```

查询用户 ID：

```bash
uv run python cli/query_user_id.py
```

公开频道/群组可用 `@username`。私有频道/超级群组通常使用 `-100...` 数字 ID。

## 运维开关

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FORWARD_RULES_PATH` | `forward_rules.json` | 规则文件路径 |
| `TELEGRAM_SESSION_PATH` | `telegram_forwarder_session` | Telethon session 路径 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_MESSAGE_CONTENT` | `false` | 是否打印消息正文 |
| `SEND_STARTUP_NOTIFICATION` | `false` | 启动时是否通知目标群 |
| `STARTUP_NOTIFICATION_DETAILS` | `false` | 启动通知是否包含监控明细 |
| `FORWARD_MODE` | `forward` | 默认投递模式：`forward` 或 `copy` |
| `SILENT_FORWARD` | `false` | 默认是否静默发送 |
| `FLOOD_WAIT_MAX_SECONDS` | `0` | FloodWait 不超过该秒数时等待并重试 |

## 安全提示

- 不要提交真实 `.env`、`forward_rules.json`、session 文件
- session 文件相当于账号登录凭证，应放在权限受控目录
- 规则文件可能暴露私有群 ID、用户名和监控策略
- 默认不打印消息正文；如需排查再临时设置 `LOG_MESSAGE_CONTENT=true`

## 项目结构

```text
telegram-forwarder/
├── main.py
├── forward_rules.example.json
├── config/
├── core/
├── filters/
├── services/
├── utils/
├── cli/
└── tests/
```

## 技术栈

- Python 3.11+
- Telethon
- python-dotenv
- PM2 可选
