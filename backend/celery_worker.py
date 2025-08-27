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
