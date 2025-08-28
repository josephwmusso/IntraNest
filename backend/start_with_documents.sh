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
