#!/bin/bash

# Log file
LOG_FILE="/home/ec2-user/logs/startup.log"

# Wait for Docker to be ready
sleep 30

echo "[$(date)] Starting startup checks..." >> $LOG_FILE

# Start Weaviate if not running
if docker ps -a | grep -q "intranest-weaviate"; then
    if ! docker ps | grep -q "intranest-weaviate"; then
        echo "[$(date)] Starting Weaviate container..." >> $LOG_FILE
        docker start intranest-weaviate
        sleep 10
        
        # Restart IntraNest Backend to ensure connection
        echo "[$(date)] Restarting IntraNest Backend..." >> $LOG_FILE
        pm2 restart IntraNest-Backend
    else
        echo "[$(date)] Weaviate already running" >> $LOG_FILE
    fi
fi

# Log the final status
echo "[$(date)] Startup check completed" >> $LOG_FILE
docker ps --format "table {{.Names}}\t{{.Status}}" | grep weaviate >> $LOG_FILE 2>&1
echo "---" >> $LOG_FILE
