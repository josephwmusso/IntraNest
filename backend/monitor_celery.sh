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
