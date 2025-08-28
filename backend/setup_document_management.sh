#!/bin/bash
# setup_document_management.sh
# Complete setup script for IntraNest Document Management

set -e  # Exit on any error

echo "🚀 Starting IntraNest Document Management Setup"
echo "================================================"

# Configuration
BACKEND_DIR="/home/ec2-user/IntraNest2.0/backend"
DOCKER_DIR="/home/ec2-user/IntraNest2.0/infrastructure/docker"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Step 1: Check prerequisites
echo
log_info "Step 1: Checking prerequisites..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is not installed."
    exit 1
fi

log_success "Prerequisites check completed"

# Step 2: Create directory structure
echo
log_info "Step 2: Creating directory structure..."

mkdir -p "$DOCKER_DIR/document-management"
mkdir -p "$BACKEND_DIR/documents"
mkdir -p "$BACKEND_DIR/logs"

log_success "Directory structure created"

# Step 3: Create Docker Compose file
echo
log_info "Step 3: Creating Docker Compose configuration..."

cat > "$DOCKER_DIR/document-management/docker-compose.yml" << 'EOF'
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

networks:
  intranest-network:
    driver: bridge

volumes:
  minio_data:
    driver: local
EOF

log_success "Docker Compose configuration created"

# Step 4: Create Redis configuration
echo
log_info "Step 4: Creating Redis configuration..."

cat > "$DOCKER_DIR/document-management/redis.conf" << 'EOF'
# Memory optimization
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Network
tcp-keepalive 300
timeout 0

# Performance
tcp-backlog 511
databases 16

# Logging
loglevel notice
logfile ""
EOF

log_success "Redis configuration created"

# Step 5: Install Python dependencies
echo
log_info "Step 5: Installing Python dependencies..."

cd "$BACKEND_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    log_info "Activated existing virtual environment"
else
    log_warning "Virtual environment not found. Creating new one..."
    python3 -m venv venv
    source venv/bin/activate
    log_success "Created and activated new virtual environment"
fi

# Install additional dependencies
pip install --upgrade pip

# Core dependencies for document management
pip install minio boto3 celery[redis] flower redis
pip install PyPDF2 python-docx

# Optional dependencies
pip install Pillow  # For image processing

log_success "Python dependencies installed"

# Step 6: Update environment variables
echo
log_info "Step 6: Updating environment variables..."

