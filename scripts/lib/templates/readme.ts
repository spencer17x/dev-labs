import type { ProjectConfig } from '../types';

export const generateReadme = (config: ProjectConfig): string => {
  return `# 🚀 ${config.name}

> ${config.description}

## Quick Start

\`\`\`bash
# 开发模式
pnpm dev

# 构建生产版本
pnpm build

# 生产环境启动
pnpm start:prod
\`\`\`

## Project Structure

\`\`\`
${config.name}/
├── src/
│   ├── config/          # 配置文件
│   ├── services/        # 业务服务
│   ├── types/           # 类型定义
│   └── index.ts         # 入口文件
├── .env.example         # 环境配置模板
├── rolldown.config.ts   # 构建配置
└── package.json
\`\`\`

复制 \`.env.example\` 为 \`.env\` 并配置相应的环境变量。
`;
};
