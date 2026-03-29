const path = require('path');

const python = process.env.PYTHON || path.join(__dirname, '.venv', 'bin', 'python');

module.exports = {
  apps: [
    {
      name: 'trending-alert-multi',
      cwd: __dirname,
      script: 'run.py',
      interpreter: python,
      args: 'run multi',
    },
  ],
};
