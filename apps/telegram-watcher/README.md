# 📡 Telegram Watcher

> Dev Lab Telegram 消息监听服务 · 双模式支持 · 高并发处理 · 智能消息分析

[![Python](https://img.shields.io/badge/Python-3.7+-3776ab?logo=python&logoColor=white)](https://python.org)
[![Telethon](https://img.shields.io/badge/Telethon-Latest-0088cc?logo=telegram&logoColor=white)](https://docs.telethon.dev)

## 🎯 项目概览

Dev Lab 中基于 Telethon 构建的 Telegram 消息监听服务，支持用户模式和机器人模式双重架构，提供完整的消息处理管道和智能分析能力。适用于消息监控、数据收集、业务集成等场景。

### ✨ 核心特性

- 🔄 **双模式支持** - 用户模式和机器人模式灵活切换
- 🎯 **精准监听** - 支持全局监听或指定聊天/用户消息
- 📊 **详细记录** - 完整消息信息记录 (发送者/时间/内容/媒体)
- ⚙️ **自定义处理** - 支持自定义消息处理逻辑和业务集成
- 📝 **完整日志** - 全面的日志记录和配置管理系统
- 🧠 **智能解析** - 自动聊天 ID 解析和配置验证
- 🚀 **高性能** - 基于异步架构，支持高并发消息处理

## 📁 项目结构

```
telegram-watcher/
├── .env.example             # 环境变量配置模板（API 凭证）
├── config.example.json      # 配置文件模板
├── config.json             # 实际配置文件（不提交到 git）
├── config_loader.py        # 配置加载器
├── main.py                 # 主服务程序
├── requirements.txt        # 依赖列表
├── session/                # 会话文件目录
└── logs/                   # 日志文件目录
```

## 🚀 快速开始

### 📋 环境要求

- Python ≥ 3.7.0
- Telegram API 凭证 (API ID + API Hash)
- Bot Token (可选，机器人模式)

### 🔑 获取 API 凭证

**步骤 1: 获取 API ID 和 API Hash** (必需)

```bash
1. 访问 https://my.telegram.org/
2. 登录 Telegram 账号
3. 点击 "API development tools"
4. 创建应用，获取 api_id 和 api_hash
```

**步骤 2: 获取 Bot Token** (机器人模式)

```bash
1. 在 Telegram 中找到 @BotFather
2. 发送 /newbot 创建新机器人
3. 按提示设置机器人名称和用户名
4. 获取 Bot Token
```

### 🚀 一键部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API 凭证
cp .env.example .env
# 编辑 .env，填入 TELEGRAM_API_ID 和 TELEGRAM_API_HASH

# 3. 配置监听目标
cp config.example.json config.json
# 编辑 config.json，配置监听目标和其他选项

# 4. 启动服务
python main.py
```

## ⚙️ 配置详解

### 📝 配置文件说明

项目采用**双层配置**：

- `.env` - 存储敏感的 API 凭证（不提交到版本控制）
- `config.json` - 存储业务配置（监听目标、日志、代理等）

### � 环境变量配置 (.env)

```env
# Telegram API 凭证（必需）
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 用户模式（可选，不设置则启动时询问）
TELEGRAM_PHONE_NUMBER=+1234567890

# 机器人模式（可选）
# TELEGRAM_BOT_TOKEN=your_bot_token

# 配置文件路径（可选，默认 config.json）
# WATCHER_CONFIG_PATH=config.json
```

### 📋 业务配置文件 (config.json)

```json
{
  "session_name": "session/telegram_watcher_session",
  "log": {
    "filename": "telegram_listener.log",
    "path": "logs",
    "level": "INFO"
  },
  "webhook": {
    "url": "http://localhost:3000/webhook",
    "timeout": 5
  },
  "proxy": {
    "url": "http://127.0.0.1:7890",
    "host": "",
    "port": "",
    "type": "http"
  },
  "targets": [
    {
      "id": "my_channel",
      "name": "我的频道",
      "type": "channel",
      "chat_id": "@mychannel",
      "enabled": true
    },
    {
      "id": "trading_group",
      "name": "交易群组",
      "type": "group",
      "chat_id": "-1001234567890",
      "enabled": true
    }
  ],
  "exclude": [
    {
      "chat_id": "@spam_group",
      "reason": "垃圾群组"
    }
  ]
}
```

### 🎭 运行模式选择

#### 👤 用户模式配置

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890  # 可选
```

- ✅ 监听所有有权限访问的消息
- ✅ 需要手机验证码登录
- ✅ 功能最全面

#### 🤖 机器人模式配置

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

- ✅ 无需验证码登录
- ⚠️ 只能接收发给机器人的消息
- ⚠️ 功能相对有限

### � 配置项说明

#### 会话配置

- `session_name` - 会话文件路径，支持相对路径或绝对路径

#### 日志配置

- `log.filename` - 日志文件名
- `log.path` - 日志目录路径
- `log.level` - 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）

#### Webhook 配置

- `webhook.url` - Webhook URL，留空则不推送
- `webhook.timeout` - 请求超时时间（秒）

#### 代理配置

- `proxy.url` - 代理 URL（推荐，如：`http://127.0.0.1:7890`）
- `proxy.host/port/type` - 分开配置代理（备选方案）

#### 监听目标配置

```json
{
  "id": "唯一标识符",
  "name": "显示名称",
  "type": "channel|group|user",
  "chat_id": "@username 或数字 ID",
  "enabled": true
}
```

#### 排除配置

```json
{
  "chat_id": "要排除的聊天 ID",
  "reason": "排除原因（可选）"
}
```

### 🎯 监听策略

| 配置             | 效果                 |
| ---------------- | -------------------- |
| 配置 `targets`   | 只监听指定聊天       |
| 不配置 `targets` | 监听所有可访问的消息 |
| 配置 `exclude`   | 排除指定聊天         |
| 两者结合         | 精准控制监听范围     |

````

## 部署与运行

### 💻 开发模式

```bash
# 直接启动服务
python main.py

# 首次运行（用户模式）会要求验证码登录
````

### 🌙 生产环境部署

#### 方式一：tmux 会话 (推荐)

```bash
# 安装 tmux
sudo apt install tmux  # Ubuntu/Debian
brew install tmux      # macOS

# 创建后台会话
tmux new -s telegram-watcher
cd /path/to/telegram-watcher
python main.py

# 分离会话（Ctrl+B, 然后按 D）
# 重新连接：tmux attach -t telegram-watcher
```

#### 方式二：systemd 服务 (Linux)

```bash
# 1. 创建服务文件
sudo nano /etc/systemd/system/telegram-watcher.service
```

```ini
[Unit]
Description=Telegram Watcher Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/telegram-watcher
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 2. 启用和启动服务
sudo systemctl enable telegram-watcher
sudo systemctl start telegram-watcher
sudo systemctl status telegram-watcher
```

#### 方式三：PM2 进程管理

```bash
# 安装 PM2
npm install -g pm2

# 启动应用
pm2 start main.py --name telegram-watcher --interpreter python3

# 管理命令
pm2 list                   # 查看进程
pm2 logs telegram-watcher  # 查看日志
pm2 restart telegram-watcher # 重启
pm2 save && pm2 startup    # 开机自启
```

## 🏗️ 技术架构

### 📊 消息数据结构

```python
{
    'message_id': 12345,           # 消息ID
    'date': '2024-01-01 12:00:00', # 消息时间
    'text': 'Hello World',         # 消息文本
    'sender_id': 123456789,        # 发送者ID
    'sender_name': 'John Doe',     # 发送者名称
    'chat_id': -1001234567890,     # 聊天ID
    'chat_title': 'My Group',      # 聊天标题
    'chat_type': 'group',          # 聊天类型
    'is_reply': False,             # 是否回复消息
    'media_type': 'text'           # 媒体类型
}
```

### 🔧 自定义处理逻辑

```python
# 在 main.py 的 process_message 方法中添加业务逻辑
async def process_message(self, message_info, event):
    # 关键词过滤
    if message_info['text'] and 'urgent' in message_info['text'].lower():
        await self.handle_urgent_message(message_info)

    # 群组消息处理
    if message_info['chat_type'] == 'group':
        await self.process_group_message(message_info)

    # 媒体消息处理
    if message_info['media_type'] != 'text':
        await self.handle_media_message(message_info, event)
```

## 🔍 故障排除

### 常见问题解决

| 问题类型         | 可能原因       | 解决方案                             |
| ---------------- | -------------- | ------------------------------------ |
| **API 限制错误** | 请求过于频繁   | 降低请求频率，等待限制解除           |
| **登录失败**     | API 凭据错误   | 检查 API_ID、API_HASH 和手机号       |
| **权限错误**     | 账号无访问权限 | 确保账号已加入相关群组/频道          |
| **聊天解析失败** | ID 格式错误    | 使用用户名(@username)或正确的聊天ID  |
| **无消息接收**   | 监听配置过严   | 检查 LISTEN_TARGETS 和 EXCLUDE_CHATS |
| **用户解析失败** | 用户名不存在   | 确认用户名正确且可访问               |

### 调试技巧

#### 启用详细日志

```env
LOG_LEVEL=DEBUG
```

#### 检查配置

```bash
# 检查网络连接
ping telegram.org

# 查看日志输出
tail -f logs/telegram_listener.log
```

## 📚 最佳实践

### 🏭 生产环境建议

1. **进程管理**
   - 使用 PM2 或 systemd 管理进程，配置自动重启
   - 设置内存限制防止内存泄漏
   - 配置系统服务实现开机自启

2. **安全配置**

   ```bash
   # 设置正确的文件权限
   chmod 600 .env
   chmod 700 sessions/

   # 添加到 .gitignore
   echo "sessions/" >> .gitignore
   echo "*.log" >> .gitignore
   echo ".env" >> .gitignore
   ```

3. **监控和维护**
   - 配置日志轮转避免磁盘空间不足
   - 定期备份 sessions 目录
   - 监控服务状态和资源使用
   - 设置告警机制

### 🔒 安全最佳实践

- **敏感信息保护**: 不要将 `.env` 文件提交到版本控制
- **会话文件安全**: 定期备份但不要公开分享 session 文件
- **访问权限控制**: 使用最小权限原则配置文件权限
- **网络安全**: 在生产环境中使用防火墙限制访问

### ⚡ 性能优化

- **内存管理**: 设置合理的内存限制和重启策略
- **日志优化**: 选择合适的日志级别，避免过度日志
- **连接管理**: 使用连接池和适当的超时设置
- **消息处理**: 对于大量消息的群组，考虑异步处理

## 🧪 开发

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式运行
python main.py
```

### 添加新功能

1. **扩展消息处理**: 在 `main.py` 中添加新的消息处理逻辑
2. **添加工具脚本**: 创建新的工具脚本用于特定功能
3. **集成外部服务**: 通过 Webhook 或 API 集成外部服务
4. **数据存储**: 添加数据库支持存储历史消息

## 📊 性能指标

- **内存使用**: ~50-150MB
- **CPU 使用**: ~2-8%
- **响应延迟**: 实时（WebSocket）
- **支持聊天**: 无限制
- **并发处理**: 支持多聊天并发监听

## ⚠️ 使用声明

- **合法合规**: 请遵守所在地区法律法规和 Telegram 服务条款
- **隐私保护**: 尊重用户隐私，不要记录或传播敏感信息
- **API 限制**: 遵守 Telegram API 的使用限制和频率控制
- **责任自负**: 使用本服务产生的任何后果由使用者承担

## 📄 许可证

本项目基于 [MIT 许可证](../../LICENSE) 开源。
