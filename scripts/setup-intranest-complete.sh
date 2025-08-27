
# Paste the entire script content from above
# Save with Ctrl+X, then Y, then Enter#!/bin/bash

# IntraNest AI Complete Setup Script
# This script sets up both LibreChat and IntraNest Backend with PM2
# and configures automatic monitoring and restart capabilities

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[i]${NC} $1"
}

echo "========================================="
echo "   IntraNest AI Complete Setup Script"
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

# Step 1: Create logs directory
print_info "Creating logs directory..."
mkdir -p /home/ec2-user/logs
print_status "Logs directory created"

# Step 2: Check and install Python dependencies for IntraNest
print_info "Checking IntraNest Backend dependencies..."
if [ -d "/home/ec2-user/IntraNest2.0/backend" ]; then
    cd /home/ec2-user/IntraNest2.0/backend
    if [ -f "venv/bin/python" ]; then
        print_status "Virtual environment found"
        source venv/bin/activate
        pip install -r requirements.txt --quiet
        deactivate
        print_status "Dependencies updated"
    else
        print_error "Virtual environment not found. Creating..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
        deactivate
        print_status "Virtual environment created and dependencies installed"
    fi
else
    print_error "IntraNest2.0 backend directory not found!"
    exit 1
fi

# Step 3: Create combined PM2 ecosystem configuration
print_info "Creating PM2 ecosystem configuration..."
cat > /home/ec2-user/ecosystem.config.js << 'EOF'
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
EOF
print_status "PM2 ecosystem configuration created"

# Step 4: Stop and restart PM2 processes
print_info "Configuring PM2 processes..."
pm2 stop all 2>/dev/null || true
pm2 delete all 2>/dev/null || true
pm2 start /home/ec2-user/ecosystem.config.js
pm2 save
print_status "PM2 processes started"

# Step 5: Setup PM2 startup script
print_info "Configuring PM2 startup..."
PM2_STARTUP_CMD=$(pm2 startup systemd -u ec2-user --hp /home/ec2-user | grep sudo | tail -n 1)
if [ ! -z "$PM2_STARTUP_CMD" ]; then
    eval $PM2_STARTUP_CMD
    print_status "PM2 startup configured"
else
    print_info "PM2 startup may already be configured"
fi

# Step 6: Create monitoring script
print_info "Creating monitoring script..."
cat > /home/ec2-user/monitor-services.sh << 'MONITOR_EOF'
#!/bin/bash

# IntraNest AI Service Monitor
LOG_FILE="/home/ec2-user/logs/monitor.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log_message() {
    echo "[$TIMESTAMP] $1" >> $LOG_FILE
}

send_alert() {
    echo "[$TIMESTAMP] ALERT: $1" >> $LOG_FILE
}

# Check MongoDB
if ! systemctl is-active --quiet mongod; then
    log_message "MongoDB is down. Attempting to restart..."
    sudo systemctl start mongod
    sleep 5
    if systemctl is-active --quiet mongod; then
        log_message "MongoDB restarted successfully"
    else
        send_alert "Failed to restart MongoDB"
    fi
else
    log_message "MongoDB is running"
fi

# Check Redis
if ! systemctl is-active --quiet redis6; then
    log_message "Redis is down. Attempting to restart..."
    sudo systemctl start redis6
    sleep 5
    if systemctl is-active --quiet redis6; then
        log_message "Redis restarted successfully"
    else
        send_alert "Failed to restart Redis"
    fi
else
    log_message "Redis is running"
fi

# Check Nginx
if ! systemctl is-active --quiet nginx; then
    log_message "Nginx is down. Attempting to restart..."
    sudo systemctl restart nginx
    sleep 5
    if systemctl is-active --quiet nginx; then
        log_message "Nginx restarted successfully"
    else
        send_alert "Failed to restart Nginx"
    fi
else
    log_message "Nginx is running"
fi

# Check PM2 processes
PM2_STATUS=$(pm2 jlist 2>/dev/null)
if [ -z "$PM2_STATUS" ] || [ "$PM2_STATUS" == "[]" ]; then
    log_message "PM2 processes not running. Attempting to resurrect..."
    pm2 resurrect
    sleep 10
