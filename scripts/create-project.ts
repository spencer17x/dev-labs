#!/usr/bin/env node

import { parseCliArgs, showHelp } from './lib/cli';
import { createInteractiveConfig } from './lib/interactive';
import { createProject } from './lib/project-creator';

// 主函数
async function main() {
  console.log('🧪 Dev Lab - 项目创建脚本');
  console.log('═'.repeat(50));

  // 检查命令行参数
  const args = process.argv.slice(2);

  // 显示帮助信息
  if (args.length === 1 && args[0] === '--help') {
    showHelp();
    return;
  }

  // 尝试解析命令行参数
  const config = parseCliArgs(args);

  if (config) {
    // 命令行模式
    console.log(`📦 正在创建项目: ${config.name} (${config.type})...`);
    await createProject(config);
    return;
  }

  // 交互式模式 - 当没有参数或参数无效时
  try {
    const interactiveConfig = await createInteractiveConfig();
    console.log(`\n📦 正在创建项目: ${interactiveConfig.name} (${interactiveConfig.type})...`);
    await createProject(interactiveConfig);
  } catch (error) {
    if (error instanceof Error) {
      if (
        error.message.includes('User force closed') ||
        error.message.includes('canceled') ||
        error.message.includes('User canceled')
      ) {
        console.log('\n👋 已取消项目创建');
        return;
      }
    }
    throw error;
  }
}

// 运行主函数
main().catch(error => {
  console.error('❌ 创建项目失败:', error.message);
  process.exit(1);
});
