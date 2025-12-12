# 🧪 Dev Lab - 项目创建脚本

这是一个模块化的项目创建脚本，支持创建不同类型的 TypeScript 项目。

## 🚀 使用方法

### 交互式创建

```bash
pnpm new
```

启动交互式界面，引导你完成项目创建：

1. **选择项目类型**：从 2 种项目类型中选择
2. **输入项目名称**：支持实时验证
3. **设置版本号**：默认 1.0.0
4. **添加项目描述**：智能默认值
5. **填写作者信息**：可选
6. **确认创建**：预览所有信息后确认

### 命令行创建

```bash
# 创建应用服务
pnpm new apps my-service 1.0.0 "My Service" "Your Name"
```

### 查看帮助

```bash
pnpm new --help
```

## 📁 项目结构

```
scripts/
├── create-project.ts           # 主入口文件
└── lib/
    ├── types.ts               # 类型定义和常量
    ├── validators.ts          # 验证函数
    ├── directory.ts           # 目录操作
    ├── cli.ts                # 命令行参数处理
    ├── interactive.ts        # 交互式用户界面
    ├── project-creator.ts    # 项目创建核心逻辑
    ├── templates/            # 模板生成器
    │   ├── package.ts        # package.json 模板
    │   ├── rolldown.ts       # rolldown 配置模板
    │   ├── config.ts         # tsconfig 和环境配置模板
    │   └── readme.ts         # README 文档模板
    └── generators/           # 代码生成器
        └── source-files.ts     # 基础源码生成
```

## 🎯 支持的项目类型

- **📱 apps**: 基于 TypeScript 的应用服务，支持零依赖部署

## ✨ 特性

- 🎮 **优雅的交互式界面**: 使用 inquirer 提供丰富的交互体验
- 💻 **灵活的命令行支持**: 支持完整的命令行参数创建
- 📝 **完整的 TypeScript 类型支持**: 严格的类型检查和智能提示
- 🏗️ **模块化设计**: 易于扩展和维护
- 📄 **自动生成项目文档**: 包含完整的 README 和配置文件
- ✅ **项目信息预览**: 创建前确认所有配置信息

## 📝 项目预览

创建前会显示完整的项目信息预览：

```
══════════════════════════════════════════════════
📋 项目信息预览
══════════════════════════════════════════════════
📱 项目类型: apps
📦 项目名称: my-service
🏷️  项目版本: 1.0.0
📄 项目描述: A modern TypeScript apps service
👤 作者信息: Your Name
📁 创建路径: apps/my-service/
══════════════════════════════════════════════════
```

## 🔧 生成的项目结构

### Apps 项目

```
my-service/
├── src/
│   ├── config/          # 配置文件
│   ├── services/        # 业务服务
│   ├── types/           # 类型定义
│   └── index.ts         # 入口文件
├── .env.example         # 环境配置模板
├── rolldown.config.ts   # 构建配置
└── package.json
```
