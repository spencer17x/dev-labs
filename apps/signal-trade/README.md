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

页面不会再轮询服务端通知缓存。“同步通知”按钮会先由浏览器直连 DexScreener 拉一轮最新 feed，再通过 `/api/runtime/ingest` 合并到当前页面会话。

页面里的 `WS 订阅` 支持这 5 个 DexScreener feed：

- `token profiles`
- `community takeovers`
- `ads`
- `boosted tokens`
- `most active boosts`

未选中的 feed 不会发起订阅；如果全部取消勾选，页面不会自动回退到默认 feed。

## Web APIs

### DexScreener APIs

#### 1. Latest Feed HTTP APIs

这些接口由浏览器直接调用，主要用于页面“同步通知”和 `http` 监听模式。浏览器先拉 DexScreener 最新 feed，再把原始 payload 转发给 Next.js 的 `/api/runtime/ingest` 统一解析。

- `https://api.dexscreener.com/token-profiles/latest/v1`
  - 用途：拉取最新 `token profiles` feed
- `https://api.dexscreener.com/community-takeovers/latest/v1`
  - 用途：拉取最新 `community takeovers` feed
- `https://api.dexscreener.com/ads/latest/v1`
  - 用途：拉取最新 `ads` feed
- `https://api.dexscreener.com/token-boosts/latest/v1`
  - 用途：拉取最新 `boosted tokens` feed
- `https://api.dexscreener.com/token-boosts/top/v1`
  - 用途：拉取最新 `most active boosts` feed

当前页面这条链路的入口在：

- `lib/browser-refresh.ts`

#### 2. Latest Feed WebSocket APIs

这些接口由浏览器直接建立 WebSocket 连接，主要用于页面默认的 `ws` 监听模式。收到消息后，页面不会自己解析原始 payload，而是把消息转发到 `/api/runtime/ingest`，统一走同一套通知生成逻辑。

- `wss://api.dexscreener.com/token-profiles/latest/v1`
  - 用途：实时接收 `token profiles` feed
- `wss://api.dexscreener.com/community-takeovers/latest/v1`
  - 用途：实时接收 `community takeovers` feed
- `wss://api.dexscreener.com/ads/latest/v1`
  - 用途：实时接收 `ads` feed
- `wss://api.dexscreener.com/token-boosts/latest/v1`
  - 用途：实时接收 `boosted tokens` feed
- `wss://api.dexscreener.com/token-boosts/top/v1`
  - 用途：实时接收 `most active boosts` feed

当前页面这条链路的入口在：

- `hooks/use-browser-watch.ts`
- `lib/watch-utils.ts`

#### 3. Token Detail HTTP API

- `https://api.dexscreener.com/tokens/v1/:chain/:addresses`
  - 用途：批量补 token detail
  - 主要字段：`name`、`symbol`、`fdv`、`marketCap`、`priceUsd`、`liquidityUsd`、`socials`、`websites`
  - 当前用途分两类：
    - 通知 detail 回填：通知先展示，detail 再按地址分批补回页面
    - 行情补全：给部分缺失 `priceUsd / marketCap` 的通知补展示用行情字段

当前页面这条链路的入口在：

- `lib/dexscreener-token-details.ts`
- `lib/browser-notification-details.ts`
- `hooks/use-market-data-enrichment.ts`

### Next.js APIs

#### 1. Runtime Ingest API

- `POST /api/runtime/ingest`
  - 用途：接收 DexScreener 原始 HTTP / WS payload，统一解析成页面通知
  - 输入：`payload` 或 `payloadText`，以及 `subscription`
  - 输出：`notifications`、`processed`、`stored`
  - 角色：这是 Web 端最核心的 BFF API，负责把原始 feed 变成 `NotificationRecord`

当前实现入口在：

- `app/api/runtime/ingest/route.ts`
- `lib/runtime/runtime-ingest.ts`
- `lib/runtime/refresh-feed.ts`

#### 2. Runtime Diagnostics API

- `POST /api/runtime/diagnostics`
  - 用途：给页面“诊断”按钮使用，检查服务端到 DexScreener 的 HTTP / WS 连通性、代理环境和通知 store 状态
  - 角色：辅助排查 API，不参与主通知链路

当前实现入口在：

- `app/api/runtime/diagnostics/route.ts`
- `lib/runtime/diagnostics.ts`

#### 3. Dashboard Filters API

- `GET /api/dashboard-filters`
  - 用途：读取 dashboard 筛选条件
- `PUT /api/dashboard-filters`
  - 用途：保存 dashboard 筛选条件

这组接口目前仍保留，但页面首屏初始化主要是服务端直接调用 `getDashboardFilters()`，不是浏览器启动后再主动请求。

当前实现入口在：

- `app/api/dashboard-filters/route.ts`
- `lib/signal-trade-data.ts`

#### 4. Legacy Refresh API

- `POST /api/notifications/refresh`
  - 用途：旧版服务端刷新接口，由 Next.js 服务端直接去 DexScreener 拉 feed 后返回通知
  - 当前状态：接口仍保留，但 Web 主链路已经改成“浏览器直连 DexScreener latest feed，再调用 `/api/runtime/ingest`”，所以页面现在基本不依赖它

当前实现入口在：

- `app/api/notifications/refresh/route.ts`

### Web Data Flow

页面当前的主链路可以概括为：

```text
DexScreener latest feed HTTP / WebSocket
-> /api/runtime/ingest
-> NotificationRecord[]
-> React session state
-> DexScreener /tokens/v1 detail backfill
```

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
