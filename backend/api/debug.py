#!/usr/bin/env python3
"""
Debug API endpoints for IntraNest 2.0
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from core.dependencies import verify_api_key
from config.settings import get_settings
from services import (
    get_storage_service, get_cache_service, get_document_processor,
    get_rag_service, get_response_generator
)

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

@router.get("/services")
async def debug_services(api_key: bool = Depends(verify_api_key)):
    """Debug service status"""
    storage_service = get_storage_service()
    cache_service = get_cache_service()
    document_processor = get_document_processor()
    rag_service = get_rag_service()
    response_generator = get_response_generator()
    
    return {
        "services": {
            "storage_service": storage_service is not None,
            "cache_service": cache_service is not None,
            "document_processor": document_processor is not None,
            "rag_service": rag_service is not None,
            "response_generator": response_generator is not None,
            "weaviate_client": rag_service and rag_service.weaviate_client is not None if rag_service else False
        },
        "environment": {
            "openai_key_present": bool(settings.openai_api_key),
            "weaviate_key_present": bool(settings.weaviate_api_key),
            "redis_configured": bool(settings.redis_url)
        },
        "capabilities": {
            "enhanced_pdf_processing": bool(document_processor),
            "modular_architecture": True
        }
    }
