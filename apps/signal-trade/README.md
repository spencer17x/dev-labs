# Signal Trade

`apps/signal-trade` 现在是一个以浏览器直连 DexScreener 为主的数据看板：

- 框架：Next.js App Router
- 样式：Tailwind CSS
- 组件：本地 shadcn 风格 UI
- 数据流：浏览器直接请求 DexScreener latest feed 与 token detail

通知和筛选都只保留在当前浏览器页面会话，不写 `localStorage`，也不写服务端内存或文件。页面里的“同步通知”、`http` watcher、`ws` watcher、`auto` watcher 都直接在浏览器里完成 ingest 和补全。

## Architecture

```text
DexScreener latest feed HTTP / WebSocket
-> browser ingest
-> NotificationRecord[]
-> React session state
-> DexScreener /tokens/v1 detail backfill
```

核心目录：

- `app/`：Next.js 页面与仍保留的 API Route
- `components/`：dashboard 组件与本地 UI 组件
- `hooks/`：通知同步、watcher、diagnostics、行情补全
- `lib/`：类型、浏览器数据流、格式化工具
- `lib/ingest/`：Dex payload 解析、富化、通知构建、token detail hydration

## Setup

在仓库根执行一次：

```bash
pnpm install
```

## Commands

```bash
pnpm --filter signal-trade dev
pnpm --filter signal-trade build
pnpm --filter signal-trade start
pnpm --filter signal-trade type-check
```

## Workflow

1. 启动页面：

```bash
pnpm --filter signal-trade dev
```

2. 在页面里点击“同步通知”，浏览器会直接拉一轮 DexScreener latest feed 并在本地生成通知。

3. 如需常驻监听，在左侧选择 `监听模式`、勾选需要的 `WS 订阅`，然后点击“启动监听”。

4. 如需排查连通性，点击“诊断”；HTTP/WS 检查都在浏览器里直接完成，不再经过服务端 runtime API。

页面里的 `WS 订阅` 支持这 5 个 DexScreener feed：

- `token profiles`
- `community takeovers`
- `ads`
- `boosted tokens`
- `most active boosts`

## Web APIs

### DexScreener APIs

#### 1. Latest Feed HTTP APIs

这些接口由浏览器直接调用，主要用于页面“同步通知”和 `http` 监听模式。

- `https://api.dexscreener.com/token-profiles/latest/v1`
- `https://api.dexscreener.com/community-takeovers/latest/v1`
- `https://api.dexscreener.com/ads/latest/v1`
- `https://api.dexscreener.com/token-boosts/latest/v1`
- `https://api.dexscreener.com/token-boosts/top/v1`

入口：

- `lib/browser-refresh.ts`

#### 2. Latest Feed WebSocket APIs

这些接口由浏览器直接建立 WebSocket 连接，主要用于页面 `ws` 和 `auto` 监听模式。

- `wss://api.dexscreener.com/token-profiles/latest/v1`
- `wss://api.dexscreener.com/community-takeovers/latest/v1`
- `wss://api.dexscreener.com/ads/latest/v1`
- `wss://api.dexscreener.com/token-boosts/latest/v1`
- `wss://api.dexscreener.com/token-boosts/top/v1`

入口：

- `hooks/use-browser-watch.ts`
- `lib/watch-utils.ts`

#### 3. Token Detail HTTP API

- `https://api.dexscreener.com/tokens/v1/:chain/:addresses`
  - 用途：补 token detail 与展示所需行情字段
  - 主要字段：`name`、`symbol`、`fdv`、`marketCap`、`priceUsd`、`liquidityUsd`、`socials`、`websites`

入口：

- `lib/dexscreener-token-details.ts`
- `lib/browser-notification-details.ts`
- `hooks/use-market-data-enrichment.ts`

### Next.js APIs

#### Dashboard Filters API

- `GET /api/dashboard-filters`
- `PUT /api/dashboard-filters`

这组接口目前只负责 dashboard 默认筛选条件的读写规范化。

入口：

- `app/api/dashboard-filters/route.ts`
- `lib/signal-trade-data.ts`

## Browser Data Flow

```text
DexScreener latest feed HTTP / WebSocket
-> parseDexSubscriptionPayload
-> enrichSignalEvent
-> hydrateStoredSignalsWithTokenDetails
-> buildNotificationRecords
-> React session state
-> optional detail backfill batches
```

对应实现入口：

- `lib/ingest/ingest-dex-payload.ts`
- `lib/ingest/enrich-signal-event.ts`
- `lib/ingest/hydrate-signals-with-token-details.ts`
- `lib/ingest/build-notification-records.ts`

## Session Behavior

- 通知流
  - 只保存在当前页面 React state
  - 刷新页面后会清空
- 前端筛选
  - 只保存在当前页面状态
  - 刷新页面后恢复默认
  - 不写浏览器 `localStorage`
- Diagnostics
  - HTTP / WS 检查由浏览器直接执行
  - 不再依赖旧的服务端 runtime diagnostics route

## Notes

- 页面首次打开时通知列表为空，等待手动同步或页面内 `ws/http/auto` 监听写入当前会话
- 页面内 watcher 完全由浏览器驱动，不依赖服务端通知缓存
- 这个项目不再包含服务端 runtime CLI、Node watcher、或旧的 refresh API
