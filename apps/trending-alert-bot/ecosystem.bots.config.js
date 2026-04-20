const path = require('path');

const python = process.env.PYTHON || path.join(__dirname, '.venv', 'bin', 'python');

const base = {
  cwd: __dirname,
  script: 'run.py',
  interpreter: python,
  instances: 1,
  autorestart: true,
  watch: false,
  max_memory_restart: '500M',
  env_file: '.env',
  time: true,
  merge_logs: true,
  log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
  min_uptime: '10s',
  max_restarts: 10,
  restart_delay: 4000,
  kill_timeout: 5000,
};

module.exports = {
  apps: [
    {
      ...base,
      name: 'trending-alert-bsc',
      args: 'run bsc',
      error_file: './logs/bsc-err.log',
      out_file: './logs/bsc-out.log',
      log_file: './logs/bsc-combined.log',
    },
    {
      ...base,
      name: 'trending-alert-sol',
      args: 'run sol',
      error_file: './logs/sol-err.log',
      out_file: './logs/sol-out.log',
      log_file: './logs/sol-combined.log',
    },
    {
      ...base,
      name: 'trending-alert-base',
      args: 'run base',
      error_file: './logs/base-err.log',
      out_file: './logs/base-out.log',
      log_file: './logs/base-combined.log',
    },
    {
      ...base,
      name: 'trending-alert-eth',
      args: 'run eth',
      error_file: './logs/eth-err.log',
      out_file: './logs/eth-out.log',
      log_file: './logs/eth-combined.log',
    },
  ],
};
