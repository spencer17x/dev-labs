// 验证项目名称
export const validateProjectName = (name: string): boolean => {
  return /^[a-z0-9-]+$/.test(name);
};
