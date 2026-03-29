# Signal Trade

`apps/signal-trade` 现在是一个前后端并存的全栈项目：

- 前端 / BFF：Next.js App Router
- 样式：Tailwind CSS
- 组件：shadcn 风格本地组件
- 采集 / 规则引擎：现有 Python 采集器与策略匹配逻辑

前端负责展示通知代币、保存筛选条件、汇总当前策略；Python 继续负责 DexScreener / X / XXYY 的采集、富化和命中通知。

## Architecture

```text
Python collectors -> StrategyEngine -> NotificationStore -> data/notifications.json
                                                      \
                                                       -> stdout / webhook

Next.js dashboard -> app/api/* -> data/notifications.json / data/dashboard-filters.json / rules.json
```

核心目录：

- `app/`：Next.js 页面与 API Route
- `components/`：dashboard 组件与 shadcn 风格 UI 组件
- `lib/`：本地数据读写、类型、demo 数据
- `core/`、`collectors/`、`services/`：原有 Python 运行时
- `data/`：前端筛选条件和通知持久化目录

## Features

- 通知代币面板：展示命中的代币、策略、链、来源、市值、持币人数、社区人数
- 前端条件筛选：链路、来源、策略、持币人数、市值、社区人数、观察名单关键词、paid only
- 本地条件持久化：前端保存到 `data/dashboard-filters.json`
- 策略摘要：从 `rules.json` 读取当前启用策略的关键条件
- 后端通知落盘：Python 每次命中通知后写入 `data/notifications.json`

## Frontend Setup

在仓库根执行一次：

```bash
pnpm install
```

启动前端开发服务：

```bash
pnpm --filter signal-trade dev
```

常用命令：

```bash
pnpm --filter signal-trade build
pnpm --filter signal-trade start
pnpm --filter signal-trade type-check
```

## Backend Setup

以下命令默认在 `apps/signal-trade` 目录下执行：

```bash
uv python install
uv venv
uv pip install -r requirements.txt
cp .env.example .env
cp config.example.json config.json
```

查看 CLI：

```bash
uv run python main.py --help
```

常用后端命令：

```bash
uv run python main.py --rules rules.json dex-rest --subscriptions token_profiles_latest --limit 10
uv run python main.py --rules rules.json dex-ws --subscriptions token_profiles_latest --limit 10
uv run python main.py twitter elonmusk
```

也可以通过 workspace script 触发：

```bash
pnpm --filter signal-trade backend:help
pnpm --filter signal-trade backend:dex-rest
pnpm --filter signal-trade backend:twitter
```

## Full-Stack Workflow

1. 启动前端：

```bash
pnpm --filter signal-trade dev
```

2. 启动任一 Python 信号源，把通知写入本地存储：

```bash
cd apps/signal-trade
uv run python main.py --rules rules.json dex-rest --subscriptions token_profiles_latest --limit 10
```

3. 打开前端页面，查看通知代币与策略摘要。

当前页面每 30 秒轮询一次 `/api/notifications`。

## Data Files

- `data/notifications.json`
  - Python 后端写入
  - 前端用来展示通知代币
- `data/dashboard-filters.json`
  - 前端写入
  - 保存筛选条件
- `rules.json`
  - Python 策略引擎读取
  - 前端只读展示摘要

这两个 `data/*.json` 已加入 git ignore，不会提交。

## Frontend Filters

当前前端支持这些可保存条件：

- `search`：搜索代币 symbol / name / address / Twitter 用户名 / 消息文本
- `watchTerms`：逗号或换行分隔的观察名单关键词
- `chain`
- `source`
- `strategyId`
- `minHolders`
- `maxMarketCap`
- `minCommunityCount`
- `paidOnly`

这些条件只作用在前端展示层，不会直接改写 Python 侧策略规则。

## Strategy Rules

规则文件仍然使用现有格式，示例见：

- [rules.json](./rules.json)
- [rules.example.json](./rules.example.json)

前端会读取并汇总这些字段：

- `id`
- `enabled`
- `chains`
- `source`
- `notify` / `action.channels`
- `xxyy.holder_count >=`
- `xxyy.holder_count >`
- `xxyy.market_cap >`
- `xxyy.kol_names contains_any`
- `xxyy.follow_addresses contains_any`

## Notes

- 如果 `data/notifications.json` 不存在，前端会显示内置 demo 数据
- Python 命中通知后会自动创建 `data/notifications.json`
- 现在 `signal-trade` 是“Next.js 仪表盘 + Python runtime” 双栈结构，不再是单纯的 Python CLI 项目