else
    # Check LibreChat
    if ! pm2 list | grep -q "LibreChat.*online"; then
        log_message "LibreChat is not running. Attempting to restart..."
        pm2 restart LibreChat || pm2 start /home/ec2-user/ecosystem.config.js
        sleep 10
    else
        log_message "LibreChat is running"
    fi
    
    # Check IntraNest Backend
    if ! pm2 list | grep -q "IntraNest-Backend.*online"; then
        log_message "IntraNest Backend is not running. Attempting to restart..."
        pm2 restart IntraNest-Backend || pm2 start /home/ec2-user/ecosystem.config.js
        sleep 10
    else
        log_message "IntraNest Backend is running"
    fi
fi

# Check LibreChat endpoint
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:3090 | grep -q "200\|301\|302"; then
    log_message "LibreChat not responding on port 3090. Attempting restart..."
    pm2 restart LibreChat
    sleep 10
fi

# Check IntraNest Backend endpoint
if ! curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/health | grep -q "200"; then
    log_message "IntraNest Backend not responding on port 8001. Attempting restart..."
    pm2 restart IntraNest-Backend
    sleep 10
fi

# Check HTTPS endpoint
if ! curl -s -o /dev/null -w "%{http_code}" https://app.intranestai.com | grep -q "200\|301\|302"; then
    send_alert "HTTPS endpoint (app.intranestai.com) is not responding"
fi

# Clean up old logs
tail -n 1000 $LOG_FILE > $LOG_FILE.tmp && mv $LOG_FILE.tmp $LOG_FILE

log_message "Health check completed"
MONITOR_EOF

chmod +x /home/ec2-user/monitor-services.sh
print_status "Monitoring script created"

# Step 7: Create health check script
print_info "Creating health check script..."
cat > /home/ec2-user/health-check.sh << 'HEALTH_EOF'
#!/bin/bash

echo "========================================="
echo "   IntraNest AI System Health Check"
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

check_service() {
    if systemctl is-active --quiet $1; then
        echo "✅ $2 is running"
    else
        echo "❌ $2 is down"
    fi
}

echo "📊 System Services:"
check_service "mongod" "MongoDB"
check_service "redis6" "Redis"
check_service "nginx" "Nginx"
echo ""

echo "📦 PM2 Processes:"
pm2 list
echo ""

echo "🔌 Port Status:"
for port in 3090 8001 80 443; do
    if netstat -tuln | grep -q ":$port "; then
        case $port in
            3090) echo "✅ Port 3090 (LibreChat) is listening" ;;
            8001) echo "✅ Port 8001 (IntraNest Backend) is listening" ;;
            80)   echo "✅ Port 80 (HTTP) is listening" ;;
            443)  echo "✅ Port 443 (HTTPS) is listening" ;;
        esac
    else
        case $port in
            3090) echo "❌ Port 3090 (LibreChat) is NOT listening" ;;
            8001) echo "❌ Port 8001 (IntraNest Backend) is NOT listening" ;;
            80)   echo "❌ Port 80 (HTTP) is NOT listening" ;;
            443)  echo "❌ Port 443 (HTTPS) is NOT listening" ;;
        esac
    fi
done
echo ""

echo "💾 Disk Usage:"
df -h / | tail -1 | awk '{print "   Used: "$3" / "$2" ("$5")"}'
echo ""

echo "🧠 Memory Usage:"
free -h | grep Mem | awk '{print "   Used: "$3" / "$2}'
echo ""

echo "⚡ CPU Load:"
uptime | awk -F'load average:' '{print "   Load Average:"$2}'
echo ""

echo "🌐 Endpoint Status:"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3090 | grep -q "200\|301\|302"; then
    echo "✅ LibreChat (localhost:3090) is responding"
else
    echo "❌ LibreChat (localhost:3090) is not responding"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/health | grep -q "200"; then
    echo "✅ IntraNest Backend (localhost:8001) is responding"
else
    echo "❌ IntraNest Backend (localhost:8001) is not responding"
fi

