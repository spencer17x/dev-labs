import { existsSync, mkdirSync, writeFileSync } from 'fs';
import { join, resolve } from 'path';
import { createDirectoryStructure } from './directory';
import { generateSourceFiles } from './generators/source-files';
import { generateEnvExample, generateTsConfig } from './templates/config';
import { generatePackageJson } from './templates/package';
import { generateReadme } from './templates/readme';
import { generateRolldownConfig } from './templates/rolldown';
import type { ProjectConfig } from './types';

// 获取根目录
const rootDir = resolve(process.cwd());

// 创建项目的核心逻辑
export const createProject = async (config: ProjectConfig) => {
  // 检查项目是否已存在
  const projectPath = join(rootDir, config.type, config.name);
  if (existsSync(projectPath)) {
    console.error(`❌ 项目已存在: ${projectPath}`);
    process.exit(1);
  }

  // 创建项目目录
  mkdirSync(projectPath, { recursive: true });

  // 创建目录结构
  createDirectoryStructure(projectPath, config.type);

  // 生成配置文件
  writeFileSync(join(projectPath, 'package.json'), generatePackageJson(config));
  writeFileSync(join(projectPath, 'rolldown.config.ts'), generateRolldownConfig(config.type));
  writeFileSync(join(projectPath, 'tsconfig.json'), generateTsConfig(config.type));
  writeFileSync(join(projectPath, '.env.example'), generateEnvExample());
  writeFileSync(join(projectPath, 'README.md'), generateReadme(config));

  // 生成源代码文件
  generateSourceFiles(projectPath, config.name, config.type);

  // 显示成功信息
  showSuccessMessage(config, projectPath);
};

const showSuccessMessage = (config: ProjectConfig, projectPath: string) => {
  console.log('\n🎉 项目创建成功!');
  console.log('═'.repeat(50));
  console.log('📁 项目路径:', projectPath);
  console.log('📦 项目类型: 📱 应用服务');

  console.log('\n🚀 快速开始:');
  console.log(`   cd ${config.type}/${config.name}`);
  console.log('   cp .env.example .env');
  console.log('   pnpm dev');

  console.log('\n📖 更多信息请查看项目 README.md');
};
