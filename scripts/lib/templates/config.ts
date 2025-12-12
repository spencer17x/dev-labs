// 生成tsconfig.json
export const generateTsConfig = (projectType?: string): string => {
  const config = {
    extends: '../../tsconfig.json',
    compilerOptions: {
      outDir: './dist',
      rootDir: './src',
      baseUrl: '.',
      paths: {
        '@/*': ['./src/*'],
      },
    },
    include: ['src/**/*'],
    exclude: ['node_modules', 'dist'],
  };

  return JSON.stringify(config, null, 2);
};

// 生成.env.example
export const generateEnvExample = (): string => {
  return `# 环境配置
NODE_ENV=development
PORT=3000

# 日志配置
LOG_LEVEL=info

# 数据库配置（如需要）
# DATABASE_URL=

# API 密钥（如需要）
# API_KEY=
# API_SECRET=
`;
};
