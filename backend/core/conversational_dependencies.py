# core/conversational_dependencies.py
from functools import lru_cache
import redis.asyncio as redis
import weaviate
import openai
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from typing import Dict, Any
import os
from datetime import datetime
from services.memory_manager import MemoryManager
from services.query_rewriter import QueryRewriter
from services.conversational_rag import ConversationalRAGService
from utils.conversational_text_processing import ConversationalTextProcessor
from config.conversational_settings import get_conversational_config
import logging

logger = logging.getLogger(__name__)

# Client Instances
@lru_cache()
def get_redis_client() -> redis.Redis:
    """Get Redis client for caching"""
    config = get_conversational_config()
    return redis.from_url(config["redis_url"], decode_responses=True)

@lru_cache()
def get_weaviate_client():
    """Get Weaviate client for vector operations (using HTTP requests for now)"""
    # For now, we'll return None and handle Weaviate through HTTP requests
    # This avoids the v3/v4 compatibility issues
    return None

@lru_cache()
def get_openai_client() -> openai.AsyncOpenAI:
    """Get OpenAI client"""
    config = get_conversational_config()
    return openai.AsyncOpenAI(api_key=config["openai_api_key"])

@lru_cache()
def get_database_engine():
    """Get database engine for session management"""
    config = get_conversational_config()
    return create_async_engine(config["database_url"], echo=True)

async def get_database_session() -> AsyncSession:
    """Get database session"""
    engine = get_database_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# Service Dependencies
async def get_text_processor() -> ConversationalTextProcessor:
    """Get conversational text processing utilities"""
    openai_client = get_openai_client()
    config = get_conversational_config()
    return ConversationalTextProcessor(openai_client, config)

async def get_memory_manager() -> MemoryManager:
    """Get memory manager instance"""
    redis_client = get_redis_client()
    weaviate_client = get_weaviate_client()
    openai_client = get_openai_client()  # Get OpenAI client
    config = get_conversational_config()

    # Get database session - this is a simplified version
    # In production, you'd want proper session management
    db_session = None  # Would get from dependency

    return MemoryManager(
        redis_client=redis_client,
        weaviate_client=weaviate_client,
        db_session=db_session,
        openai_client=openai_client,  # Pass OpenAI client to MemoryManager
        config=config
    )

async def get_query_rewriter() -> QueryRewriter:
    """Get query rewriter instance"""
    openai_client = get_openai_client()
    config = get_conversational_config()

    return QueryRewriter(
        openai_client=openai_client,
        config=config
    )

async def get_conversational_rag_service() -> ConversationalRAGService:
    """Get conversational RAG service instance"""
    memory_manager = await get_memory_manager()
    query_rewriter = await get_query_rewriter()
    weaviate_client = get_weaviate_client()
    openai_client = get_openai_client()
    config = get_conversational_config()

    return ConversationalRAGService(
        memory_manager=memory_manager,
        query_rewriter=query_rewriter,
        weaviate_client=weaviate_client,
        openai_client=openai_client,
        config=config
    )

# Health Check Functions
async def check_conversational_services() -> Dict[str, Any]:
    """Check health of all conversational services"""
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    try:
        # Check Redis
        redis_client = get_redis_client()
        await redis_client.ping()
        health_status["services"]["redis"] = {"status": "healthy", "type": "cache"}
    except Exception as e:
        health_status["services"]["redis"] = {"status": "unhealthy", "error": str(e)}

    try:
        # Check Weaviate using HTTP requests (avoid client version issues)
        import requests
        config = get_conversational_config()

        headers = {}
        if config.get("weaviate_api_key"):
            headers["Authorization"] = f"Bearer {config['weaviate_api_key']}"

        response = requests.get(f"{config['weaviate_url']}/v1/meta", headers=headers, timeout=5)

        if response.status_code == 200:
            health_status["services"]["weaviate"] = {"status": "healthy", "type": "vector_db"}
        else:
            health_status["services"]["weaviate"] = {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        health_status["services"]["weaviate"] = {"status": "unhealthy", "error": str(e)}

    try:
        # Check OpenAI
        openai_client = get_openai_client()
        # Simple test call
        models = await openai_client.models.list()
        health_status["services"]["openai"] = {"status": "healthy", "type": "llm"}
    except Exception as e:
        health_status["services"]["openai"] = {"status": "unhealthy", "error": str(e)}

    # Overall health
    unhealthy_services = [name for name, status in health_status["services"].items()
                         if status["status"] == "unhealthy"]

    health_status["overall_status"] = "healthy" if not unhealthy_services else "degraded"
    health_status["unhealthy_services"] = unhealthy_services

    return health_status
