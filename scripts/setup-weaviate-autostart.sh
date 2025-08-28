#!/bin/bash

# IntraNest AI - Weaviate Auto-Start Setup Script
# This script configures Weaviate to start automatically without manual crontab editing

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
echo "   Weaviate Auto-Start Configuration"
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

# Step 1: Update monitoring script to include Weaviate
print_info "Updating monitoring script..."

# Check if Weaviate monitoring already exists in the script
if ! grep -q "Check Weaviate container" /home/ec2-user/monitor-services.sh 2>/dev/null; then
    cat >> /home/ec2-user/monitor-services.sh << 'MONITOR_EOF'

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
MONITOR_EOF
    print_status "Weaviate monitoring added to monitor-services.sh"
else
    print_info "Weaviate monitoring already exists in monitor-services.sh"
fi

# Step 2: Create systemd service for Weaviate
print_info "Creating systemd service for Weaviate..."

sudo tee /etc/systemd/system/weaviate-docker.service > /dev/null << 'SYSTEMD_EOF'
[Unit]
Description=Weaviate Docker Container
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker start intranest-weaviate
ExecStop=/usr/bin/docker stop intranest-weaviate
User=ec2-user
Group=docker
StandardOutput=journal

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable weaviate-docker.service 2>/dev/null || print_info "Service already enabled"
sudo systemctl start weaviate-docker.service 2>/dev/null || print_info "Service already started"
print_status "Systemd service created and enabled"

# Step 3: Update Docker container restart policy (most reliable method)
print_info "Setting Docker container restart policy..."

if docker ps -a | grep -q "intranest-weaviate"; then
    docker update --restart unless-stopped intranest-weaviate > /dev/null 2>&1
    print_status "Docker restart policy set to 'unless-stopped'"
else
    print_error "Weaviate container not found"
fi

# Step 4: Create startup check script
print_info "Creating startup check script..."

cat > /home/ec2-user/startup-check.sh << 'STARTUP_EOF'
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
STARTUP_EOF

chmod +x /home/ec2-user/startup-check.sh
print_status "Startup check script created"

# Step 5: Update crontab programmatically (no manual editing required)
print_info "Updating crontab entries..."

# Save current crontab
crontab -l 2>/dev/null > /tmp/current_cron || true

# Check if our entries already exist
NEEDS_UPDATE=false

if ! grep -q "monitor-services.sh" /tmp/current_cron 2>/dev/null; then
    echo "*/5 * * * * /home/ec2-user/monitor-services.sh" >> /tmp/current_cron
    NEEDS_UPDATE=true
fi

if ! grep -q "pm2 restart all" /tmp/current_cron 2>/dev/null; then
    echo "0 3 * * * /usr/bin/pm2 restart all" >> /tmp/current_cron
    NEEDS_UPDATE=true
fi

if ! grep -q "startup-check.sh" /tmp/current_cron 2>/dev/null; then
    echo "@reboot /home/ec2-user/startup-check.sh" >> /tmp/current_cron
    NEEDS_UPDATE=true
fi

if [ "$NEEDS_UPDATE" = true ]; then
    # Install the new crontab
    crontab /tmp/current_cron
    print_status "Crontab updated successfully"
else
    print_info "Crontab already configured"
fi

# Clean up
rm -f /tmp/current_cron

# Step 6: Test Weaviate connection
print_info "Testing Weaviate..."

# Start Weaviate if not running
if ! docker ps | grep -q "intranest-weaviate"; then
    print_info "Starting Weaviate container..."
    docker start intranest-weaviate
    sleep 5
fi

# Check if Weaviate is responding
if docker ps | grep -q "intranest-weaviate"; then
    print_status "Weaviate container is running"
    
    # Test Weaviate endpoint
    if curl -s http://localhost:8080/v1/.well-known/ready 2>/dev/null | grep -q "true"; then
        print_status "Weaviate is responding on port 8080"
    else
        print_info "Weaviate is starting up, may take a moment to be ready"
    fi
else
    print_error "Weaviate container failed to start"
fi

# Step 7: Restart IntraNest Backend to ensure connection
print_info "Restarting IntraNest Backend to ensure Weaviate connection..."
pm2 restart IntraNest-Backend > /dev/null 2>&1
sleep 3
print_status "IntraNest Backend restarted"

# Step 8: Final verification
echo ""
echo "========================================="
echo "   Configuration Summary"
echo "========================================="

echo ""
echo "📋 Auto-Start Methods Configured:"
echo "──────────────────────────────────"

# Check Docker restart policy
RESTART_POLICY=$(docker inspect intranest-weaviate 2>/dev/null | grep -A 1 '"RestartPolicy"' | grep '"Name"' | cut -d'"' -f4)
if [ "$RESTART_POLICY" = "unless-stopped" ]; then
    echo "✅ Docker restart policy: unless-stopped"
else
    echo "⚠️  Docker restart policy: $RESTART_POLICY"
fi

# Check systemd service
if sudo systemctl is-enabled weaviate-docker.service > /dev/null 2>&1; then
    echo "✅ Systemd service: enabled"
else
    echo "⚠️  Systemd service: not enabled"
fi

# Check crontab
if crontab -l 2>/dev/null | grep -q "monitor-services.sh"; then
    echo "✅ Monitoring cron: configured (every 5 minutes)"
else
    echo "⚠️  Monitoring cron: not configured"
fi

if crontab -l 2>/dev/null | grep -q "startup-check.sh"; then
    echo "✅ Startup check: configured (@reboot)"
else
    echo "⚠️  Startup check: not configured"
fi

# Check current status
echo ""
echo "📊 Current Status:"
echo "──────────────────"

# PM2 services
PM2_STATUS=$(pm2 list --no-color 2>/dev/null)
if echo "$PM2_STATUS" | grep -q "LibreChat.*online"; then
    echo "✅ LibreChat: running"
else
    echo "❌ LibreChat: not running"
fi

if echo "$PM2_STATUS" | grep -q "IntraNest-Backend.*online"; then
    echo "✅ IntraNest Backend: running"
else
    echo "❌ IntraNest Backend: not running"
fi

# Weaviate
if docker ps | grep -q "intranest-weaviate"; then
    echo "✅ Weaviate: running"
else
    echo "❌ Weaviate: not running"
fi

# Test IntraNest health
if curl -s http://localhost:8001/api/health 2>/dev/null | grep -q '"weaviate":"operational"'; then
    echo "✅ Weaviate connection: operational"
else
    echo "⚠️  Weaviate connection: not operational"
fi

echo ""
echo "========================================="
echo "   Setup Complete!"
echo "========================================="
echo ""
print_status "Weaviate is now configured for automatic startup"
print_status "The system will monitor and restart services automatically"
echo ""
echo "Useful commands:"
echo "  docker ps | grep weaviate        # Check Weaviate status"
echo "  pm2 status                       # Check all PM2 services"
echo "  ./monitor-services.sh            # Run monitoring manually"
echo "  crontab -l                       # View all cron jobs"
echo "  sudo systemctl status weaviate-docker  # Check systemd service"
echo ""
