import inquirer from 'inquirer';
import type { ProjectConfig } from './types';
import { PROJECT_TYPES } from './types';
import { validateProjectName } from './validators';

// 定义问答的中间状态类型
interface PartialAnswers {
  type?: string;
  name?: string;
  version?: string;
  description?: string;
  author?: string;
  confirm?: boolean;
}

// 交互式界面
export const createInteractiveConfig = async (): Promise<ProjectConfig> => {
  console.log('🚀 开始交互式项目创建...\n');

  const answers = await inquirer.prompt([
    {
      type: 'list',
      name: 'type',
      message: '🎯 请选择项目类型:',
      choices: PROJECT_TYPES.map(type => ({
        name: type.name,
        value: type.value,
        short: type.short,
      })),
      pageSize: 10,
      loop: false,
    },
    {
      type: 'input',
      name: 'name',
      message: () => {
        return `📝 请输入项目名称 (例: my-service):`;
      },
      validate: (input: string) => {
        if (!input.trim()) {
          return '❌ 项目名称不能为空';
        }
        if (!validateProjectName(input.trim())) {
          return '❌ 项目名称只能包含小写字母、数字和连字符';
        }
        return true;
      },
      filter: (input: string) => input.trim(),
    },
    {
      type: 'input',
      name: 'version',
      message: '📋 请输入项目版本:',
      default: '1.0.0',
      validate: (input: string) => {
        if (!input.trim()) {
          return '❌ 版本号不能为空';
        }
        // 简单的版本号验证
        if (!/^\d+\.\d+\.\d+/.test(input.trim())) {
          return '❌ 请输入有效的版本号格式 (如: 1.0.0)';
        }
        return true;
      },
    },
    {
      type: 'input',
      name: 'description',
      message: '📄 请输入项目描述:',
      default: (answers: PartialAnswers) => {
        return `A modern TypeScript ${answers.type} service`;
      },
    },
    {
      type: 'input',
      name: 'author',
      message: '👤 请输入作者名称 (可选):',
      default: '',
    },
    {
      type: 'confirm',
      name: 'confirm',
      message: (answers: PartialAnswers) => {
        console.log('\n' + '═'.repeat(50));
        console.log('📋 项目信息预览');
        console.log('═'.repeat(50));
        console.log(`📱 项目类型: ${answers.type}`);
        console.log(`📦 项目名称: ${answers.name}`);
        console.log(`🏷️  项目版本: ${answers.version}`);
        console.log(`📄 项目描述: ${answers.description}`);
        console.log(`👤 作者信息: ${answers.author || '(未填写)'}`);
        console.log(`📁 创建路径: ${answers.type}/${answers.name}/`);
        console.log('═'.repeat(50));

        return '✅ 确认创建项目?';
      },
      default: true,
    },
  ]);

  if (!answers.confirm) {
    throw new Error('User canceled project creation');
  }

  // 移除确认字段
  const { confirm, ...config } = answers;
  return config as ProjectConfig;
};
