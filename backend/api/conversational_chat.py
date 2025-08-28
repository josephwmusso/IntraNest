# api/conversational_chat.py
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import json
import asyncio
from datetime import datetime
from core.conversational_dependencies import get_conversational_rag_service, get_memory_manager
from services.conversational_rag import ConversationalRAGService
from services.memory_manager import MemoryManager
from models.conversation_models import ChatSession, MessageRole

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Conversational Chat"])

# Request/Response Models
class ConversationalChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: str
    stream: bool = False
    max_context_messages: Optional[int] = 10

class ConversationalChatResponse(BaseModel):
    response: str
    session_id: str
    metadata: Dict[str, Any]
    timestamp: datetime

class ChatSessionRequest(BaseModel):
    user_id: str
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    session_id: str
    title: Optional[str]
    created_at: datetime
    message_count: int

class SessionHistoryResponse(BaseModel):
    sessions: List[ChatSessionResponse]
    total: int

@router.post("/conversational", response_model=ConversationalChatResponse)
async def conversational_chat(
    request: ConversationalChatRequest,
    rag_service: ConversationalRAGService = Depends(get_conversational_rag_service)
):
    """Enhanced chat endpoint with conversational memory and context awareness"""
    try:
        # Generate session ID if not provided
        if not request.session_id:
            import uuid
            request.session_id = str(uuid.uuid4())
        
        # Process query with conversational context
        result = await rag_service.process_conversational_query(
            user_id=request.user_id,
            session_id=request.session_id,
            query=request.message,
            stream=request.stream
        )
        
        if result["type"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        if result["type"] == "stream":
            # Return streaming response (handled by separate endpoint)
            raise HTTPException(status_code=400, detail="Use /chat/conversational/stream for streaming responses")
        
        return ConversationalChatResponse(
            response=result["response"],
            session_id=request.session_id,
            metadata=result["metadata"],
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error in conversational chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/conversational/stream")
async def conversational_chat_stream(
    request: ConversationalChatRequest,
    rag_service: ConversationalRAGService = Depends(get_conversational_rag_service)
):
    """Streaming endpoint for conversational chat"""
    try:
        # Generate session ID if not provided
        if not request.session_id:
            import uuid
            request.session_id = str(uuid.uuid4())
        
        # Process query with streaming
        result = await rag_service.process_conversational_query(
            user_id=request.user_id,
            session_id=request.session_id,
            query=request.message,
            stream=True
        )
        
        if result["type"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        async def generate_sse_stream():
            """Generate Server-Sent Events stream"""
            try:
                # Send metadata first
                metadata_event = {
                    "type": "metadata",
                    "data": result["metadata"]
                }
                yield f"data: {json.dumps(metadata_event)}\n\n"
                
                # Stream response content
                full_response = ""
                async for chunk in result["generator"]:
                    full_response += chunk
                    chunk_event = {
                        "type": "chunk",
                        "data": {"content": chunk}
                    }
                    yield f"data: {json.dumps(chunk_event)}\n\n"
                    await asyncio.sleep(0.01)  # Small delay for better UX
                
                # Send completion event
                completion_event = {
                    "type": "complete",
                    "data": {
                        "full_response": full_response,
                        "session_id": request.session_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                yield f"data: {json.dumps(completion_event)}\n\n"
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                error_event = {
                    "type": "error", 
                    "data": {"error": str(e)}
                }
                yield f"data: {json.dumps(error_event)}\n\n"
        
        return StreamingResponse(
            generate_sse_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in streaming chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    request: ChatSessionRequest,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Create a new chat session"""
    try:
        import uuid
        session_id = str(uuid.uuid4())
        
        # Create new session with initial state
        session = ChatSession(
            id=session_id,
            user_id=request.user_id,
            title=request.title or f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Save session
        await memory_manager.save_session(session)
        
        return ChatSessionResponse(
            session_id=session_id,
            title=session.title,
            created_at=session.created_at,
            message_count=0
        )
        
    except Exception as e:
        logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{user_id}", response_model=SessionHistoryResponse)
async def get_user_sessions(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Get chat sessions for a user"""
    try:
        # This would be implemented with actual database queries
        # For now, return empty response
        return SessionHistoryResponse(
            sessions=[],
            total=0
        )
        
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Get messages for a specific session"""
    try:
        # Get conversation context (includes recent messages)
        context = await memory_manager.get_conversation_context(session_id, "", limit)
        
        return {
            "session_id": session_id,
            "messages": context.get("recent_messages", []),
            "conversation_state": context.get("conversation_state"),
            "total_messages": len(context.get("recent_messages", []))
        }
        
    except Exception as e:
        logger.error(f"Error getting session messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Delete a chat session and its memory"""
    try:
        await memory_manager.clear_session_memory(session_id)
        
        return {"message": f"Session {session_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/context")
async def get_session_context(
    session_id: str,
    user_id: str,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Get full context for a session (for debugging/analysis)"""
    try:
        context = await memory_manager.get_conversation_context(session_id, user_id)
        
        return {
            "session_id": session_id,
            "context": context,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error getting session context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/summarize")
async def trigger_session_summarization(
    session_id: str,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Manually trigger summarization for a session"""
    try:
        # This would trigger the summarization process
        # Implementation depends on your MemoryManager
        await memory_manager._trigger_summarization(session_id)
        
        return {"message": f"Summarization triggered for session {session_id}"}
        
    except Exception as e:
        logger.error(f"Error triggering summarization: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy compatibility endpoint
@router.post("/completions")
async def chat_completions_compatibility(
    request: Request,
    rag_service: ConversationalRAGService = Depends(get_conversational_rag_service)
):
    """OpenAI-compatible endpoint with conversational enhancements"""
    try:
        body = await request.json()
        
        # Extract information from OpenAI format
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        # Get the last user message
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")
        
        # Use a default session for legacy compatibility
        session_id = body.get("session_id", "legacy_session")
        user_id = body.get("user_id", "default_user")
        
        # Process with conversational RAG
        result = await rag_service.process_conversational_query(
            user_id=user_id,
            session_id=session_id,
            query=user_message,
            stream=stream
        )
        
        if result["type"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        if stream and result["type"] == "stream":
            # OpenAI-compatible streaming format 
            async def openai_stream_format():
                completion_id = f"chatcmpl-{int(datetime.utcnow().timestamp())}"
                
                async for chunk in result["generator"]:
                    chunk_response = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": int(datetime.utcnow().timestamp()),
                        "model": "intranest-conversational",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_response)}\n\n"
                
                # Send completion
                final_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(datetime.utcnow().timestamp()),
                    "model": "intranest-conversational",
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                openai_stream_format(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        else:
            # Non-streaming OpenAI format
            return {
                "id": f"chatcmpl-{int(datetime.utcnow().timestamp())}",
                "object": "chat.completion",
                "created": int(datetime.utcnow().timestamp()),
                "model": "intranest-conversational", 
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result["response"]
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 0,  # Would calculate actual tokens
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
            
    except Exception as e:
        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
