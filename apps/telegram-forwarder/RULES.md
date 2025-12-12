# 转发规则配置详解

本文档详细说明 Telegram 消息转发机器人的规则配置方式和各种过滤规则类型。

## 配置文件结构

`forward_rules.json` 采用群组维度的配置结构：

```json
{
  "session_name": "telegram_forwarder_session",
  "groups": [
    {
      "id": "unique_group_id",
      "name": "群组显示名称",
      "enabled": true,
      "source": "@source_channel",
      "rules": [
        {
          "enabled": true,
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

## 字段说明

### 群组配置 (groups[])

| 字段      | 类型          | 必填 | 默认值 | 说明                           |
| --------- | ------------- | ---- | ------ | ------------------------------ |
| `id`      | string        | 是   | -      | 群组唯一标识符，用于日志和调试 |
| `name`    | string        | 是   | -      | 群组显示名称                   |
| `enabled` | boolean       | 否   | `true` | 是否启用该群组                 |
| `source`  | string/number | 是   | -      | 源群组/频道（用户名或数字ID）  |
| `rules`   | array         | 是   | -      | 转发规则列表                   |

**source 格式说明：**

- 公开群组/频道：使用 `@username` 格式，如 `"@binance_announcements"`
- 私有群组：使用数字 ID，如 `-1001234567890`

### 规则配置 (rules[])

| 字段      | 类型    | 必填 | 默认值 | 说明                       |
| --------- | ------- | ---- | ------ | -------------------------- |
| `enabled` | boolean | 否   | `true` | 是否启用该规则             |
| `targets` | array   | 是   | -      | 目标群组列表（字符串数组） |
| `filters` | object  | 是   | -      | 过滤器配置                 |

### 过滤器配置 (filters)

| 字段    | 类型   | 必填 | 默认值 | 说明                                           |
| ------- | ------ | ---- | ------ | ---------------------------------------------- |
| `mode`  | string | 是   | -      | 过滤模式：`all`、`include`、`exclude`          |
| `rules` | array  | 否   | `[]`   | 过滤规则列表（mode 为 include/exclude 时需要） |

## 过滤模式

### 1. all - 全量转发

转发所有消息，不进行任何过滤。

```json
{
  "filters": {
    "mode": "all"
  }
}
```

**使用场景：**

- 完整备份/同步频道
- 消息归档
- 镜像频道

### 2. include - 白名单模式

只转发匹配规则的消息。

```json
{
  "filters": {
    "mode": "include",
    "rules": [
      {
        "type": "keyword",
        "config": {
          "words": ["重要", "紧急"]
        }
      }
    ]
  }
}
```

**使用场景：**

- 筛选特定主题的消息
- 追踪特定用户的发言
- 提取包含关键信息的消息

### 3. exclude - 黑名单模式

转发所有消息，但排除匹配规则的消息。

```json
{
  "filters": {
    "mode": "exclude",
    "rules": [
      {
        "type": "user",
        "config": {
          "users": ["@spammer"],
          "forward_all": true
        }
      }
    ]
  }
}
```

**使用场景：**

- 过滤垃圾消息
- 屏蔽特定用户
- 排除广告内容

## 过滤规则类型

### 1. 关键词过滤 (keyword)

匹配消息中是否包含指定关键词。

```json
{
  "type": "keyword",
  "config": {
    "words": ["BTC", "ETH", "加密货币"],
    "match_case": false,
    "match_mode": "any"
  }
}
```

**配置参数：**

- `words` (array, 必填): 关键词列表
- `match_case` (boolean, 可选, 默认 `false`): 是否区分大小写
- `match_mode` (string, 可选, 默认 `"any"`): 匹配模式
  - `"any"`: 匹配任意一个关键词
  - `"all"`: 必须匹配所有关键词

**示例场景：**

```json
// 监控加密货币相关消息
{
  "type": "keyword",
  "config": {
    "words": ["BTC", "Bitcoin", "比特币"],
    "match_case": false,
    "match_mode": "any"
  }
}
```

### 2. 正则表达式过滤 (regex)

使用正则表达式匹配消息内容。

```json
{
  "type": "regex",
  "config": {
    "pattern": "\\$[0-9]+\\.?[0-9]*",
    "flags": "i",
    "description": "匹配价格"
  }
}
```

**配置参数：**

- `pattern` (string, 必填): 正则表达式
- `flags` (string, 可选): 正则标志
  - `i`: 忽略大小写
  - `m`: 多行模式
  - `s`: 单行模式（. 匹配换行符）
- `description` (string, 可选): 规则描述，用于日志

**示例场景：**

```json
// 匹配加密货币地址
{
  "type": "regex",
  "config": {
    "pattern": "(?:0x[a-fA-F0-9]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})",
    "description": "匹配以太坊地址或比特币地址"
  }
}

