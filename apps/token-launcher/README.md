# Token Launcher

监听推特并自动在 BSC 上通过 four.meme 创建代币。

## 功能

- 🐦 监听指定推特用户的新推文
- 🤖 分析推文内容提取关键词（TODO: AI分析）
- 🚀 自动调用 four.meme API 创建代币
- 📢 Telegram 通知

## 安装

```bash
cd apps/token-launcher
pip install -r requirements.txt
```

## 配置

1. 复制配置文件：

```bash
cp config.example.json config.json
cp .env.example .env
```

2. 编辑 `.env` 填写敏感信息：

```bash
# Twitter Cookie
TWITTER_AUTH_TOKEN=your_auth_token
TWITTER_CT0=your_ct0

# Four.meme
FOUR_MEME_PRIVATE_KEY=your_wallet_private_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# OpenAI (可选)
OPENAI_API_KEY=your_openai_api_key
```

3. 编辑 `config.json` 配置非敏感项（监听用户等）：

```json
{
  "twitter": {
    "watch_users": ["elonmusk"],
    "poll_interval": 30
  },
  "four_meme": {
    "chain": "bsc"
  }
}
```

> 💡 敏感信息优先从 `.env` 读取，会自动覆盖 `config.json` 中的值

### 获取 Twitter Cookie

1. 登录 Twitter
2. 打开开发者工具 (F12)
3. 找到 Application > Cookies > twitter.com
4. 复制 `auth_token` 和 `ct0` 的值

## 运行

```bash
python main.py
```

或使用 PM2：

```bash
pm2 start ecosystem.config.js
```

## 项目结构

```
token-launcher/
├── main.py                 # 入口
├── config/                 # 配置
├── twitter/                # 推特监听
├── analyzer/               # AI分析 (TODO)
├── deployer/               # 代币部署
├── notifier/               # 通知
├── data/                   # 数据存储
└── logs/                   # 日志
```

## TODO

- [ ] 实现 four.meme API 调用
- [ ] 接入 AI 分析推文
- [ ] 支持更多链
- [ ] 添加 Web UI
