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
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env_file: '.env',
      error_file: './logs/multi-err.log',
      out_file: './logs/multi-out.log',
      log_file: './logs/multi-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
      kill_timeout: 5000,
    },
  ],
};
