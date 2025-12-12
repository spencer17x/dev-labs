# 🧪 Dev Lab

> 现代化开发实验室：智能代理 · 消息处理 · 零依赖部署 · 超快构建

[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178c6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.7+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![rolldown](https://img.shields.io/badge/rolldown-1.0.0--beta-ff6b35?logo=rollup&logoColor=white)](https://rolldown.rs/)
[![pnpm](https://img.shields.io/badge/pnpm-workspace-f69220?logo=pnpm&logoColor=white)](https://pnpm.io/)
[![License](https://img.shields.io/badge/License-MIT-green?logo=opensourceinitiative&logoColor=white)](./LICENSE)

## 🎯 项目概览

Dev Lab 是一个现代化的开发实验室，专注于智能代理、消息处理和自动化工具的快速原型开发。采用最新的构建技术和零依赖部署策略，让创新想法快速落地。

### 🏗️ 技术架构亮点

- **🚄 极速构建**: rolldown 驱动，构建速度提升 40-100 倍
- **📦 零依赖部署**: 单文件包含所有依赖，无需 node_modules
- **⚡ 热重载开发**: vite-node 提供毫秒级开发反馈
- **🔧 统一工作流**: pnpm workspace + 标准化脚本
- **🧪 实验友好**: 快速创建新项目，支持多种技术栈

### 🚀 实验项目

| 项目                                                 | 技术栈      | 部署大小  | 核心功能                     |
| ---------------------------------------------------- | ----------- | --------- | ---------------------------- |
| **[notifier-bot](./apps/notifier-bot/)**             | TypeScript  | **1.0MB** | Webhook 消息聚合与多渠道推送 |
| **[twitter-bot](./apps/twitter-bot/)**               | TypeScript  | **2.4MB** | Twitter 到 Telegram 消息转发 |
| **[telegram-forwarder](./apps/telegram-forwarder/)** | Python 3.7+ | 虚拟环境  | Telegram 智能转发机器人      |
| **[telegram-watcher](./apps/telegram-watcher/)**     | Python 3.7+ | 虚拟环境  | Telegram 消息监听处理        |

## 📁 项目结构

```
dev-lab/
├─ apps/                          # 实验应用
│  ├─ notifier-bot/              # 消息聚合通知服务
│  ├─ twitter-bot/               # Twitter 转发机器人
│  ├─ telegram-forwarder/        # Telegram 转发机器人
│  └─ telegram-watcher/          # Telegram 消息监听
├─ scripts/                      # 开发脚本
│  └─ create-project.ts          # 项目生成脚本
├─ package.json                  # 工作区配置
├─ pnpm-workspace.yaml          # pnpm 工作区
├─ tsconfig.json                # TypeScript 根配置
└─ SECURITY.md                  # 安全指南
```

## ⚡ 快速开始

### 📋 环境要求

```bash
# 基础环境
Node.js ≥ 18.0.0    # TypeScript 项目
Python ≥ 3.7.0      # Python 项目
pnpm ≥ 8.0.0        # 推荐包管理器
```

### 🚀 一键启动

#### TypeScript 项目（零依赖部署）

```bash
# 克隆仓库
git clone <repo-url> dev-lab && cd dev-lab

# 安装所有依赖
pnpm install

# 开发模式（热重载 + 毫秒级启动）
pnpm --filter notifier-bot dev
pnpm --filter twitter-bot dev

# 构建生产版本（零依赖单文件）
pnpm --filter <project> build

# 生产环境启动
pnpm --filter <project> start:prod
```

#### Python 项目

```bash
# 进入项目目录
cd apps/telegram-forwarder  # 或其他 Python 项目

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安装依赖并运行
pip install -r requirements.txt
python main.py
```

### 🎯 实验场景示例

| 实验场景           | 推荐组合                             | 技术价值                      |
| ------------------ | ------------------------------------ | ----------------------------- |
| **社交媒体自动化** | `twitter-bot` + `telegram-forwarder` | 跨平台消息流转与智能过滤      |
| **消息处理管道**   | `notifier-bot` + `telegram-watcher`  | Webhook 聚合 → 多渠道分发实验 |
| **智能通知系统**   | `notifier-bot` + `twitter-bot`       | 多源信息聚合与推送            |

## 🏗️ 核心技术栈

### ⚡ 构建系统革命

```bash
# 传统构建 vs rolldown 构建
npm run build    # 传统: 2-15 秒
pnpm build       # rolldown: 0.03-0.1 秒 (100倍提升!)

# 零依赖部署
dist/
├── index.cjs           # 单文件包含所有依赖 (1.0MB - 2.4MB)
└── .env.example        # 环境配置模板
```

### 🔧 开发体验

- **rolldown v1.0.0-beta**: Rust 驱动的超快构建器
- **vite-node v3.2.4**: 开发时毫秒级 TypeScript 执行
- **pnpm workspace**: 统一的多包管理和脚本系统

### 🚀 部署策略

```bash
# TypeScript 项目：零依赖云部署
pnpm build
scp dist/index.cjs server:/app/
node /app/index.cjs  # 无需 npm install，秒级启动

# Python 项目：虚拟环境部署
pip install -r requirements.txt
python main.py
```

## 🛠️ 创建新项目

使用内置脚本快速生成新项目骨架：

```bash
# 交互式创建项目
pnpm new

# 命令行快速创建
pnpm new <type> <name> [version] [description] [author]

# 示例
pnpm new apps my-service 1.0.0 "我的服务" "作者名"
```

**生成的项目特性：**

- 📦 **零依赖部署** - 单个 CJS 文件包含所有依赖
- ⚡ **毫秒级构建** - rolldown 超快构建体验
- 🔥 **热重载开发** - vite-node 实时执行
- 🛡️ **完整类型安全** - TypeScript 严格模式
- 📋 **标准化结构** - 统一的项目结构和配置

## 🤝 加入实验

Dev Lab 欢迎所有形式的技术实验和贡献！无论是新的实验项目、Bug 修复、功能改进还是文档完善。

### 🔬 实验工作流

```bash
# 1. Fork 仓库并创建实验分支
git checkout -b experiment/awesome-idea

# 2. 安装依赖并开始实验
pnpm install
pnpm --filter <project-name> dev

# 3. 构建验证实验结果
pnpm --filter <project-name> build
pnpm -w -r build  # 全局构建验证

# 4. 提交实验成果
git commit -m "feat: add awesome experiment"

# 5. 分享实验成果
```

### 📏 代码规范

- **TypeScript**: ESLint + Prettier + 严格模式
- **Python**: PEP 8 + Black 格式化
- **提交信息**: [Conventional Commits](https://conventionalcommits.org/) 规范
- **文档**: Markdown + 中英文对照

### 🧪 质量保证

```bash
# TypeScript 项目
pnpm test        # 单元测试
pnpm type-check  # 类型检查
pnpm lint        # 代码检查

# Python 项目
python -m pytest tests/     # 单元测试
python -m mypy src/         # 类型检查
python -m flake8 src/       # 代码检查
```

## 📄 许可证与声明

### 开源许可

本项目采用 [MIT 许可证](./LICENSE) 开源，允许自由使用、修改和分发。

### ⚠️ 实验须知

- **🎓 实验目的**: 本项目专为技术学习和实验研究设计
- **⚖️ 合规实验**: 实验前请了解并遵守相关法律法规和平台服务条款
- **🌐 负责任实验**: API 调用和监控功能请合理控制频率，避免对目标服务造成负担
- **💰 风险意识**: 涉及金融相关实验时，请注意风险控制，仅用于学习目的
- **🛡️ 安全实验**: 请妥善保管 API 密钥和配置信息，避免在实验中泄露敏感数据

## 📚 项目文档

| 项目               | 技术栈      | 部署大小  | 文档链接                                      | 核心功能                 |
| ------------------ | ----------- | --------- | --------------------------------------------- | ------------------------ |
| **消息聚合服务**   | TypeScript  | **1.0MB** | [README](./apps/notifier-bot/README.md)       | Webhook 聚合与推送       |
| **Twitter 机器人** | TypeScript  | **2.4MB** | [README](./apps/twitter-bot/README.md)        | Twitter 到 Telegram 转发 |
| **Telegram 转发**  | Python 3.7+ | 虚拟环境  | [README](./apps/telegram-forwarder/README.md) | 智能消息转发与过滤       |
| **Telegram 监听**  | Python 3.7+ | 虚拟环境  | [README](./apps/telegram-watcher/README.md)   | 消息监听与处理服务       |

---

<div align="center">

### ⭐ 如果这个项目对你有帮助，请给个 Star！

**Dev Lab · 让技术实验更有趣 · 让创新想法快速落地**

</div>
