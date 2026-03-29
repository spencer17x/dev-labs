# Telegram 消息转发机器人

自动转发 Telegram 消息的 Python 机器人，支持灵活的规则配置和多种过滤方式。

## ✨ 核心特性

- 🎯 **智能分发** - 一个源群组可配置多条规则，将不同消息转发到不同目标
- 🔍 **强大过滤** - 支持关键词、正则表达式、用户、媒体类型等 6 种过滤器
- 📦 **清晰配置** - 群组维度组织规则，JSON 格式配置文件
- 🐛 **易于调试** - 可配置日志级别，详细的规则匹配信息

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone <repo-url> dev-lab
cd dev-lab/apps/telegram-forwarder

# 使用仓库根 .python-version 固定的 Python 版本
uv python install
uv venv

# 安装依赖
uv pip install -r requirements.txt
```

### 配置

1. **设置 Telegram API 凭据**

从 [https://my.telegram.org](https://my.telegram.org) 获取 API_ID 和 API_HASH，创建 `.env` 文件：

手动创建 `.env`（与 `main.py` 同级）并编辑：

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_PATH=telegram_forwarder_session  # 可选
LOG_LEVEL=INFO  # 可选: DEBUG, INFO, WARNING, ERROR, CRITICAL
# FORWARD_RULES_PATH=./forward_rules.json  # 可选：自定义规则文件路径
```

2. **配置转发规则**

```bash
cp forward_rules.example.json forward_rules.json
```

编辑 `forward_rules.json` 配置你的转发规则。

### 运行

**直接运行：**

```bash
uv run python main.py
```

**使用 PM2 运行（推荐生产环境）：**

```bash
# 安装 PM2（如未安装）
npm install -g pm2

# 启动服务
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 查看日志
pm2 logs telegram-forwarder

# 停止服务
pm2 stop telegram-forwarder

# 重启服务
pm2 restart telegram-forwarder

# 删除服务
pm2 delete telegram-forwarder

# 设置开机自启
pm2 startup
pm2 save
```

`ecosystem.config.js` 会默认优先使用当前目录 `.venv/bin/python`，也可以通过 `PYTHON=/custom/python pm2 start ecosystem.config.js` 覆盖解释器。

首次运行需要登录 Telegram 账号（输入手机号和验证码）。

## 📖 配置说明

### 配置结构

```json
{
  "session_name": "telegram_forwarder_session",
  "groups": [
    {
      "id": "unique_id",
      "name": "显示名称",
      "source": "@source_channel",
      "rules": [
        {
          "targets": ["@target1", "@target2"],
          "filters": {
            "mode": "all"
          }
        }
      ]
    }
  ]
}
```

### 必填字段

| 字段                   | 说明         | 示例                              |
| ---------------------- | ------------ | --------------------------------- |
| `id`                   | 群组唯一标识 | `"binance_news"`                  |
| `name`                 | 群组显示名称 | `"币安公告监控"`                  |
| `source`               | 源群组/频道  | `"@channel"` 或 `-1001234567890`  |
| `rules[].targets`      | 目标群组列表 | `["@target1", "@target2"]`        |
| `rules[].filters.mode` | 过滤模式     | `"all"`, `"include"`, `"exclude"` |

### 可选配置

- `session_name`：会话文件名或路径（等价于 `TELEGRAM_SESSION_PATH`）
- 环境变量 `FORWARD_RULES_PATH`：自定义配置文件路径（默认 `forward_rules.json`）

### 过滤模式

- **`all`** - 转发所有消息
- **`include`** - 白名单，只转发匹配的消息
- **`exclude`** - 黑名单，排除匹配的消息

### 过滤规则类型

支持 6 种过滤规则（可组合使用）：

1. **keyword** - 关键词匹配
2. **regex** - 正则表达式
3. **user** - 特定用户
4. **user_conditional** - 用户+条件
5. **media** - 媒体类型
6. **composite** - 组合规则（AND/OR）

📚 **详细文档**: [RULES.md](RULES.md) 包含所有规则类型的完整说明和示例。

## 💡 配置示例

### 全量转发

```json
{
  "id": "news_backup",
  "name": "新闻频道备份",
  "source": "@news_channel",
  "rules": [
    {
      "targets": ["@backup_channel"],
      "filters": { "mode": "all" }
    }
  ]
}
```

### 关键词过滤

```json
{
  "id": "btc_monitor",
  "name": "BTC 消息监控",
  "source": "@crypto_news",
  "rules": [
    {
      "targets": ["@btc_digest"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "keyword",
            "config": { "words": ["BTC", "Bitcoin", "比特币"] }
          }
        ]
      }
    }
  ]
}
```

### 一源多目标

```json
{
  "id": "signal_hub",
  "name": "交易信号中心",
  "source": "@all_signals",
  "rules": [
    {
      "targets": ["@btc_only"],
      "filters": {
        "mode": "include",
        "rules": [{ "type": "keyword", "config": { "words": ["BTC"] } }]
      }
    },
    {
      "targets": ["@eth_only"],
      "filters": {
        "mode": "include",
        "rules": [{ "type": "keyword", "config": { "words": ["ETH"] } }]
      }
    }
  ]
}
```

