#!/bin/bash
# update_backend.sh - Add document management to existing backend

set -e

echo "📝 Updating IntraNest backend with document management..."

cd /home/ec2-user/IntraNest2.0/backend

# Backup existing main.py
cp main.py main.py.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backed up existing main.py"

# Create the enhanced main.py by appending new code
echo "🔧 Adding document management imports and classes..."

# Add the new imports after the existing ones
cat >> main.py << 'EOF'

# === DOCUMENT MANAGEMENT IMPORTS ===
import minio
import redis
import json
import hashlib
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import asyncio

# === DOCUMENT MANAGEMENT CONFIGURATION ===
class DocumentConfig:
    """Document management configuration"""
    STORAGE_TYPE = os.getenv("STORAGE_TYPE", "minio")
    S3_BUCKET = os.getenv("S3_BUCKET", "intranest-documents")
    S3_REGION = os.getenv("S3_REGION", "us-west-2")
    S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "intranest")
    S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "intranest123")
    S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
    
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'text/html', 'text/markdown'
    }
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200

class StorageService:
    """Handle file storage operations"""
    def __init__(self):
        self.client = minio.Minio(
            DocumentConfig.S3_ENDPOINT.replace("http://", "").replace("https://", ""),
            access_key=DocumentConfig.S3_ACCESS_KEY,
            secret_key=DocumentConfig.S3_SECRET_KEY,
            secure=DocumentConfig.S3_ENDPOINT.startswith("https://")
        )
    
    def generate_presigned_upload_url(self, tenant_id: str, user_id: str, filename: str) -> Dict[str, Any]:
        """Generate presigned URL for direct upload"""
        file_extension = Path(filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        object_key = f"tenants/{tenant_id}/users/{user_id}/{unique_filename}"
        
        try:
            presigned_url = self.client.presigned_put_object(
                DocumentConfig.S3_BUCKET,
                object_key,
                expires=timedelta(hours=1)
            )
            
            return {
                "upload_url": presigned_url,
                "object_key": object_key,
                "bucket": DocumentConfig.S3_BUCKET,
                "expires_in": 3600
            }
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate upload URL")
    
    def get_file_content(self, object_key: str) -> bytes:
        """Retrieve file content for processing"""
        try:
            response = self.client.get_object(DocumentConfig.S3_BUCKET, object_key)
            return response.read()
        except Exception as e:
            logger.error(f"Failed to retrieve file {object_key}: {e}")
            raise

class DocumentCacheService:
    """Handle document metadata caching"""
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True
        )
    
    def cache_processing_status(self, document_id: str, status: Dict, ttl: int = 3600):
        """Cache document processing status"""
        cache_key = f"processing:document:{document_id}"
        self.redis_client.setex(cache_key, ttl, json.dumps(status))
    
    def get_processing_status(self, document_id: str) -> Optional[Dict]:
        """Get document processing status"""
        cache_key = f"processing:document:{document_id}"
        cached = self.redis_client.get(cache_key)
        return json.loads(cached) if cached else None

# Initialize document management services
try:
    storage_service = StorageService()
    cache_service = DocumentCacheService()
    print("✅ Document management services initialized")
except Exception as e:
    print(f"⚠️  Document management services initialization warning: {e}")
    storage_service = None
    cache_service = None

# === DOCUMENT MANAGEMENT ENDPOINTS ===

