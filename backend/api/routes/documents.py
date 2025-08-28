# backend/api/routes/documents.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

class DocumentMetadata(BaseModel):
    tags: Optional[List[str]] = []
    description: Optional[str] = ""

class DocumentUploadResponse(BaseModel):
    message: str
    document_id: str
    filename: str
    processing_status: str
    estimated_processing_time: str

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = "default-user",    # Temporary until auth
    tenant_id: str = "default"        # Temporary until auth
) -> DocumentUploadResponse:
    """Upload document for processing"""
    
    from main import weaviate_service
    
    try:
        # Basic file validation
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/html', 'text/markdown']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"File type {file.content_type} not supported")
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Read file content
        file_content = await file.read()
        
        # Ensure tenant exists
        await weaviate_service.setup_tenant(tenant_id)
        
        # For now, create a simple chunk (later we'll add proper document processing)
        document_data = {
            "document_id": document_id,
            "filename": file.filename,
            "file_type": file.content_type,
            "user_id": user_id
        }
        
        # Create a simple chunk from the content
        chunks = [{
            "text": file_content.decode('utf-8') if file.content_type == 'text/plain' else f"Content of {file.filename}",
            "chunk_id": 0,
            "metadata": {
                "file_size": len(file_content),
                "upload_timestamp": datetime.utcnow().isoformat()
            }
        }]
        
        # Upload to Weaviate
        await weaviate_service.upload_document_chunks(tenant_id, document_data, chunks)
        
        return DocumentUploadResponse(
            message="Document upload initiated",
            document_id=document_id,
            filename=file.filename,
            processing_status="completed",
            estimated_processing_time="Instant"
        )
        
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/search/semantic")
async def semantic_search(
    query: str,
    user_id: str = "default-user",
    tenant_id: str = "default",
    limit: int = 5,
    similarity_threshold: float = 0.7
) -> Dict[str, Any]:
    """Perform semantic search across documents"""
    
    from main import weaviate_service
    
    try:
        results = await weaviate_service.search_documents(
            tenant_id=tenant_id,
            user_id=user_id,
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold
        )
        
        return {
            "query": query,
            "results": results,
            "total_results": len(results),
            "processing_time": 0.1  # Placeholder
        }
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
