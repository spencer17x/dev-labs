import { writeFileSync } from 'fs';
import { join } from 'path';

// 生成基础源代码文件
export const generateSourceFiles = (
  projectPath: string,
  projectName: string,
  projectType: string,
) => {
  // src/index.ts
  writeFileSync(join(projectPath, 'src/index.ts'), generateIndexFile(projectName));

  // src/config/index.ts
  writeFileSync(join(projectPath, 'src/config/index.ts'), generateConfigFile());

  // src/services/index.ts
  writeFileSync(join(projectPath, 'src/services/index.ts'), generateServicesFile());

  // src/types/index.ts
  writeFileSync(join(projectPath, 'src/types/index.ts'), generateTypesFile());
};

const generateIndexFile = (projectName: string): string => {
  return `import { config } from './config/index.js';
import { logger } from './services/index.js';

// 简单的主函数
async function main() {
  logger.info('🚀 启动 ${projectName}...');
  logger.info(\`📋 配置: \${JSON.stringify(config, null, 2)}\`);

  // 在这里添加你的业务逻辑
  logger.info('✅ ${projectName} 运行中');

  // 保持程序运行
  process.on('SIGINT', () => {
    logger.info('👋 正在优雅关闭...');
    process.exit(0);
  });
}

// 运行主函数
main().catch((error) => {
  logger.error(\`❌ 启动失败: \${error.message}\`);
  process.exit(1);
});
`;
};

const generateConfigFile = (): string => {
  return `import dotenv from 'dotenv';

// 加载环境变量
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || '3000', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
  logLevel: process.env.LOG_LEVEL || 'info',

  // 可根据需要添加更多配置项
  // apiKey: process.env.API_KEY || '',
  // apiSecret: process.env.API_SECRET || '',
};

export type Config = typeof config;
`;
};

const generateServicesFile = (): string => {
  return `// 简单的日志服务
export const logger = {
  info: (message: string) => {
    console.log(\`[\${new Date().toISOString()}] INFO: \${message}\`);
  },
  error: (message: string) => {
    console.error(\`[\${new Date().toISOString()}] ERROR: \${message}\`);
  },
  warn: (message: string) => {
    console.warn(\`[\${new Date().toISOString()}] WARN: \${message}\`);
  },
  debug: (message: string) => {
    if (process.env.NODE_ENV === 'development') {
      console.debug(\`[\${new Date().toISOString()}] DEBUG: \${message}\`);
    }
  }
};
`;
};

const generateTypesFile = (): string => {
  return `// 基础类型定义
export interface AppConfig {
  port: number;
  nodeEnv: string;
  logLevel: string;
}

// 日志级别
export type LogLevel = 'info' | 'warn' | 'error' | 'debug';

// 通用响应类型
export interface BaseResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  timestamp: string;
}
`;
};