// 匹配价格信息
{
  "type": "regex",
  "config": {
    "pattern": "\\$[0-9,]+(?:\\.[0-9]{2})?",
    "description": "匹配美元价格"
  }
}
```

### 3. 用户过滤 (user)

只转发特定用户的消息。

```json
{
  "type": "user",
  "config": {
    "users": ["@username", 123456789],
    "forward_all": true
  }
}
```

**配置参数：**

- `users` (array, 必填): 用户列表（用户名或用户ID）
  - 用户名格式：`"@username"` 或 `"username"`
  - 用户ID格式：数字，如 `123456789`
- `forward_all` (boolean, 可选, 默认 `true`): 是否转发该用户的所有消息

**示例场景：**

```json
// 追踪专家分析师
{
  "type": "user",
  "config": {
    "users": ["@crypto_expert", "@trader_pro", 987654321],
    "forward_all": true
  }
}
```

### 4. 用户条件过滤 (user_conditional)

转发特定用户的消息，但需要满足附加条件。

```json
{
  "type": "user_conditional",
  "config": {
    "users": ["@vip_user"],
    "forward_all": false,
    "conditions": [
      {
        "type": "keyword",
        "config": {
          "words": ["重要"],
          "match_mode": "any"
        }
      }
    ],
    "condition_logic": "any"
  }
}
```

**配置参数：**

- `users` (array, 必填): 用户列表
- `forward_all` (boolean, 可选, 默认 `false`): 如果为 `true`，忽略条件，转发所有消息
- `conditions` (array, 可选): 附加条件列表（可以是任意其他规则类型）
- `condition_logic` (string, 可选, 默认 `"any"`): 条件逻辑
  - `"any"`: 满足任意一个条件即可
  - `"all"`: 必须满足所有条件

**示例场景：**

```json
// 只转发 KOL 发送的包含地址的消息
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

// 只转发 VIP 用户的重要消息
{
  "type": "user_conditional",
  "config": {
    "users": ["@vip_member"],
    "conditions": [
      {
        "type": "keyword",
        "config": {
          "words": ["紧急", "重要", "必读"]
        }
      }
    ],
    "condition_logic": "any"
  }
}
```

### 5. 媒体类型过滤 (media)

根据消息的媒体类型进行过滤。

```json
{
  "type": "media",
  "config": {
    "types": ["photo", "video"],
    "match_mode": "any"
  }
}
```

**配置参数：**

- `types` (array, 必填): 媒体类型列表
  - `"photo"`: 图片
  - `"video"`: 视频
  - `"document"`: 文档/文件
  - `"audio"`: 音频
  - `"sticker"`: 贴纸
  - `"voice"`: 语音消息
- `match_mode` (string, 可选, 默认 `"any"`): 匹配模式
  - `"any"`: 包含任意一种类型
  - `"all"`: 必须包含所有类型

**示例场景：**

```json
// 只转发图片消息
{
  "type": "media",
  "config": {
    "types": ["photo"],
    "match_mode": "any"
  }
}

// 转发图片或视频
{
  "type": "media",
  "config": {
    "types": ["photo", "video"],
    "match_mode": "any"
  }
}
```

### 6. 组合规则 (composite)

使用逻辑运算符组合多个规则。

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
          "words": ["分析"]
        }
      }
    ]
  }
}
```

**配置参数：**

- `logic` (string, 必填): 逻辑运算符
  - `"and"`: 所有规则都必须匹配
  - `"or"`: 任意一个规则匹配即可
- `rules` (array, 必填): 子规则列表

**示例场景：**

```json
// 来自分析师的分析报告（用户 AND 关键词）
{
  "type": "composite",
  "config": {
    "logic": "and",
    "rules": [
      {
        "type": "user",
        "config": {
          "users": ["@analyst_1", "@analyst_2"]
        }
      },
      {
        "type": "keyword",
        "config": {
          "words": ["分析", "报告", "研究"]
        }
      }
    ]
  }
}

// 包含地址或价格信息（正则 OR 正则）
{
  "type": "composite",
  "config": {
    "logic": "or",
    "rules": [
      {
        "type": "regex",
        "config": {
          "pattern": "0x[a-fA-F0-9]{40}"
        }
      },
      {
        "type": "regex",
        "config": {
          "pattern": "\\$[0-9,]+"
        }
      }
    ]
  }
}
```

## 配置示例

### 示例 1：全量同步

转发源群组的所有消息到目标群组：

```json
{
  "id": "full_sync",
  "name": "新闻频道全量同步",
  "enabled": true,
  "source": "@news_channel",
  "rules": [
    {
      "targets": ["@my_backup_channel"],
      "filters": {
        "mode": "all"
      }
    }
  ]
}
```

### 示例 2：关键词过滤

只转发包含特定关键词的消息：

```json
{
  "id": "crypto_news",
  "name": "加密货币新闻",
  "enabled": true,
  "source": "@crypto_channel",
  "rules": [
    {
      "targets": ["@my_crypto_digest"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "keyword",
            "config": {
              "words": ["BTC", "Bitcoin", "比特币"],
              "match_case": false,
              "match_mode": "any"
            }
          }
        ]
      }
    }
  ]
}
```

### 示例 3：用户追踪

只转发特定用户的消息：

