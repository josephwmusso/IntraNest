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

# Check Weaviate container
if docker ps -a | grep -q "intranest-weaviate"; then
    if ! docker ps | grep -q "intranest-weaviate"; then
        log_message "Weaviate container is stopped. Starting..."
        docker start intranest-weaviate
        sleep 5
        if docker ps | grep -q "intranest-weaviate"; then
            log_message "Weaviate container started successfully"
            # Restart IntraNest Backend to reconnect
            pm2 restart IntraNest-Backend
        else
            send_alert "Failed to start Weaviate container"
        fi
    else
        log_message "Weaviate container is running"
    fi
fi