if curl -s -o /dev/null -w "%{http_code}" https://app.intranestai.com | grep -q "200\|301\|302"; then
    echo "✅ HTTPS (app.intranestai.com) is responding"
else
    echo "❌ HTTPS (app.intranestai.com) is not responding"
fi
echo ""

echo "🔒 SSL Certificate:"
echo | openssl s_client -servername app.intranestai.com -connect app.intranestai.com:443 2>/dev/null | openssl x509 -noout -dates 2>/dev/null | grep notAfter | sed 's/notAfter=/   Expires: /'
echo ""

echo "========================================="
echo "   Health Check Complete"
echo "========================================="
HEALTH_EOF

chmod +x /home/ec2-user/health-check.sh
print_status "Health check script created"

# Step 8: Configure crontab
print_info "Configuring crontab..."
(crontab -l 2>/dev/null | grep -v "monitor-services.sh" | grep -v "pm2 restart all"; echo "*/5 * * * * /home/ec2-user/monitor-services.sh"; echo "0 3 * * * /usr/bin/pm2 restart all") | crontab -
print_status "Crontab configured"

# Step 9: Ensure system services are enabled
print_info "Enabling system services..."
sudo systemctl enable mongod 2>/dev/null || print_info "MongoDB already enabled"
sudo systemctl enable redis6 2>/dev/null || print_info "Redis already enabled"
sudo systemctl enable nginx 2>/dev/null || print_info "Nginx already enabled"
print_status "System services enabled"

# Step 10: Create quick commands reference
print_info "Creating quick commands reference..."
cat > /home/ec2-user/quick-commands.txt << 'QUICK_EOF'
IntraNest AI - Quick Management Commands
=========================================

SERVICE MANAGEMENT:
-------------------
pm2 restart all                    # Restart both services
pm2 restart LibreChat              # Restart only LibreChat
pm2 restart IntraNest-Backend      # Restart only IntraNest
pm2 logs                           # View all logs
pm2 logs LibreChat --lines 50     # View LibreChat logs
pm2 logs IntraNest-Backend        # View IntraNest logs
pm2 monit                          # Real-time monitoring

HEALTH CHECKS:
--------------
./health-check.sh                  # Run full health check
pm2 status                         # Check PM2 status
curl http://localhost:8001/api/health  # Test IntraNest
curl http://localhost:3090         # Test LibreChat

TROUBLESHOOTING:
----------------
pm2 delete all && pm2 start /home/ec2-user/ecosystem.config.js
pm2 save
tail -f /home/ec2-user/logs/monitor.log
sudo systemctl restart nginx
sudo systemctl restart mongod
sudo systemctl restart redis6

MAINTENANCE:
------------
pm2 flush                          # Clear PM2 logs
df -h                              # Check disk space
free -h                            # Check memory
QUICK_EOF
print_status "Quick commands reference created"

# Step 11: Wait for services to start
print_info "Waiting for services to start..."
sleep 10

# Step 12: Test services
echo ""
echo "========================================="
echo "   Testing Services"
echo "========================================="

# Test LibreChat
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3090 | grep -q "200\|301\|302"; then
    print_status "LibreChat is responding on port 3090"
else
    print_error "LibreChat is NOT responding on port 3090"
fi

# Test IntraNest Backend
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/health | grep -q "200"; then
    print_status "IntraNest Backend is responding on port 8001"
else
    print_error "IntraNest Backend is NOT responding on port 8001"
fi

# Test HTTPS
if curl -s -o /dev/null -w "%{http_code}" https://app.intranestai.com | grep -q "200\|301\|302"; then
    print_status "HTTPS endpoint is responding"
else
    print_error "HTTPS endpoint is NOT responding"
fi

# Final status
echo ""
echo "========================================="
echo "   Setup Complete!"
echo "========================================="
echo ""
print_info "Quick commands saved to: ~/quick-commands.txt"
print_info "Health check script: ./health-check.sh"
print_info "Monitor logs: tail -f ~/logs/monitor.log"
print_info "PM2 status: pm2 status"
echo ""
print_status "IntraNest AI is configured for 24/7 operation!"
echo ""

# Show current PM2 status
pm2 status