@app.post("/api/documents/presigned-url")
async def generate_presigned_url(request: dict, api_key: bool = Depends(verify_api_key)):
    """Generate presigned URL for direct file upload"""
    if not storage_service:
        raise HTTPException(status_code=503, detail="Storage service not available")
        
    try:
        filename = request.get("filename")
        user_id = request.get("user_id")
        tenant_id = request.get("tenant_id", "default")
        file_size = request.get("file_size", 0)
        
        if not filename or not user_id:
            raise HTTPException(status_code=400, detail="filename and user_id are required")
        
        # Validate file size
        if file_size > DocumentConfig.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File size {file_size} exceeds maximum allowed size"
            )
        
        # Validate file type
        mime_type = mimetypes.guess_type(filename)[0]
        if mime_type not in DocumentConfig.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Supported: PDF, DOCX, TXT, HTML, MD"
            )
        
        # Generate presigned URL
        upload_info = storage_service.generate_presigned_upload_url(tenant_id, user_id, filename)
        document_id = f"doc_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Cache initial metadata
        document_metadata = {
            "document_id": document_id,
            "filename": filename,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "object_key": upload_info["object_key"],
            "status": "upload_pending",
            "created_at": datetime.now().isoformat(),
            "file_size": file_size,
            "mime_type": mime_type
        }
        
        if cache_service:
            cache_service.cache_processing_status(document_id, document_metadata)
        
        return {
            "success": True,
            "document_id": document_id,
            "upload_url": upload_info["upload_url"],
            "expires_in": upload_info["expires_in"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/documents/confirm-upload")
async def confirm_upload(request: dict, api_key: bool = Depends(verify_api_key)):
    """Confirm successful upload and process document"""
    if not cache_service or not storage_service:
        raise HTTPException(status_code=503, detail="Document services not available")
        
    try:
        document_id = request.get("document_id")
        user_id = request.get("user_id")
        
        if not document_id or not user_id:
            raise HTTPException(status_code=400, detail="document_id and user_id required")
        
        # Get document metadata
        document_metadata = cache_service.get_processing_status(document_id)
        if not document_metadata:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if document_metadata.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update status and process
        document_metadata["status"] = "processing"
        document_metadata["processing_started_at"] = datetime.now().isoformat()
        cache_service.cache_processing_status(document_id, document_metadata)
        
        # Process document (simplified for now)
        try:
            await process_document_simple(document_id, document_metadata)
        except Exception as e:
            document_metadata["status"] = "error"
            document_metadata["error"] = str(e)
            cache_service.cache_processing_status(document_id, document_metadata)
        
        return {
            "success": True,
            "document_id": document_id,
            "status": document_metadata["status"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/status/{document_id}")
async def get_processing_status(document_id: str, user_id: str, api_key: bool = Depends(verify_api_key)):
    """Get document processing status"""
    if not cache_service:
        raise HTTPException(status_code=503, detail="Cache service not available")
        
    try:
        status = cache_service.get_processing_status(document_id)
        if not status:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if status.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "success": True,
            "document_id": document_id,
            "status": status.get("status", "unknown"),
            "filename": status.get("filename"),
            "created_at": status.get("created_at"),
            "completed_at": status.get("completed_at"),
            "error": status.get("error"),
            "chunks_created": status.get("chunks_created", 0),
            "progress": status.get("progress", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === DOCUMENT PROCESSING FUNCTIONS ===

async def process_document_simple(document_id: str, document_metadata: Dict):
    """Simplified document processing"""
    try:
        object_key = document_metadata["object_key"]
        filename = document_metadata["filename"]
        user_id = document_metadata["user_id"]
        
        # Download and process file
        file_content = storage_service.get_file_content(object_key)
        text_content = file_content.decode('utf-8', errors='ignore')
        
        # Create chunks
        chunks = create_simple_chunks(text_content, filename, document_id, user_id)
        
        if chunks:
            # Store in Weaviate
            success_count = await store_chunks_simple(chunks)
            
            # Update status
            document_metadata.update({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "chunks_created": success_count,
                "progress": 100
            })
        else:
            raise Exception("No content extracted")
        
        cache_service.cache_processing_status(document_id, document_metadata, ttl=86400)
        
    except Exception as e:
        document_metadata.update({
            "status": "error",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })
        cache_service.cache_processing_status(document_id, document_metadata, ttl=86400)
        raise

def create_simple_chunks(text_content: str, filename: str, document_id: str, user_id: str) -> List[Dict]:
    """Create simple text chunks"""
    if not text_content.strip():
        return []
    
    chunks = []
    chunk_size = 1000
    
    # Split into chunks
    for i in range(0, len(text_content), chunk_size):
        chunk_text = text_content[i:i + chunk_size]
        
        chunk_data = {
            "content": chunk_text,
            "filename": filename,
            "user_id": user_id,
            "document_id": document_id,
            "node_id": f"{document_id}_chunk_{i // chunk_size}",
            "chunk_id": i // chunk_size,
            "page_number": 1,
            "metadata": {
                "upload_date": datetime.now().isoformat(),
                "file_type": "text/plain",
                "chunk_size": len(chunk_text)
            }
        }
        chunks.append(chunk_data)
    
    return chunks

async def store_chunks_simple(chunks: List[Dict]) -> int:
    """Store chunks in Weaviate"""
    client = weaviate.connect_to_local(
        host=WEAVIATE_URL.replace("http://", "").replace("https://", ""),
        auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None
    )
    
    try:
        documents_collection = client.collections.get("Documents")
        success_count = 0
        
        for chunk in chunks:
            try:
                documents_collection.data.insert(chunk)
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to insert chunk: {e}")
        
        return success_count
        
    finally:
        client.close()

print("📄 Document management endpoints added to IntraNest backend")
EOF

echo "✅ Document management code added to main.py"

# Update .env file
echo "🔧 Updating environment variables..."
cat >> .env << 'EOF'

# Document Management Configuration
STORAGE_TYPE=minio
S3_BUCKET=intranest-documents
S3_ACCESS_KEY=intranest
S3_SECRET_KEY=intranest123
S3_ENDPOINT=http://localhost:9000
REDIS_URL=redis://localhost:6379
EOF

echo "✅ Environment variables updated"

echo ""
echo "🎉 Backend update complete!"
echo ""
echo "📋 What was added:"
echo "  • Document upload endpoints"
echo "  • MinIO storage integration"
echo "  • Redis caching"
echo "  • Document processing pipeline"
echo ""
echo "🚀 Ready to test! Run:"
echo "  uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
