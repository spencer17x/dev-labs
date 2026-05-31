# 转发规则配置

`forward_rules.json` 支持两种写法：

- `forwards`：简单写法，适合大多数转发场景
- `groups`：完整写法，适合复杂组合规则

启动前建议运行：

```bash
uv run python main.py --check-config --config forward_rules.json
```

## 简单写法

全量转发：

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

媒体过滤：

```json
{
  "forwards": [
    {
      "from": "@art_channel",
      "to": "@gallery",
      "media": ["photo", "video"]
    }
  ]
}
```

正则过滤：

```json
{
  "forwards": [
    {
      "from": "@signals",
      "to": "@address_alerts",
      "regex": "0x[a-fA-F0-9]{40}",
      "regex_description": "以太坊地址"
    }
  ]
}
```

## 完整写法

完整结构：

```json
{
  "groups": [
    {
      "id": "unique_group_id",
      "name": "显示名称",
      "enabled": true,
      "source": "@source_channel",
      "rules": [
        {
          "enabled": true,
          "targets": ["@target_channel"],
          "forward_mode": "forward",
          "silent": false,
          "dedupe": true,
          "filters": {
            "mode": "all"
          }
        }
      ]
    }
  ]
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 群组唯一标识，用于日志 |
| `name` | 是 | 显示名称 |
| `enabled` | 否 | 默认 `true`；禁用时可省略 `source` 和 `rules` |
| `source` | 启用时必填 | 源群组/频道，支持 `@username` 或数字 ID |
| `rules` | 启用时必填 | 转发规则列表 |
| `targets` | 是 | 目标群组/频道，支持字符串或数组 |
| `forward_mode` | 否 | `forward` 保留原转发来源，`copy` 复制为新消息 |
| `silent` | 否 | 是否静默发送 |
| `dedupe` | 否 | 多条规则命中同一目标时是否去重，默认 `true` |
| `filters.mode` | 否 | `all`、`include`、`exclude`，默认 `all` |

## 过滤模式

- `all`：转发所有消息
- `include`：只转发命中过滤规则的消息
- `exclude`：转发未命中过滤规则的消息

`include` 和 `exclude` 必须配置非空 `filters.rules`。

## 过滤规则

### keyword

```json
{
  "type": "keyword",
  "config": {
    "words": ["BTC", "Bitcoin"],
    "match_case": false,
    "match_mode": "any"
  }
}
```

- `words`：非空字符串数组
- `match_case`：是否区分大小写，默认 `false`
- `match_mode`：`any` 或 `all`

### regex

```json
{
  "type": "regex",
  "config": {
    "pattern": "\\$[0-9,]+(?:\\.[0-9]{2})?",
    "flags": "i",
    "description": "美元价格"
  }
}
```

- `pattern`：非空正则表达式
- `flags`：可选，只允许 `i`、`m`、`s`
- 启动校验会提前编译正则，坏正则会阻止启动

### user

```json
{
  "type": "user",
  "config": {
    "users": ["@username", "123456789", 987654321]
  }
}
```

`users` 支持用户名、数字用户 ID、字符串形式的数字用户 ID。

### user_conditional

```json
{
  "type": "user_conditional",
  "config": {
    "users": ["@kol_1", "@kol_2"],
    "conditions": [
      {
        "type": "regex",
        "config": {
          "pattern": "0x[a-fA-F0-9]{40}"
        }
      }
    ],
    "condition_logic": "any"
  }
}
```

- `forward_all=true` 时，只要用户匹配就转发，忽略 `conditions`
- `forward_all=false` 或省略时，必须配置非空 `conditions`
- `condition_logic` 支持 `any` 或 `all`

### media

```json
{
  "type": "media",
  "config": {
    "types": ["photo", "video"],
    "match_mode": "any"
  }
}
```

媒体类型支持：`photo`、`video`、`document`、`audio`、`sticker`、`voice`。

### composite

```json
{
  "type": "composite",
  "config": {
    "logic": "and",
    "rules": [
      {
        "type": "user",
        "config": {
          "users": ["@analyst"]
        }
      },
      {
        "type": "keyword",
        "config": {
          "words": ["分析", "报告"]
        }
      }
    ]
  }
}
```

`logic` 支持 `and` 或 `or`，`rules` 必须非空。

### length

```json
{
  "type": "length",
  "config": {
    "min": 10,
    "max": 280
  }
}
```

`min` 和 `max` 至少配置一个，按消息文本长度匹配。

### link

```json
{
  "type": "link",
  "config": {
    "contains": true
  }
}
```

匹配包含链接的消息；`contains=false` 时匹配不含链接的消息。

### reply、bot、channel_post

```json
{
  "type": "reply",
  "config": {
    "is_reply": true
  }
}
```

```json
{
  "type": "bot",
  "config": {
    "is_bot": true
  }
}
```

```json
{
  "type": "channel_post",
  "config": {
    "is_channel_post": true
  }
}
```

这些规则分别匹配回复消息、bot 发送者和频道帖子。

## 示例：多路分发

```json
{
  "groups": [
    {
      "id": "signal_hub",
      "name": "交易信号中心",
      "source": "@all_signals",
      "rules": [
        {
          "targets": ["@btc_only"],
          "filters": {
            "mode": "include",
            "rules": [
              {
                "type": "keyword",
                "config": {
                  "words": ["BTC", "Bitcoin", "比特币"]
                }
              }
            ]
          }
        },
        {
          "targets": ["@eth_only"],
          "filters": {
            "mode": "include",
            "rules": [
              {
                "type": "keyword",
                "config": {
                  "words": ["ETH", "Ethereum", "以太坊"]
                }
              }
            ]
          }
        },
        {
          "targets": ["@all_backup"]
        }
      ]
    }
  ]
}
```

## 排查

1. 先运行 `uv run python main.py --check-config --config forward_rules.json`
2. 设置 `LOG_LEVEL=DEBUG` 查看规则匹配细节
3. 确认账号能读取源群消息
4. 确认账号在目标群有发送权限
5. 私有频道/超级群组优先使用 `-100...` 数字 ID
