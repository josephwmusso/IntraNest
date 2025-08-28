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
