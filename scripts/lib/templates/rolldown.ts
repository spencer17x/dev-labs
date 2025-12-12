// 生成rolldown.config.ts
export const generateRolldownConfig = (projectType: string): string => {
  return `import { defineConfig } from 'rolldown';

export default defineConfig({
  input: 'src/index.ts',
  output: {
    dir: 'dist',
    format: 'cjs',
    entryFileNames: 'index.cjs'
  },
  external: [],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname
    }
  }
});
`;
};