```json
{
  "id": "vip_tracking",
  "name": "VIP用户追踪",
  "enabled": true,
  "source": "@discussion_group",
  "rules": [
    {
      "targets": ["@vip_messages"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "user",
            "config": {
              "users": ["@expert1", "@expert2", 987654321],
              "forward_all": true
            }
          }
        ]
      }
    }
  ]
}
```

### 示例 4：一源多目标

同一个源群组，不同规则转发到不同目标：

```json
{
  "id": "multi_target",
  "name": "交易信号多目标分发",
  "enabled": true,
  "source": "@trading_signals",
  "rules": [
    {
      "targets": ["@btc_signals"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "keyword",
            "config": {
              "words": ["BTC", "Bitcoin"]
            }
          }
        ]
      }
    },
    {
      "targets": ["@eth_signals"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "keyword",
            "config": {
              "words": ["ETH", "Ethereum"]
            }
          }
        ]
      }
    },
    {
      "targets": ["@all_signals_backup"],
      "filters": {
        "mode": "all"
      }
    }
  ]
}
```

### 示例 5：地址监控

监控特定用户发送的加密货币地址：

```json
{
  "id": "address_monitor",
  "name": "KOL地址监控",
  "enabled": true,
  "source": -1001234567890,
  "rules": [
    {
      "targets": ["@address_alerts"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "user_conditional",
            "config": {
              "users": ["@kol_trader", "@whale_watcher"],
              "conditions": [
                {
                  "type": "regex",
                  "config": {
                    "pattern": "(?:0x[a-fA-F0-9]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})",
                    "description": "匹配以太坊或比特币地址"
                  }
                }
              ],
              "condition_logic": "any"
            }
          }
        ]
      }
    }
  ]
}
```

### 示例 6：媒体过滤

只转发包含图片的消息：

```json
{
  "id": "media_only",
  "name": "图片消息收集",
  "enabled": true,
  "source": "@art_channel",
  "rules": [
    {
      "targets": ["@my_gallery"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "media",
            "config": {
              "types": ["photo"],
              "match_mode": "any"
            }
          }
        ]
      }
    }
  ]
}
```

### 示例 7：复杂组合

组合多种条件进行精确过滤：

```json
{
  "id": "complex_filter",
  "name": "高质量信号筛选",
  "enabled": true,
  "source": "@signal_channel",
  "rules": [
    {
      "targets": ["@premium_signals"],
      "filters": {
        "mode": "include",
        "rules": [
          {
            "type": "composite",
            "config": {
              "logic": "and",
              "rules": [
                {
                  "type": "user",
                  "config": {
                    "users": ["@verified_analyst"]
                  }
                },
                {
                  "type": "composite",
                  "config": {
                    "logic": "or",
                    "rules": [
                      {
                        "type": "keyword",
                        "config": {
                          "words": ["买入", "卖出"]
                        }
                      },
                      {
                        "type": "media",
                        "config": {
                          "types": ["photo"]
                        }
                      }
                    ]
                  }
                }
              ]
            }
          }
        ]
      }
    }
  ]
}
```

## 最佳实践

### 1. 规则命名

使用有意义的 `id` 和 `name` 帮助识别规则：

```json
{
  "id": "btc_price_alerts", // 简短的标识符
  "name": "BTC价格提醒 - 监控价格相关消息" // 详细描述
}
```

### 2. 规则顺序

- 将更具体的规则放在前面
- 将全量转发规则放在最后作为兜底

```json
{
  "rules": [
    {
      "targets": ["@urgent_channel"],
      "filters": {
        "mode": "include",
        "rules": [{ "type": "keyword", "config": { "words": ["紧急"] } }]
      }
    },
    {
      "targets": ["@backup_channel"],
      "filters": {
        "mode": "all"
      }
    }
  ]
}
```

### 3. 测试规则

在生产环境使用前，建议：

1. 创建测试群组
2. 使用 `enabled: false` 暂时禁用规则
3. 观察日志输出验证规则是否正确

### 4. 性能优化

- 避免过于复杂的正则表达式
- 合理使用 `composite` 规则，避免过深的嵌套
- 对于简单场景，使用 `keyword` 而非 `regex`

### 5. 安全建议

- 不要在配置文件中包含敏感信息
- 定期检查 `targets` 列表确保目标群组正确
- 对私有群组使用数字 ID 而非用户名

## 故障排查

### 规则不生效？

1. 检查 `enabled` 字段是否为 `true`
2. 检查 `source` 格式是否正确
3. 检查 `targets` 数组是否为空
4. 查看日志输出了解规则匹配情况

### 正则表达式不工作？

1. 使用在线工具测试正则表达式（如 regex101.com）
2. 注意 JSON 中反斜杠需要转义：`\\` 表示一个反斜杠
3. 检查 `flags` 参数是否正确

### 消息没有被转发？

1. 检查是否触发了频率限制
2. 确认机器人账号在目标群组中
3. 确认目标群组允许机器人发送消息
4. 查看错误日志获取详细信息

## 更多信息

- [README.md](README.md) - 项目概览和快速开始
- [forward_rules.example.json](forward_rules.example.json) - 配置示例文件
