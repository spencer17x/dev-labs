module.exports = {
  apps: [
    {
      name: 'trending-alert-bsc',
      cwd: __dirname,
      script: 'run.py',
      interpreter: 'python3',
      args: 'run bsc',
    },
    {
      name: 'trending-alert-sol',
      cwd: __dirname,
      script: 'run.py',
      interpreter: 'python3',
      args: 'run sol',
    },
    {
      name: 'trending-alert-base',
      cwd: __dirname,
      script: 'run.py',
      interpreter: 'python3',
      args: 'run base',
    },
    {
      name: 'trending-alert-multi',
      cwd: __dirname,
      script: 'run.py',
      interpreter: 'python3',
      args: 'run multi',
    },
  ],
};
