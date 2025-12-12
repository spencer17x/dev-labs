import { existsSync, mkdirSync } from 'fs';
import { join } from 'path';

// 创建目录结构
export const createDirectoryStructure = (projectPath: string, projectType: string) => {
  const directories = ['src', 'src/config', 'src/services', 'src/types'];

  directories.forEach(dir => {
    const fullPath = join(projectPath, dir);
    if (!existsSync(fullPath)) {
      mkdirSync(fullPath, { recursive: true });
    }
  });
};
