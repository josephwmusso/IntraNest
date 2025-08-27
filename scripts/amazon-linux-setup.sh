#!/bin/bash

# Amazon Linux 2023 Setup Script for LibreChat
# Run this after copying LibreChat to fix missing services

echo "================================================"
echo "Setting up LibreChat on Amazon Linux 2023"
echo "================================================"

# 1. Install missing dependencies for Amazon Linux
echo "📦 Installing Amazon Linux dependencies..."
sudo yum update -y
sudo yum install -y git nginx redis6 gcc-c++ make

# 2. Install MongoDB for Amazon Linux
echo "📦 Installing MongoDB..."
cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/amazon/2023/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-7.0.asc
EOF

sudo yum install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod

# 3. Start Redis
echo "🔄 Starting Redis..."
sudo systemctl start redis6
sudo systemctl enable redis6

# 4. Configure Nginx for Amazon Linux
echo "📝 Configuring Nginx..."
sudo tee /etc/nginx/conf.d/librechat.conf << 'EOF'
server {
    listen 80;
    listen 3090;
    server_name 54.71.15.44;
    client_max_body_size 100M;

    # Main LibreChat proxy
    location / {
        proxy_pass http://127.0.0.1:3090;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for SSE
        proxy_buffering off;
        proxy_cache off;
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # Static assets
    location /assets {
        alias /home/ec2-user/LibreChat/client/public/assets;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# 5. Test and restart Nginx
sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx

# 6. Setup PM2 auto-start
echo "📦 Setting up PM2 auto-start..."
sudo env PATH=$PATH:/home/ec2-user/.nvm/versions/node/v20.19.4/bin pm2 startup systemd -u ec2-user --hp /home/ec2-user

# 7. Configure firewall (using firewalld on Amazon Linux)
echo "🔥 Configuring firewall..."
sudo systemctl start firewalld
sudo systemctl enable firewalld
sudo firewall-cmd --permanent --add-port=22/tcp
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=3090/tcp
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --reload

# 8. Fix .env file (the error we saw)
echo "📝 Fixing .env configuration..."
cd /home/ec2-user/LibreChat
if [ -f ".env" ]; then
    # Remove any problematic lines and ensure proper format
    sed -i '/^AI:/d' .env
    
    # Update domain references
    sed -i 's|DOMAIN_CLIENT=.*|DOMAIN_CLIENT=http://54.71.15.44:3090|g' .env
    sed -i 's|DOMAIN_SERVER=.*|DOMAIN_SERVER=http://54.71.15.44:3090|g' .env
    sed -i 's|HOST=.*|HOST=0.0.0.0|g' .env
fi

# 9. Build frontend if needed
if [ ! -d "client/dist" ] && [ ! -d "client/public/dist" ]; then
    echo "🔨 Building frontend..."
    npm run frontend:dev
fi

# 10. Restart LibreChat
echo "🔄 Restarting LibreChat..."
pm2 restart LibreChat

# 11. Check AWS Security Group reminder
echo ""
echo "================================================"
echo "✅ Amazon Linux Setup Complete!"
echo "================================================"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Check AWS Security Groups in EC2 Console:"
echo "   - Allow inbound TCP 3090 from 0.0.0.0/0"
echo "   - Allow inbound TCP 8001 from 0.0.0.0/0"
echo "   - Allow inbound TCP 80 from 0.0.0.0/0"
echo ""
echo "2. Test LibreChat:"
echo "   curl -I http://localhost:3090"
echo "   curl -I http://54.71.15.44:3090"
echo ""
echo "3. Check services:"
echo "   pm2 status"
echo "   pm2 logs LibreChat --lines 50"
echo "   sudo systemctl status nginx"
echo "   sudo systemctl status mongod"
echo "   sudo systemctl status redis6"
echo ""
echo "4. If LibreChat isn't accessible externally,"
echo "   check Security Groups in AWS Console!"
echo ""
echo "================================================"
