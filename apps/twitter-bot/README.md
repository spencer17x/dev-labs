# 🐦 Twitter Bot

> Dev Lab Twitter 监控转发系统 · 实时推文追踪 · 零依赖部署 · 智能过滤

[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178c6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![rolldown](https://img.shields.io/badge/rolldown-1.0.0--beta-ff6b35?logo=rollup&logoColor=white)](https://rolldown.rs/)
[![Twitter](https://img.shields.io/badge/Twitter-API-1da1f2?logo=twitter&logoColor=white)](https://developer.twitter.com/)

## 🎯 项目概览

Dev Lab 中的 Twitter 推文监控和转发工具，实时监控指定 Twitter 用户推文并自动转发到 Telegram 群组或频道。基于 rolldown 构建系统，实现 **2.4MB** 零依赖单文件部署，构建速度提升 **40 倍**。

### ✨ 核心特性

- 📦 **零依赖部署** - 单文件包含所有依赖，仅 2.4MB
- 🔄 **实时监控** - Twitter 用户推文实时追踪转发
- 🎯 **多群组转发** - 支持同时转发到多个 Telegram 群组
- 🚄 **超快构建** - 开发构建从秒级提升到毫秒级
- 🔥 **热重载开发** - 毫秒级代码变更反馈
- 🛡️ **智能过滤** - 支持关键词过滤、去重、频率控制
- 🔧 **配置灵活** - 环境变量配置，支持多账号管理

## 📁 项目结构

```
twitter-bot/
├── .env.example              # 环境变量配置模板
├── config.example.env        # 配置示例文件
├── db.example.json          # 数据库示例文件
├── package.json             # 项目配置和脚本
├── rolldown.config.ts       # rolldown 打包配置
├── tsconfig.json           # TypeScript 配置
├── dist/                   # 构建输出目录
│   └── index.cjs          # 打包后的单文件（约 2.4MB）
├── logs/                   # 日志文件目录
│   ├── error.log          # 错误日志
│   └── out.log            # 输出日志
└── src/
    ├── index.ts            # 程序入口
    ├── config/
    │   └── index.ts        # 配置管理
    └── utils/
        ├── bot.ts          # Telegram 机器人逻辑
        ├── twitter.ts      # Twitter API 封装
        ├── db.ts           # 数据库工具
        ├── api.ts          # Twitter API 配置
        └── test-send-message.ts # 消息测试工具
```

## 🚀 快速开始

### 📋 环境要求

- **开发环境**: Node.js ≥ 16.17.0, pnpm
- **生产环境**: 仅需 Node.js ≥ 16.17.0（无需安装依赖）

### 1. 安装依赖

```bash
pnpm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# Twitter 认证配置
ct0=your_ct0_value
auth_token=your_auth_token_value
interval=30

# Telegram Bot 配置
tg_bot_token=your_telegram_bot_token
```

### 3. 获取 Twitter 认证信息

1. 登录 [Twitter](https://twitter.com)
2. 打开浏览器开发者工具 (F12)
3. 在 Application → Cookies 中找到 `ct0` 和 `auth_token` 值

### 4. 创建 Telegram Bot

1. 在 Telegram 中联系 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新机器人
3. 获取 Bot Token

### 5. 初始化数据库

```bash
cp db.example.json db.json
```

### 6. 运行服务

```bash
# 开发模式
pnpm dev

# 构建项目
pnpm build

# 生产模式
pnpm start:prod
```

## 📝 可用脚本

| 脚本              | 说明                           |
| ----------------- | ------------------------------ |
| `pnpm dev`        | 开发模式运行（使用 vite-node） |
| `pnpm build`      | 构建生产版本（零依赖单文件）   |
| `pnpm start:prod` | 运行构建后的文件               |
| `pnpm clean`      | 清理构建文件                   |
| `pnpm test:send`  | 测试 Telegram 消息发送功能     |

## 🎮 机器人命令

### 基础命令

- `/start` - 启动机器人并显示欢迎信息
- `/help` - 显示所有可用命令的帮助信息

### 用户管理

- `/sub <username>` - 订阅 Twitter 用户

  ```
  /sub elonmusk
  ```

- `/unsub <username>` - 取消订阅 Twitter 用户

  ```
  /unsub elonmusk
  ```

- `/users` - 查看当前订阅的所有用户列表
- `/groups` - 查看机器人当前所在的群组列表

### 管理员命令

- `/admin <username>` - 添加管理员

  ```
  /admin new_admin
  ```

- `/admins` - 查看所有管理员列表

> **注意**: 除了基础命令外，其他命令需要管理员权限。第一个添加机器人到群组的用户自动成为管理员。

## 🔧 群组管理

### 自动群组管理

机器人会**自动管理群组列表**，无需手动配置：

- **添加群组**: 直接将机器人添加到目标群组，机器人会自动记录
- **移除群组**: 将机器人从群组中移除，会自动从列表删除
- **推文转发**: 推文会自动转发到**所有**机器人所在的群组

### 数据结构

`db.json` 文件结构：

```json
{
  "groups": [
    {
      "id": -1001234567890,
      "title": "群组名称",
      "type": "supergroup",
      "fromId": 123456789,
      "fromUsername": "添加者用户名"
    }
  ],
  "subUsers": ["elonmusk", "jack"],
  "admins": ["admin_username"]
}
```

## 📊 推文格式

转发到 Telegram 的推文格式示例：

```
*Elon Musk* 发推了
内容: Hello Twitter!
当前时间: 2024-01-01 12:00:00
北京时间: 2024-01-01 12:00:00
世界时间: 2024-01-01 04:00:00
链接: 查看原文
```

## 🚀 部署

### 零依赖部署（推荐）

```bash
# 1. 本地构建
pnpm build

# 2. 查看构建结果
ls -lh dist/index.cjs  # ~2.4MB

# 3. 复制到服务器
scp dist/index.cjs .env db.json user@server:/app/

# 4. 服务器上直接运行
node index.cjs
```

### 使用 PM2 管理

```bash
# 启动服务
pm2 start dist/index.cjs --name twitter-bot

# 查看状态
pm2 status twitter-bot

# 查看日志
pm2 logs twitter-bot
```

### 使用 systemd 管理

创建服务文件 `/etc/systemd/system/twitter-bot.service`：

```ini
[Unit]
Description=Twitter to Telegram Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/twitter-bot
ExecStart=/usr/bin/node index.cjs
Restart=on-failure
RestartSec=10
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

## 🔧 技术架构

### 构建系统

- **rolldown**: 基于 Rust 的高性能打包工具
- **vite-node**: 开发时 TypeScript 直接执行
- **零依赖打包**: 所有 npm 依赖都被打包到单个文件

### 核心技术栈

| 技术                       | 用途               | 版本     |
| -------------------------- | ------------------ | -------- |
| twitter-openapi-typescript | Twitter API 客户端 | ^0.0.38  |
| Telegraf                   | Telegram Bot 框架  | ^4.16.3  |
| dayjs                      | 时间处理           | ^1.11.11 |
| axios                      | HTTP 请求          | ^1.7.2   |

## 🔍 故障排除

### Twitter 认证失败

```
Error: 401 Unauthorized
```

**解决方案：**

1. 重新登录 Twitter 获取最新的认证信息
2. 确认 `ct0` 和 `auth_token` 值正确
3. 检查网络连接和防火墙设置

### Telegram Bot 无响应

```
Error: 400 Bad Request: chat not found
```

**解决方案：**

1. 验证 Bot Token 格式正确
2. 确认机器人已添加到群组并有发送消息权限
3. 尝试发送 `/start` 命令激活机器人

### 推文未转发

**解决方案：**

1. 确认订阅的用户名拼写正确（不含 @）
2. 检查该用户是否发布了新推文
3. 查看日志确认 API 调用状态
4. 适当增加检查间隔避免频率限制

## 🧪 开发

### 本地开发

```bash
# 安装依赖
pnpm install

# 开发模式（热重载）
pnpm dev

# 测试消息发送
pnpm test:send
```

### 核心类说明

#### TwitterUtil

```typescript
const twitterUtil = await TwitterUtil.create({
  ct0: 'your_ct0',
  authToken: 'your_auth_token',
  interval: 30,
});

// 关注用户
await twitterUtil.followUser('username');

// 检查更新
twitterUtil.checkUpdate({
  onUpdate: tweetData => {
    // 处理新推文
  },
});
```

#### DBUtil

```typescript
const dbUtil = new DBUtil();

// 用户管理
dbUtil.addUser('username');
dbUtil.removeUser('username');
dbUtil.getUsers();

// 管理员管理
dbUtil.addAdmin('admin_username');
dbUtil.getAdmins();
```

## 📊 性能指标

- **内存使用**: ~50-100MB
- **CPU 使用**: ~1-5%
- **包大小**: 2.4MB（零依赖）
- **启动时间**: ~3-5 秒
- **响应延迟**: 3-10 秒

## ⚠️ 重要提醒

- **安全性**: `ct0` 和 `auth_token` 具有完整账号权限，请妥善保管
- **频率限制**: 建议检查间隔设置为 30-60 秒
- **服务条款**: 请遵守 Twitter 和 Telegram 的使用条款
- **免责声明**: 仅供学习和个人使用

## 📄 许可证

本项目基于 [MIT 许可证](../../LICENSE) 开源。
