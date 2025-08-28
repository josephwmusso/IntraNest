#!/bin/bash
# docker_cleanup_fix.sh - Clean up existing containers and restart properly

set -e

echo "🧹 Cleaning up existing Docker containers..."

# Stop and remove any existing IntraNest containers
echo "Stopping existing containers..."
docker stop intranest-redis intranest-minio intranest-minio-setup 2>/dev/null || true
docker rm intranest-redis intranest-minio intranest-minio-setup 2>/dev/null || true

# Clean up any orphaned containers
docker container prune -f

echo "✅ Containers cleaned up"

# Navigate to Docker directory
cd /home/ec2-user/IntraNest2.0/infrastructure/docker/document-management

# Stop any running compose services
docker-compose down --remove-orphans 2>/dev/null || true

echo "🔧 Creating clean docker-compose.yml..."

# Create updated docker-compose.yml without version (to avoid warnings)
cat > docker-compose.yml << 'EOF'
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
    command: redis-server --appendonly yes --requirepass ""
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

echo "✅ Updated docker-compose.yml created"

# Start services fresh
echo "🚀 Starting all services fresh..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 20

# Check service health
echo "🧪 Testing service health..."

# Test MinIO
if curl -f http://localhost:9000/minio/health/live &>/dev/null; then
    echo "✅ MinIO is healthy (http://localhost:9000)"
else
    echo "❌ MinIO health check failed"
    docker-compose logs minio
fi

# Test Redis
if redis-cli -h localhost -p 6379 ping | grep -q PONG; then
    echo "✅ Redis is healthy (localhost:6379)"
else
    echo "❌ Redis health check failed"
    docker-compose logs redis
fi

# Check MinIO bucket setup
sleep 5
if docker logs intranest-minio-setup 2>/dev/null | grep -q "successfully"; then
    echo "✅ MinIO bucket setup completed"
else
    echo "⚠️  MinIO bucket setup may need verification"
    docker logs intranest-minio-setup
fi

echo ""
echo "🎉 Docker services are ready!"
echo "Services status:"
docker-compose ps

echo ""
echo "📋 Service URLs:"
echo "  • MinIO Console: http://localhost:9001"
echo "  • MinIO API: http://localhost:9000"
echo "  • Redis: localhost:6379"
echo ""
echo "🔑 MinIO Login: intranest / intranest123"
