module.exports = {
  apps: [
    {
      name: 'telegram-forwarder',
      script: 'main.py',
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env_file: '.env',
      error_file: './logs/err.log',
      out_file: './logs/out.log',
      log_file: './logs/combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      // 重启策略
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
      // 监听异常退出
      listen_timeout: 3000,
      kill_timeout: 5000,
      wait_ready: false,
    },
  ],
};
