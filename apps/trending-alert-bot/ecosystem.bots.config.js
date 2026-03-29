const path = require('path');

const python = process.env.PYTHON || path.join(__dirname, '.venv', 'bin', 'python');

module.exports = {
  apps: [
    {
      name: 'trending-alert-bsc',
      cwd: __dirname,
      script: 'run.py',
      interpreter: python,
      args: 'run bsc',
    },
    {
      name: 'trending-alert-sol',
      cwd: __dirname,
      script: 'run.py',
      interpreter: python,
      args: 'run sol',
    },
    {
      name: 'trending-alert-base',
      cwd: __dirname,
      script: 'run.py',
      interpreter: python,
      args: 'run base',
    },
  ],
};
