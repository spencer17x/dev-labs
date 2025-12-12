// 项目配置类型定义
export interface ProjectConfig {
  type: 'apps';
  name: string;
  version: string;
  description: string;
  author: string;
}

// 项目类型选项
export const PROJECT_TYPES = [
  {
    name: '📱 应用服务 (apps) - 基于 TypeScript 的应用服务，支持零依赖部署',
    value: 'apps',
    short: 'apps',
  },
];
