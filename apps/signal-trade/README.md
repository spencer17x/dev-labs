# Signal Trade

`apps/signal-trade` 现在是纯 `Next.js + TypeScript` 的全栈项目：

- 页面 / BFF：Next.js App Router
- 样式：Tailwind CSS
- 组件：本地 shadcn 风格 UI
- 运行时：TypeScript collectors 与富化逻辑

前端页面负责展示通知流、筛选通知，并直接在页面里切换 watcher 的 `http / ws / auto` 模式。通知和筛选都只保留在当前浏览器页面会话，不写 `localStorage`，也不写 Node 端内存或文件。服务端 API 只负责向 DexScreener 拉取批次数据、解析 WS payload，并把 DexScreener 自带字段整理后返回给页面。`runtime:refresh` 走 REST 单次刷新，`runtime:watch` 仍然支持 `http`、`ws`、`auto` 三种模式，但 CLI 只输出处理日志，不再为页面持久化任何通知数据。

## Architecture

```text
DexScreener REST / WebSocket -> normalize + notification formatting -> stateless API response

Next.js dashboard -> in-page React state
```

核心目录：

- `app/`：Next.js 页面与 API Route
- `components/`：dashboard 组件与本地 UI 组件
- `lib/`：类型与前端默认数据
- `lib/runtime/`：采集、富化与通知格式化
- `scripts/`：runtime CLI 入口

## Setup

在仓库根执行一次：

```bash
pnpm install
```

在 `apps/signal-trade` 目录初始化本地配置：

```bash
cd apps/signal-trade
cp .env.example .env
cp config.example.json config.json
```

`config.json` 现在只保留这些运行时参数：

- `dexscreener.pollIntervalSec`
- `dexscreener.requestTimeoutSec`
- `dexscreener.wsHeartbeatSec`
- `dexscreener.reconnectDelaySec`
- `twitter.requestTimeoutSec`

## Commands

前端开发：

```bash
pnpm --filter signal-trade dev
pnpm --filter signal-trade build
pnpm --filter signal-trade start
pnpm --filter signal-trade type-check
```

运行时刷新：

```bash
pnpm --filter signal-trade runtime:refresh -- --limit 10 --subscriptions token_profiles_latest community_takeovers_latest
# HTTP polling
pnpm --filter signal-trade runtime:watch -- --transport http --interval-sec 15 --limit 10 --subscriptions token_profiles_latest ads_latest
# pure WebSocket
pnpm --filter signal-trade runtime:watch -- --transport ws --limit 10 --subscriptions token_profiles_latest token_boosts_latest
# WebSocket with REST fallback
pnpm --filter signal-trade runtime:watch -- --transport auto --interval-sec 15 --limit 10 --subscriptions token_profiles_latest token_boosts_top
```

## Workflow

1. 启动页面：

```bash
pnpm --filter signal-trade dev
```

2. 通过页面点击“同步通知”，或者直接运行：

```bash
pnpm --filter signal-trade runtime:refresh -- --limit 10
```

3. 打开页面查看当前会话通知流，并通过页面筛选条件过滤结果。

4. 如需常驻监听，可以直接在页面左侧选择 `监听模式`、勾选需要的 `WS 订阅`，再点击“启动监听”。

如果需要单独看 CLI 日志，也可以另开一个终端运行：

```bash
pnpm --filter signal-trade runtime:watch -- --transport auto --subscriptions token_profiles_latest community_takeovers_latest ads_latest
```

`runtime:watch` 与页面内 watcher 的模式说明：

- `http`：仅按 `--interval-sec` 做 REST 轮询
- `ws`：页面里走浏览器直连 DexScreener WebSocket，CLI 仍然是服务端直连，不做 REST 兜底
- `auto`：页面里优先使用浏览器 WebSocket，异常时退回浏览器端 HTTP 刷新；CLI 则是服务端 WS + REST fallback

页面不会再轮询服务端通知缓存。“同步通知”按钮会直接触发 `/api/notifications/refresh` 拉取一轮新数据，并合并到当前页面会话。

页面里的 `WS 订阅` 支持这 5 个 DexScreener feed：

- `token profiles`
- `community takeovers`
- `ads`
- `boosted tokens`
- `most active boosts`

未选中的 feed 不会发起订阅；如果全部取消勾选，页面不会自动回退到默认 feed。

## Session Behavior

- 通知流
  - 只保存在当前页面的 React state
  - 刷新页面后会清空
  - Node 端不会缓存、不会落文件
- 前端筛选
  - 只保存在当前页面状态
  - 刷新页面后恢复默认
  - 不写浏览器 `localStorage`

## Frontend Filters

当前前端支持这些会话内条件：

- `search`：搜索代币 symbol / name / address / Twitter 用户名 / 消息文本
- `watchTerms`：逗号或换行分隔的观察名单关键词
- `watchTransport`
- `watchSubscriptions`
- `chain`
- `source`
- `minHolders`
- `maxHolders`
- `maxMarketCap`
- `minCommunityCount`
- `kolNames`
- `followAddresses`
- `paidOnly`

这些条件只作用在展示层，不会改写原始通知数据。

## Notes

- 页面首次打开时通知列表为空，等待手动同步或页面内 `ws/http` 监听写入当前会话
- 当前 runtime 同时支持 DexScreener REST 单次刷新和 WebSocket 实时监听，页面直接展示 DexScreener feed 返回的字段
- 页面内 watcher 完全由浏览器驱动，不依赖服务端通知缓存
- 当前 Node 端不再写 `notifications.json`、`dashboard-filters.json`，也不保留进程内通知缓存
- 这个项目不再需要 `uv`、`requirements.txt` 或 Python 入口脚本