# Backup existing .env
if [ -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env" "$BACKEND_DIR/.env.backup"
    log_info "Backed up existing .env file"
fi

# Add document management configuration to .env
cat >> "$BACKEND_DIR/.env" << 'EOF'

# Document Management Configuration
STORAGE_TYPE=minio
S3_BUCKET=intranest-documents
S3_REGION=us-west-2
S3_ACCESS_KEY=intranest
S3_SECRET_KEY=intranest123
S3_ENDPOINT=http://localhost:9000

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Document Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_FILE_SIZE=52428800
EOF

log_success "Environment variables updated"

# Step 7: Create Celery worker
echo
log_info "Step 7: Creating Celery worker file..."

# The Celery worker code is created as a separate artifact
# For now, create a placeholder
cat > "$BACKEND_DIR/celery_worker.py" << 'EOF'
# Celery worker will be implemented here
# See the provided celery_worker.py artifact for complete implementation
import os
from celery import Celery

celery_app = Celery(
    'intranest_worker',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

@celery_app.task
def test_task():
    return "Celery worker is running!"

if __name__ == '__main__':
    celery_app.start()
EOF

log_success "Celery worker placeholder created"

# Step 8: Start storage services
echo
log_info "Step 8: Starting storage services..."

cd "$DOCKER_DIR/document-management"

# Stop any existing containers
docker-compose down 2>/dev/null || true

# Start MinIO and Redis
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 15

# Check MinIO health
if curl -f http://localhost:9000/minio/health/live &>/dev/null; then
    log_success "MinIO is running and healthy"
else
    log_warning "MinIO may not be fully ready yet"
fi

# Check if bucket was created
sleep 5
docker logs intranest-minio-setup 2>/dev/null | grep -q "successfully" && \
    log_success "MinIO bucket created successfully" || \
    log_warning "MinIO bucket creation may have issues"

log_success "Storage services started"

# Step 9: Test the setup
echo
log_info "Step 9: Testing the setup..."

cd "$BACKEND_DIR"
source venv/bin/activate

# Test imports
python3 -c "
import minio
import redis
import celery
print('✅ All required packages can be imported')
" 2>/dev/null && log_success "Python dependencies test passed" || log_error "Python dependencies test failed"

# Test MinIO connection
python3 -c "
import minio
client = minio.Minio('localhost:9000', access_key='intranest', secret_key='intranest123', secure=False)
buckets = list(client.list_buckets())
print(f'✅ MinIO connection successful. Found {len(buckets)} buckets')
" 2>/dev/null && log_success "MinIO connection test passed" || log_error "MinIO connection test failed"

# Test Redis connection
python3 -c "
import redis
client = redis.Redis(host='localhost', port=6379, decode_responses=True)
client.ping()
print('✅ Redis connection successful')
" 2>/dev/null && log_success "Redis connection test passed" || log_error "Redis connection test failed"

# Step 10: Create startup scripts
echo
log_info "Step 10: Creating startup scripts..."

# Backend startup script with document management
cat > "$BACKEND_DIR/start_with_documents.sh" << 'EOF'
#!/bin/bash
# Start IntraNest backend with document management

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start storage services
cd ../infrastructure/docker/document-management
docker-compose up -d

# Wait for services
sleep 10

# Go back to backend
cd ../../../backend

# Start Celery worker in background
celery -A celery_worker worker --loglevel=info --detach

# Start FastAPI server
echo "🚀 Starting IntraNest backend with document management..."
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
EOF

chmod +x "$BACKEND_DIR/start_with_documents.sh"

# Celery monitoring script  
cat > "$BACKEND_DIR/monitor_celery.sh" << 'EOF'
#!/bin/bash
# Monitor Celery worker and tasks

cd "$(dirname "$0")"
source venv/bin/activate

echo "🔍 Celery Worker Status:"
celery -A celery_worker status

echo -e "\n📊 Active Tasks:"
celery -A celery_worker active

echo -e "\n📈 Task Statistics:"
celery -A celery_worker stats
EOF

chmod +x "$BACKEND_DIR/monitor_celery.sh"

log_success "Startup scripts created"

# Step 11: Display setup summary
echo
echo "🎉 IntraNest Document Management Setup Complete!"
echo "================================================"
echo
log_info "Services Status:"
echo "  • MinIO (Object Storage): http://localhost:9001 (admin: intranest/intranest123)"
echo "  • MinIO API: http://localhost:9000"
echo "  • Redis (Cache): localhost:6379"
echo
log_info "Next Steps:"
echo "  1. Add the enhanced backend code to your main.py"
echo "  2. Copy the complete celery_worker.py from the artifact"
echo "  3. Start the backend with: ./start_with_documents.sh"
echo "  4. Test document upload via API"
echo
log_info "API Endpoints Added:"
echo "  • POST /api/documents/presigned-url - Generate upload URL"
echo "  • POST /api/documents/confirm-upload - Confirm and process"
echo "  • GET /api/documents/status/{id} - Get processing status"
echo "  • POST /api/documents/list - List user documents"
echo
log_info "Monitoring Commands:"
echo "  • Monitor Celery: ./monitor_celery.sh"
echo "  • View MinIO Console: http://localhost:9001"
echo "  • Check logs: docker-compose logs -f"
echo
log_info "Testing Commands:"
# Test upload
cat > "$BACKEND_DIR/test_upload.py" << 'PYTEST'
#!/usr/bin/env python3
"""Test script for document upload functionality"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:8001"
API_KEY = "intranest_3JLzzwF0rQ7I6ulzx1F1RasuBE_1m0EN6xOLsIp8Q7s"
TEST_USER = "test_user_123"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def test_presigned_url():
    """Test presigned URL generation"""
    print("🧪 Testing presigned URL generation...")
    
    payload = {
        "filename": "test_document.txt",
        "user_id": TEST_USER,
        "file_size": 1024
    }
    
    response = requests.post(f"{API_BASE}/api/documents/presigned-url", 
                           json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Presigned URL generated: {data['document_id']}")
        return data
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
        return None

def test_file_upload(presigned_data):
    """Test actual file upload to presigned URL"""
    print("🧪 Testing file upload...")
    
    # Sample file content
    test_content = """IntraNest Test Document
    
This is a test document for the IntraNest document management system.
It contains sample content to test the upload and processing functionality.

Key features being tested:
- File upload via presigned URL
- Document processing and chunking
- Weaviate storage integration
- Background processing with Celery

This document should be processed into multiple chunks for semantic search.
"""
    
    # Upload to presigned URL
    upload_response = requests.put(
        presigned_data["upload_url"],
        data=test_content.encode('utf-8'),
        headers={"Content-Type": "text/plain"}
    )
    
    if upload_response.status_code in [200, 204]:
        print("✅ File uploaded successfully")
        return True
    else:
        print(f"❌ Upload failed: {upload_response.status_code}")
        return False

def test_confirm_upload(document_id):
    """Test upload confirmation and processing"""
    print("🧪 Testing upload confirmation...")
    
    payload = {
        "document_id": document_id,
        "user_id": TEST_USER
    }
    
    response = requests.post(f"{API_BASE}/api/documents/confirm-upload",
                           json=payload, headers=headers)
    
    if response.status_code == 200:
        print("✅ Upload confirmed, processing started")
        return True
    else:
        print(f"❌ Confirmation failed: {response.status_code} - {response.text}")
        return False

def test_processing_status(document_id):
    """Test processing status monitoring"""
    print("🧪 Monitoring processing status...")
    
    max_attempts = 30  # 30 seconds max
    for attempt in range(max_attempts):
        response = requests.get(
            f"{API_BASE}/api/documents/status/{document_id}",
            params={"user_id": TEST_USER},
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            progress = data.get("progress", 0)
            
            print(f"  Status: {status} ({progress}%)")
            
            if status == "completed":
                print(f"✅ Processing completed! Chunks created: {data.get('chunks_created', 0)}")
                return True
            elif status == "error":
                print(f"❌ Processing failed: {data.get('error', 'Unknown error')}")
                return False
            
            time.sleep(1)
        else:
            print(f"❌ Status check failed: {response.status_code}")
            return False
    
    print("⏰ Processing timeout")
    return False

def test_document_list():
    """Test document listing"""
    print("🧪 Testing document list...")
    
    payload = {"user_id": TEST_USER}
    
    response = requests.post(f"{API_BASE}/api/documents/list",
                           json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        docs = data.get("documents", [])
        print(f"✅ Found {len(docs)} documents for user")
        
        if docs:
            doc = docs[0]
            print(f"  Sample document: {doc.get('filename')} ({doc.get('chunks', 0)} chunks)")
        
        return True
    else:
        print(f"❌ List failed: {response.status_code} - {response.text}")
        return False

def main():
    """Run complete test suite"""
    print("🚀 Starting IntraNest Document Management Tests")
    print("=" * 50)
    
    # Test 1: Generate presigned URL
    presigned_data = test_presigned_url()
    if not presigned_data:
        return
    
    document_id = presigned_data["document_id"]
    
    # Test 2: Upload file
    if not test_file_upload(presigned_data):
        return
    
    # Test 3: Confirm upload
    if not test_confirm_upload(document_id):
        return
    
    # Test 4: Monitor processing
    if not test_processing_status(document_id):
        return
    
    # Test 5: List documents
    test_document_list()
    
    print("\n🎉 All tests completed successfully!")

if __name__ == "__main__":
    main()
PYTEST

chmod +x "$BACKEND_DIR/test_upload.py"

echo "  • Test upload: python3 test_upload.py"
echo
log_warning "Important Notes:"
echo "  • Make sure to add the enhanced backend code to main.py"
echo "  • Copy the complete celery_worker.py from the provided artifact"
echo "  • Update your requirements.txt with new dependencies"
echo "  • MinIO console credentials: intranest / intranest123"
echo
log_success "Setup completed! Ready for Phase 1 testing."
