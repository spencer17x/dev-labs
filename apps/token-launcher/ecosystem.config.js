module.exports = {
  apps: [
    {
      name: 'token-launcher',
      script: 'main.py',
      interpreter: 'python3',
      cwd: './',
      env: {
        NODE_ENV: 'production',
      },
      error_file: './logs/error.log',
      out_file: './logs/out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      restart_delay: 5000,
      max_restarts: 10,
    },
  ],
};
