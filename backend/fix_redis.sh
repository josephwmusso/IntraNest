#!/bin/bash
# fix_redis.sh - Quick fix for Redis setup

echo "🔧 Adding Redis to Docker setup..."

cd /home/ec2-user/IntraNest2.0/infrastructure/docker/document-management

# Stop existing services
docker-compose down

# Update docker-compose.yml to include Redis
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # MinIO - S3-compatible object storage
  minio:
    image: minio/minio:latest
    container_name: intranest-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: intranest
      MINIO_ROOT_PASSWORD: intranest123
      MINIO_BROWSER_REDIRECT_URL: http://localhost:9001
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    networks:
      - intranest-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  # MinIO Client - for bucket creation
  minio-setup:
    image: minio/mc:latest
    container_name: intranest-minio-setup
    depends_on:
      - minio
    networks:
      - intranest-network
    entrypoint: >
      /bin/sh -c "
      sleep 10;
      /usr/bin/mc alias set intranest http://minio:9000 intranest intranest123;
      /usr/bin/mc mb intranest/intranest-documents --ignore-existing;
      /usr/bin/mc policy set public intranest/intranest-documents;
      echo 'MinIO setup completed successfully';
      "

  # Redis - Cache and message broker
  redis:
    image: redis:7-alpine
    container_name: intranest-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    networks:
      - intranest-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  intranest-network:
    driver: bridge

volumes:
  minio_data:
    driver: local
  redis_data:
    driver: local
EOF

echo "✅ Updated docker-compose.yml with Redis"

# Start services
echo "🚀 Starting all services..."
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services to start..."
sleep 15

# Test connections
echo "🧪 Testing connections..."

# Test MinIO
if curl -f http://localhost:9000/minio/health/live &>/dev/null; then
    echo "✅ MinIO is healthy"
else
    echo "❌ MinIO connection failed"
fi

# Test Redis
if docker run --rm --network document-management_intranest-network redis:7-alpine redis-cli -h redis ping | grep -q PONG; then
    echo "✅ Redis is healthy"
else
    echo "❌ Redis connection failed"
fi

echo "🎉 Docker services are ready!"
echo ""
echo "Services running:"
echo "  • MinIO Console: http://localhost:9001"
echo "  • MinIO API: http://localhost:9000" 
echo "  • Redis: localhost:6379"
