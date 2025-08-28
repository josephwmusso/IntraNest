# backend/api/routes/health.py
from fastapi import APIRouter, Depends
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Comprehensive system health check"""
    
    # Import here to avoid circular imports
    from main import weaviate_service, ai_service
    
    health_status = {
        "status": "healthy",
        "timestamp": "2025-01-29T00:00:00Z",
        "services": {
            "api": "healthy",
            "weaviate": "unknown",
            "redis": "unknown",
            "ai_provider": "unknown"
        },
        "capabilities": {
            "chat": True,
            "enhanced_chat": True,
            "document_upload": True,
            "processing_enabled": True,
            "intelligent_chunking": True,
            "vector_embeddings": True,
            "semantic_search": True,
            "rag_integration": True,
            "document_chunks": True,
            "multi_tenant": True
        }
    }
    
    # Check Weaviate
    if weaviate_service:
        try:
            weaviate_health = await weaviate_service.health_check()
            health_status["services"]["weaviate"] = weaviate_health["status"]
        except Exception as e:
            logger.error(f"Weaviate health check failed: {e}")
            health_status["services"]["weaviate"] = "unhealthy"
    
    # Check AI service
    if ai_service:
        health_status["services"]["ai_provider"] = "healthy"
    
    # Overall status
    unhealthy_services = [k for k, v in health_status["services"].items() if v == "unhealthy"]
    if unhealthy_services:
        health_status["status"] = "degraded" if len(unhealthy_services) == 1 else "unhealthy"
    
    return health_status