更多示例查看 [forward_rules.example.json](forward_rules.example.json) 和 [RULES.md](RULES.md)。

## 🔧 工具

### 获取群组 / 用户 ID

**方法 1：使用脚本**

```bash
uv run python cli/list_my_groups.py
```

可选择显示列表或导出 JSON（默认导出文件 `my_groups.json`）。

**查询用户 ID**

```bash
uv run python cli/query_user_id.py
```

**方法 2：使用 Bot**

转发群组消息到 [@userinfobot](https://t.me/userinfobot)，查看返回的 ID。

**ID 格式说明：**

- 公开群组/频道：`@username` 或 `-1001234567890`
- 私有群组：`-1001234567890`（必须使用数字 ID）

## 📊 日志输出

运行时会显示详细的转发信息：

```
📨 收到消息 [ID: 123] 来自 [News Channel] (ID: -1001234567890)
   发送者: John (@john) [ID: 987654321]
   内容: Bitcoin reaches new high...
   匹配到 2 条规则
   ✓ 规则 1 匹配 (模式: include) → 转发到 1 个目标
   ✗ 规则 2 不匹配 (模式: include)
   ✅ 消息已转发到 1 个目标
```

💡 设置 `LOG_LEVEL=DEBUG` 查看更详细的规则匹配过程。

## 🔔 启动通知

机器人启动后会向所有转发目标群组发送一条“已启动”通知消息；如需禁用该行为，可在 `core/bot.py` 中注释 `send_startup_notifications()` 调用。

## ❓ 常见问题

<details>
<summary><strong>如何获取 Telegram API 凭据？</strong></summary>

1. 访问 [https://my.telegram.org](https://my.telegram.org)
2. 登录后点击 "API development tools"
3. 填写应用信息（名称和简称）
4. 获取 API_ID 和 API_HASH
</details>

<details>
<summary><strong>支持私有群组吗？</strong></summary>

支持，但需要满足：

- 你的账号是该群组成员
- 使用数字 ID 格式（`-1001234567890`）
</details>

<details>
<summary><strong>如何暂停某个群组的转发？</strong></summary>

在配置中添加 `"enabled": false`：

```json
{
  "id": "paused_group",
  "name": "已暂停",
  "enabled": false,
  "source": "@source"
}
```

</details>

<details>
<summary><strong>规则不生效怎么办？</strong></summary>

1. 设置 `LOG_LEVEL=DEBUG` 查看详细匹配过程
2. 检查 source 和 targets 格式是否正确
3. 确认机器人账号在目标群组中
4. 查看 [RULES.md](RULES.md) 故障排查章节
</details>

<details>
<summary><strong>可以转发图片和视频吗？</strong></summary>

可以，支持所有类型的消息：文本、图片、视频、文档、音频等。

</details>

<details>
<summary><strong>如何运行多个机器人实例？</strong></summary>

设置不同的 `TELEGRAM_SESSION_PATH` 避免会话冲突：

```bash
# 实例 1
TELEGRAM_SESSION_PATH=session1 uv run python main.py

# 实例 2
TELEGRAM_SESSION_PATH=session2 uv run python main.py
```

</details>

## 📁 项目结构

```
telegram-forwarder/
├── main.py                      # 程序入口
├── forward_rules.json           # 转发规则配置
├── .env                         # 环境变量
├── requirements.txt             # 依赖列表
├── core/                        # 核心业务层
│   ├── __init__.py
│   ├── bot.py                  # Bot 主类
│   ├── event_handler.py        # 事件处理器
│   └── forwarder.py            # 转发逻辑
├── services/                    # 服务层
│   ├── __init__.py
│   ├── telegram_service.py     # Telegram API 交互
│   └── message_service.py      # 消息处理服务
├── config/                      # 配置层
│   ├── __init__.py
│   ├── loader.py               # 配置加载
│   └── validator.py            # 配置验证
├── filters/                     # 过滤器层
│   ├── __init__.py
│   └── message_filter.py       # 消息过滤逻辑
├── utils/                       # 工具层
│   ├── __init__.py
│   └── entity_helper.py        # 实体信息处理
└── cli/                         # 命令行工具
    ├── __init__.py
    ├── query_user_id.py        # 查询用户ID
    └── list_my_groups.py       # 群组列表/导出
```

## 📚 文档

- **[README.md](README.md)** - 快速开始（本文档）
- **[RULES.md](RULES.md)** - 完整规则配置文档
- **[forward_rules.example.json](forward_rules.example.json)** - 配置示例

## 🛠️ 技术栈

- Python 3.11（由仓库根 `.python-version` + `uv` 管理）
- [Telethon](https://docs.telethon.dev/) - Telegram MTProto API 客户端
- [python-dotenv](https://github.com/theskumar/python-dotenv) - 环境变量管理

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
