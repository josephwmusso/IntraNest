#!/bin/bash

# Run this on your AWS EC2 instance after copying LibreChat
# This sets up all the necessary services and configurations

echo "================================================"
echo "Setting up LibreChat on AWS EC2"
echo "================================================"

# 1. Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y curl git build-essential nginx python3-pip redis-server

# 2. Install Node.js 20 if not present
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi

# 3. Install MongoDB if not present
if ! command -v mongod &> /dev/null; then
    echo "📦 Installing MongoDB..."
    curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
       sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg \
       --dearmor
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
       sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    sudo apt update
    sudo apt install -y mongodb-org
    sudo systemctl start mongod
    sudo systemctl enable mongod
fi

# 4. Start Redis (for session management)
echo "🔄 Starting Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 5. Navigate to LibreChat directory
cd /home/ec2-user/LibreChat

# 6. Install Node dependencies
echo "📦 Installing LibreChat dependencies..."
npm ci

# 7. Build frontend if needed
if [ ! -d "client/dist" ]; then
    echo "🔨 Building frontend..."
    npm run frontend:dev
fi

# 8. Update environment configuration
echo "📝 Updating environment configuration..."
cat > .env.production << 'EOF'
#===============================================================================
# LibreChat AWS Production Configuration
#===============================================================================

HOST=0.0.0.0
PORT=3090
MONGO_URI=mongodb://localhost:27017/LibreChat
DOMAIN_CLIENT=http://54.71.15.44:3090
DOMAIN_SERVER=http://54.71.15.44:3090

# Redis for session management
REDIS_URI=redis://localhost:6379

# Session Settings
SESSION_EXPIRY=604800000
REFRESH_TOKEN_EXPIRY=2592000000

# Your existing keys (update these!)
CREDS_KEY=${CREDS_KEY}
CREDS_IV=${CREDS_IV}
JWT_SECRET=${JWT_SECRET}
JWT_REFRESH_SECRET=${JWT_REFRESH_SECRET}

# IntraNest Integration
INTRANEST_API_KEY=${INTRANEST_API_KEY}

# Microsoft OAuth
MICROSOFT_CLIENT_ID=${MICROSOFT_CLIENT_ID}
MICROSOFT_CLIENT_SECRET=${MICROSOFT_CLIENT_SECRET}
MICROSOFT_CALLBACK_URL=http://54.71.15.44:3090/oauth/microsoft/callback

# OpenAI (for conversational features)
OPENAI_API_KEY=${OPENAI_API_KEY}

# Registration
ALLOW_REGISTRATION=false
ALLOW_SOCIAL_LOGIN=true
ALLOW_SOCIAL_REGISTRATION=true

# Logging
DEBUG_LOGGING=true
EOF

# Copy existing .env values if they exist
if [ -f ".env" ]; then
    echo "📋 Migrating existing .env values..."
    # Extract and replace placeholder values
    source .env
    sed -i "s/\${CREDS_KEY}/$CREDS_KEY/g" .env.production
    sed -i "s/\${CREDS_IV}/$CREDS_IV/g" .env.production
    sed -i "s/\${JWT_SECRET}/$JWT_SECRET/g" .env.production
    sed -i "s/\${JWT_REFRESH_SECRET}/$JWT_REFRESH_SECRET/g" .env.production
    sed -i "s/\${INTRANEST_API_KEY}/$INTRANEST_API_KEY/g" .env.production
    sed -i "s/\${MICROSOFT_CLIENT_ID}/$MICROSOFT_CLIENT_ID/g" .env.production
    sed -i "s/\${MICROSOFT_CLIENT_SECRET}/$MICROSOFT_CLIENT_SECRET/g" .env.production
    sed -i "s/\${OPENAI_API_KEY}/$OPENAI_API_KEY/g" .env.production
    
    # Use production env
    mv .env .env.backup
    mv .env.production .env
fi

# 9. Install PM2 for process management
echo "📦 Installing PM2..."
sudo npm install -g pm2

# 10. Create PM2 ecosystem file
echo "📝 Creating PM2 configuration..."
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'LibreChat',
      script: 'api/server/index.js',
      cwd: '/home/ec2-user/LibreChat',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        NODE_ENV: 'production',
        HOST: '0.0.0.0',
        PORT: 3090
      },
      error_file: 'logs/err.log',
      out_file: 'logs/out.log',
      log_file: 'logs/combined.log',
      time: true
    }
  ]
};
EOF

# 11. Setup Nginx
echo "📝 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/librechat << 'EOF'
server {
    listen 80;
    listen 3090;
    server_name 54.71.15.44;
    client_max_body_size 100M;

    # Main LibreChat proxy
    location / {
        proxy_pass http://localhost:3090;
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

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/librechat /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 12. Create logs directory
mkdir -p logs

# 13. Start LibreChat with PM2
echo "🚀 Starting LibreChat..."
pm2 delete LibreChat 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save
pm2 startup systemd -u ec2-user --hp /home/ec2-user

# 14. Setup firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 3090/tcp
sudo ufw allow 8001/tcp
sudo ufw --force enable

echo "================================================"
echo "✅ LibreChat Setup Complete!"
echo "================================================"
echo ""
echo "Access LibreChat at: http://54.71.15.44:3090"
echo ""
echo "📊 Monitor with:"
echo "  pm2 status"
echo "  pm2 logs LibreChat"
echo "  pm2 monit"
echo ""
echo "🔄 Restart with:"
echo "  pm2 restart LibreChat"
echo ""
echo "⚠️  Important: Make sure your AWS Security Group allows:"
echo "  - Port 3090 (LibreChat)"
echo "  - Port 8001 (IntraNest Backend)"
