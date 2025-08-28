module.exports = {
  apps: [
    {
      name: 'LibreChat',
      script: './api/server/index.js',
      cwd: '/home/ec2-user/LibreChat',
      env: {
        NODE_ENV: 'production',
        HOST: '0.0.0.0',
        PORT: '3090'
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      error_file: '/home/ec2-user/logs/librechat-error.log',
      out_file: '/home/ec2-user/logs/librechat-out.log',
      log_file: '/home/ec2-user/logs/librechat-combined.log',
      time: true,
      merge_logs: true,
      restart_delay: 5000,
      min_uptime: 10000,
      max_restarts: 10
    },
    {
      name: 'IntraNest-Backend',
      script: '/home/ec2-user/IntraNest2.0/backend/venv/bin/python',
      args: 'main.py',
      cwd: '/home/ec2-user/IntraNest2.0/backend',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        PORT: '8001'
      },
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      error_file: '/home/ec2-user/logs/intranest-error.log',
      out_file: '/home/ec2-user/logs/intranest-out.log',
      log_file: '/home/ec2-user/logs/intranest-combined.log',
      time: true,
      merge_logs: true,
      restart_delay: 5000,
      min_uptime: 10000,
      max_restarts: 10
    }
  ]
}
