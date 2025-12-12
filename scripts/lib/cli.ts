import type { ProjectConfig } from './types';
import { PROJECT_TYPES } from './types';
import { validateProjectName } from './validators';

// 处理命令行参数
export const parseCliArgs = (args: string[]): ProjectConfig | null => {
  if (args.length >= 2) {
    const [type, name, version = '1.0.0', description = '', author = ''] = args;

    if (!['apps'].includes(type)) {
      return null; // 返回 null 而不是直接退出
    }

    if (!validateProjectName(name)) {
      return null; // 返回 null 而不是直接退出
    }

    return {
      type: type as 'apps',
      name,
      version,
      description: description || `A modern TypeScript ${type} service`,
      author,
    };
  }

  return null;
};

// 显示帮助信息
export const showHelp = () => {
  console.log('用法:');
  console.log('  pnpm new                              # 交互式创建');
  console.log('  pnpm new <type> <name> [options]      # 命令行创建');
  console.log('');
  console.log('项目类型:');
  PROJECT_TYPES.forEach(type => {
    console.log(`  ${type.value.padEnd(20)} ${type.name}`);
  });
  console.log('');
  console.log('示例:');
  console.log('  pnpm new apps my-service 1.0.0 "My Service" "Your Name"');
};
