#!/bin/bash
set -e

echo "🚀 Installing IntraNest 2.0..."

# Get AWS region
AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "us-west-2")
echo "AWS Region: $AWS_REGION"

# Function to get SSM parameter
get_ssm_param() {
    aws ssm get-parameter --region "$AWS_REGION" --name "$1" --with-decryption --query 'Parameter.Value' --output text 2>/dev/null
}

# Create project directory
mkdir -p /home/ec2-user/intranest2.0
cd /home/ec2-user/intranest2.0

# Create directory structure
mkdir -p {backend,frontend,infrastructure/{docker,kubernetes},data/{uploads,backups},logs}

# Generate secure API key for Weaviate
WEAVIATE_API_KEY=$(openssl rand -hex 32)
echo "Generated Weaviate API key: ${WEAVIATE_API_KEY:0:8}..."

# Try to get secrets from SSM
echo "Retrieving secrets from AWS SSM..."
OPENAI_KEY=$(get_ssm_param "/intranest2/openai/api_key")
MS_CLIENT_ID=$(get_ssm_param "/intranest2/microsoft/client_id")
MS_CLIENT_SECRET=$(get_ssm_param "/intranest2/microsoft/client_secret")
MS_TENANT_ID=$(get_ssm_param "/intranest2/microsoft/tenant_id")

echo "Retrieved OpenAI key: ${OPENAI_KEY:0:8}..."
echo "Retrieved MS Client ID: ${MS_CLIENT_ID:0:8}..."

# Create environment file
cat > .env << ENV
# IntraNest 2.0 Environment Configuration
APP_NAME="IntraNest 2.0"
APP_VERSION="2.0.0"
ENVIRONMENT="development"
DEBUG=true

# Weaviate Configuration
WEAVIATE_URL="http://localhost:8080"
WEAVIATE_API_KEY="$WEAVIATE_API_KEY"

# Redis Configuration
REDIS_URL="redis://localhost:6379"

# JWT Configuration
JWT_SECRET_KEY="$(openssl rand -hex 32)"
JWT_ALGORITHM="HS256"
JWT_EXPIRATION_HOURS=24

# CORS Configuration
CORS_ORIGINS="http://localhost:3000,http://54.71.15.44:3000"

# File Upload Configuration
MAX_FILE_SIZE_MB=50
ALLOWED_FILE_TYPES="pdf,docx,txt,md,html"

# Performance Configuration
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT_SECONDS=30
EMBEDDING_BATCH_SIZE=10

# API Keys from SSM
OPENAI_API_KEY="$OPENAI_KEY"
MICROSOFT_CLIENT_ID="$MS_CLIENT_ID"
MICROSOFT_CLIENT_SECRET="$MS_CLIENT_SECRET"
MICROSOFT_TENANT_ID="$MS_TENANT_ID"
ENV

echo "Created environment file"

# Create Docker Compose configuration
cat > infrastructure/docker/docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  weaviate:
    image: semitechnologies/weaviate:1.25.1
    container_name: intranest-weaviate
    restart: unless-stopped
    ports:
      - "8080:8080"
      - "50051:50051"
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      QUERY_MAXIMUM_RESULTS: 10000
      AUTHENTICATION_APIKEY_ENABLED: 'true'
      AUTHENTICATION_APIKEY_ALLOWED_KEYS: '${WEAVIATE_API_KEY}'
      AUTHENTICATION_APIKEY_USERS: 'intranest-admin'
      AUTHORIZATION_ADMINLIST_ENABLED: 'true'
      AUTHORIZATION_ADMINLIST_USERS: 'intranest-admin'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'text2vec-openai'
      ENABLE_MODULES: 'text2vec-openai,generative-openai,backup-filesystem'
      OPENAI_APIKEY: '${OPENAI_API_KEY}'
      CLUSTER_HOSTNAME: 'node1'
      LOG_LEVEL: 'info'
      LOG_FORMAT: 'json'
    volumes:
      - weaviate_data:/var/lib/weaviate
      - weaviate_backups:/var/lib/weaviate/backups
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/v1/meta"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    env_file:
      - ../../.env

  redis:
    image: redis:7-alpine
    container_name: intranest-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  weaviate_data:
    driver: local
  weaviate_backups:
    driver: local
  redis_data:
    driver: local

networks:
  default:
    name: intranest_network
COMPOSE

echo "Created Docker Compose configuration"

# Set proper permissions
chmod 600 .env

echo "✅ IntraNest 2.0 setup completed!"
echo "📋 Next steps:"
echo "  1. cd /home/ec2-user/intranest2.0"
echo "  2. sudo /usr/local/bin/docker-compose -f infrastructure/docker/docker-compose.yml up -d"
echo "  3. Check status: sudo /usr/local/bin/docker-compose -f infrastructure/docker/docker-compose.yml ps"
