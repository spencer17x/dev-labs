import type { ProjectConfig } from '../types';

// 生成package.json
export const generatePackageJson = (config: ProjectConfig): string => {
  return JSON.stringify(
    {
      name: config.name,
      version: config.version,
      description: config.description,
      type: 'module',
      main: 'dist/index.cjs',
      scripts: {
        clean: 'rm -rf dist',
        build: 'npm run clean && rolldown -c rolldown.config.ts',
        dev: 'vite-node src/index.ts',
        'start:prod': 'node dist/index.cjs',
      },
      keywords: [],
      author: config.author,
      license: 'MIT',
      devDependencies: {},
      dependencies: {},
    },
    null,
    2,
  );
};
