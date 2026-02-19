module.exports = {
  apps: [
    {
      name: 'trending-alert-bsc',
      cwd: __dirname,
      script: 'run.py',
      interpreter: 'python3',
      args: 'start bsc',
    },
    {
      name: 'trending-alert-sol',
      cwd: __dirname,
      script: 'run.py',
      interpreter: 'python3',
      args: 'start sol',
    },
    {
      name: 'trending-alert-base',
      cwd: __dirname,
      script: 'run.py',
      interpreter: 'python3',
      args: 'start base',
    },
  ],
};
