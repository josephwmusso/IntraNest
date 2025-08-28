# backend/api/routes/chat.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: str = "default-user"  # Temporary until auth is implemented
    tenant_id: str = "default"     # Temporary until auth is implemented
    include_sources: bool = True
    stream: bool = False

class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]]
    session_id: Optional[str]
    document_context_used: bool
    metadata: Dict[str, Any]

@router.post("/chat", response_model=ChatResponse)
async def chat_with_rag(chat_message: ChatMessage) -> ChatResponse:
    """Main chat endpoint with RAG integration"""
    
    # Import here to avoid circular imports
    from main import weaviate_service, ai_service
    
    try:
        # Ensure tenant exists
        await weaviate_service.setup_tenant(chat_message.tenant_id)
        
        # Generate RAG response
        rag_result = await weaviate_service.generate_rag_response(
            tenant_id=chat_message.tenant_id,
            user_id=chat_message.user_id,
            query=chat_message.message,
            limit=5
        )
        
        return ChatResponse(
            response=rag_result["response"],
            sources=rag_result["sources"],
            session_id=chat_message.session_id,
            document_context_used=rag_result["document_context_used"],
            metadata=rag_result["metadata"]
        )
        
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@router.post("/chat/simple")
async def simple_chat(chat_message: ChatMessage) -> Dict[str, Any]:
    """Simple chat without document context"""
    
    from main import ai_service
    
    try:
        # For now, return a simple response
        # Later this will use the AI service
        return {
            "response": f"I received your message: '{chat_message.message}'. This is a simple response without document context.",
            "sources": [],
            "document_context_used": False,
            "session_id": chat_message.session_id
        }
        
    except Exception as e:
        logger.error(f"Simple chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")
