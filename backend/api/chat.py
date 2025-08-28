#!/usr/bin/env python3
"""
Professional Chat and RAG API endpoints for IntraNest 2.0
Advanced LibreChat integration with intelligent conversational RAG support
Full conversation context management and professional debugging
"""

import asyncio
import json
import logging
import uuid
import hashlib
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Optional

from core.dependencies import verify_api_key
from models.document_models import RAGResponse
from services import get_rag_service, get_response_generator
from utils.text_processing import generate_tokens
from utils.weaviate_helper import WeaviateHelper

# FIXED: Import conversational RAG dependencies with correct function name
try:
    from core.conversational_dependencies import get_conversational_rag_service
    CONVERSATIONAL_RAG_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Conversational RAG available")
except ImportError as e:
    CONVERSATIONAL_RAG_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Conversational RAG not available: {e}")

router = APIRouter()

class RAGRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    context_limit: int = 5

def extract_session_from_request(request_data: dict, headers: dict = None) -> tuple:
    """
    Professional session extraction with LibreChat conversation intelligence
    Returns: (session_id, user_id, is_librechat_request)
    """
    
    # DEBUG: Log everything we receive
    logger.info("🔍 DEBUG: Professional session extraction starting")
    logger.info(f"📋 Request keys: {list(request_data.keys())}")
    
    # Analyze request structure
    session_keys = [key for key in request_data.keys() if 'session' in key.lower()]
    user_keys = [key for key in request_data.keys() if 'user' in key.lower()]
    conversation_keys = [key for key in request_data.keys() if 'conversation' in key.lower()]
    
    logger.info(f"🔍 Session-related keys: {session_keys}")
    logger.info(f"🔍 User-related keys: {user_keys}")
    logger.info(f"🔍 Conversation-related keys: {conversation_keys}")
    
    # Log key fields for debugging
    important_fields = ['session_id', 'sessionId', 'user_id', 'userId', 'conversationId', 'conversation_id', 'user', 'model']
    for field in important_fields:
        if field in request_data:
            logger.info(f"🎯 Found {field}: {request_data[field]}")
    
    # Method 1: Direct session parameters (existing direct API calls)
    session_id = request_data.get('session_id')
    user_id = request_data.get('user_id', 'anonymous')
    
    if session_id:
        logger.info(f"📍 Direct API session detected: {session_id}")
        return session_id, user_id, False
    
    # Method 2: Alternative parameter names (from frontend session manager)
    session_id = (
        request_data.get('sessionId') or
        request_data.get('conversation_id') or
        request_data.get('conversationId')
    )
    
    user_id = (
        request_data.get('userId') or
        request_data.get('user_id') or
        request_data.get('user') or
        'anonymous'
    )
    
    if session_id:
        logger.info(f"📍 Frontend session manager detected: {session_id}")
        return session_id, user_id, True
    
    # Method 3: PROFESSIONAL LibreChat conversation intelligence
    messages = request_data.get('messages', [])
    user_field = request_data.get('user')
    
    if messages and user_field:
        logger.info("🧠 Using LibreChat conversation intelligence")
        
        # Extract conversation essence for stable session creation
        conversation_essence = ""
        user_messages = []
        
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get('role', '')
                content = msg.get('content', '')
                
                if role == 'user' and content:
                    user_messages.append(content)
                    # Use first significant user message for session stability
                    if len(content.strip()) > 10:  # Ignore very short messages
                        conversation_essence = content[:200]  # First 200 chars
                        break
        
        if conversation_essence:
            # Create stable session based on user + conversation starter
            conversation_hash = hashlib.md5(
                f"{user_field}_{conversation_essence}".encode()
            ).hexdigest()[:8]
            
            session_id = f"conv_{user_field}_{conversation_hash}"
            logger.info(f"📍 LibreChat conversation session: {session_id} (from: '{conversation_essence[:50]}...')")
            return session_id, user_field, True
        else:
            # Fallback: user-based session with timestamp for uniqueness
            timestamp_hour = datetime.now().strftime('%Y%m%d_%H')
            session_id = f"user_{user_field}_{timestamp_hour}"
            logger.info(f"📍 LibreChat user session: {session_id}")
            return session_id, user_field, True
    
    # Method 4: Check headers for session info
    if headers:
        header_session = None
        header_user = None
        
        for header_name, header_value in headers.items():
            header_lower = header_name.lower()
            if 'session' in header_lower and not header_session:
                header_session = header_value
            elif 'user' in header_lower and not header_user:
                header_user = header_value
        
        if header_session:
            logger.info(f"📍 Header session detected: {header_session}")
            return header_session, header_user or user_id, True
    
    # Method 5: SMART continuity session
    # Create session that provides natural conversation continuity
    user_from_request = request_data.get('user', 'anonymous')
    
    if user_from_request != 'anonymous':
        # Hour-based session for natural conversation flow
        current_hour = datetime.now().strftime('%Y%m%d_%H')
        session_id = f"flow_{user_from_request}_{current_hour}"
        logger.info(f"📍 Smart continuity session: {session_id}")
        return session_id, user_from_request, True
    
    # Method 6: Generate new session (last resort)
    timestamp = int(datetime.now().timestamp())
    session_id = f"auto_{timestamp}_{uuid.uuid4().hex[:8]}"
    user_id = user_from_request if user_from_request != 'anonymous' else 'anonymous'
    
    logger.info(f"📍 Generated new session: {session_id}")
    logger.warning("⚠️ No session context found, created new session")
    return session_id, user_id, True

def analyze_conversation_context(messages: list) -> dict:
    """Analyze conversation for better context understanding"""
    context = {
        'turn_count': 0,
        'user_messages': [],
        'topics': [],
        'conversation_type': 'unknown'
    }
    
    if not messages:
        return context
    
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get('role', '')
            content = msg.get('content', '')
            
            if role == 'user':
                context['turn_count'] += 1
                context['user_messages'].append(content)
                
                # Simple topic detection
                if any(word in content.lower() for word in ['tcs', 'transit', 'cyber', 'security']):
                    context['topics'].append('TCS')
                if any(word in content.lower() for word in ['ai', 'artificial', 'intelligence', 'improve']):
                    context['topics'].append('AI')
    
    # Determine conversation type
    if context['turn_count'] == 1:
        context['conversation_type'] = 'initial'
    elif context['turn_count'] > 1:
        context['conversation_type'] = 'continuation'
    
    return context

async def generate_intranest_content(user_message: str, user_id: str = "anonymous", model: str = "IntraNest-AI") -> str:
    """Generate professional content using response generator and RAG service"""
    response_generator = get_response_generator()
    rag_service = get_rag_service()

    if response_generator:
        return await response_generator.generate_professional_response(user_message, user_id, model, rag_service)
    else:
        return "I apologize, but the response service is not available. Please try again later."

async def generate_conversational_content(
    user_message: str,
    user_id: str = "anonymous",
    session_id: Optional[str] = None,
    model: str = "IntraNest-AI",
    conversation_context: dict = None
) -> str:
    """Generate conversational content with advanced context awareness"""
    if not CONVERSATIONAL_RAG_AVAILABLE:
        logger.warning("🔄 Conversational RAG unavailable, using standard RAG")
        return await generate_intranest_content(user_message, user_id, model)

    try:
        # FIXED: Use correct function name with await
        conversational_rag = await get_conversational_rag_service()

        # Ensure session ID exists
        if not session_id:
            session_id = f"session_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"

        # Log conversation context
        if conversation_context:
            logger.info(f"🧠 Conversation context: {conversation_context['conversation_type']} "
                       f"(turn {conversation_context['turn_count']}, topics: {conversation_context['topics']})")

        # Use conversational RAG for enhanced response
        result = await conversational_rag.process_conversational_query(
            query=user_message,
            user_id=user_id,
            session_id=session_id
        )

        logger.info(f"✅ Conversational RAG response generated with context retention")
        return result["response"]

    except Exception as e:
        logger.error(f"❌ Conversational RAG error: {e}")
        logger.info("🔄 Falling back to standard RAG")
        return await generate_intranest_content(user_message, user_id, model)

def auto_detect_user_id() -> str:
    """Auto-detect user_id from recent documents with enhanced logic"""
    try:
        client = WeaviateHelper.get_client()
        try:
            documents_collection = client.collections.get("Documents")
            recent_response = documents_collection.query.fetch_objects(limit=150)  # Increased sample

            # Count user_ids in recent documents with weighting
            user_counts = {}
            total_docs = 0
            
            for obj in recent_response.objects:
                total_docs += 1
                props = obj.properties if hasattr(obj, 'properties') else {}
                if isinstance(props, dict):
                    obj_user_id = props.get('user_id', '')
                    if obj_user_id and obj_user_id != 'anonymous':
                        user_counts[obj_user_id] = user_counts.get(obj_user_id, 0) + 1

            # Use the most common user_id
            if user_counts:
                detected_user_id = max(user_counts, key=user_counts.get)
                confidence = user_counts[detected_user_id] / total_docs if total_docs > 0 else 0
                logger.info(f"🔄 Auto-detected user_id: {detected_user_id} "
                           f"({user_counts[detected_user_id]}/{total_docs} docs, {confidence:.1%} confidence)")
                return detected_user_id

        finally:
            client.close()
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-detect user_id: {e}")

    return "anonymous"

@router.post("/completions")
async def chat_completions_with_streaming(
    request_data: dict, 
    request: Request,
    api_key: bool = Depends(verify_api_key)
):
    """
    PROFESSIONAL: OpenAI-compatible chat completions with advanced LibreChat integration
    Supports conversational RAG with intelligent session management
    """
    try:
        # PROFESSIONAL DEBUG: Comprehensive request analysis
        logger.info("🔍 === PROFESSIONAL REQUEST ANALYSIS ===")
        logger.info(f"📋 Request keys: {list(request_data.keys())}")
        logger.info(f"📄 Request preview: {str(request_data)[:300]}...")
        
        # Check headers for additional context
        relevant_headers = {}
        if hasattr(request, 'headers'):
            for name, value in request.headers.items():
                if any(term in name.lower() for term in ['session', 'user', 'conversation', 'auth']):
                    relevant_headers[name] = value
        
        logger.info(f"🔍 Relevant headers: {relevant_headers}")
        logger.info("🔍 === END REQUEST ANALYSIS ===")
        
        # PROFESSIONAL SESSION EXTRACTION
        session_id, extracted_user_id, is_librechat = extract_session_from_request(
            request_data, 
            dict(request.headers) if hasattr(request, 'headers') else {}
        )
        
        # Extract request parameters
        messages = request_data.get("messages", [])
        model = request_data.get("model", "IntraNest-AI")
        stream = request_data.get("stream", False)
        user_id = request_data.get("user_id", extracted_user_id)

        # Analyze conversation context
        conversation_context = analyze_conversation_context(messages)
        
        # Auto-detect user_id if needed
        if user_id == "anonymous":
            detected_user_id = auto_detect_user_id()
            if detected_user_id != "anonymous":
                user_id = detected_user_id
                logger.info(f"🔄 Using auto-detected user_id: {user_id}")

        # Ensure we have messages
        if not messages:
            messages = [{"role": "user", "content": "Hello"}]

        # Extract user message
        user_message = "Hello"
        for msg in reversed(messages):
            if msg.get("role") == "user" and msg.get("content"):
                user_message = msg.get("content")
                break

        # PROFESSIONAL LOGGING
        client_type = "LibreChat" if is_librechat else "Direct API"
        logger.info(
            f"💬 {client_type} request: '{user_message[:100]}...' "
            f"user: {user_id} session: {session_id} "
            f"[{conversation_context['conversation_type']} turn {conversation_context['turn_count']}]"
        )

        # INTELLIGENT RESPONSE GENERATION
        if CONVERSATIONAL_RAG_AVAILABLE:
            response_content = await generate_conversational_content(
                user_message, user_id, session_id, model, conversation_context
            )
            logger.info(f"✅ Used conversational RAG with session: {session_id}")
        else:
            response_content = await generate_intranest_content(user_message, user_id, model)
            logger.warning("⚠️ Used standard RAG (conversational unavailable)")

        # STREAMING RESPONSE
        if stream:
            async def event_generator():
                try:
                    completion_id = f"chatcmpl-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8]}"
                    created = int(datetime.now().timestamp())

                    for token in generate_tokens(response_content):
                        chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None
                            }],
                            "session_id": session_id,
                            "conversation_context": conversation_context
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                        await asyncio.sleep(0.01)

                    # Final chunk
                    final_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }],
                        "session_id": session_id
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"

                except Exception as e:
                    logger.error(f"❌ Streaming error: {e}")
                    yield f"data: [DONE]\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Session-ID": session_id
                }
            )
        
        # NON-STREAMING RESPONSE
        else:
            return {
                "id": f"chatcmpl-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": max(1, len(user_message) // 4),
                    "completion_tokens": max(1, len(response_content) // 4),
                    "total_tokens": max(2, len(user_message + response_content) // 4)
                },
                "session_id": session_id,
                "conversation_context": conversation_context,
                "metadata": {
                    "client_type": client_type,
                    "conversational_rag_used": CONVERSATIONAL_RAG_AVAILABLE,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

    except Exception as e:
        logger.error(f"❌ Chat completions error: {e}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        logger.error(f"❌ Request data: {request_data}")
        
        return {
            "id": f"chatcmpl-error-{int(datetime.now().timestamp())}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": "IntraNest-AI",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I apologize, but I encountered an error processing your request. Please try again."
                },
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 25, "total_tokens": 26},
            "error": {
                "type": "internal_error",
                "message": "Request processing failed",
                "timestamp": datetime.utcnow().isoformat()
            }
        }

@router.post("/rag", response_model=RAGResponse)
async def rag_chat_endpoint(request: RAGRequest, api_key: bool = Depends(verify_api_key)):
    """Professional RAG-powered chat endpoint"""
    rag_service = get_rag_service()

    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="query is required")

        if not rag_service:
            raise HTTPException(status_code=503, detail="Document service not available")

        # Auto-detect user_id if anonymous
        user_id = request.user_id
        if user_id == "anonymous":
            detected_user_id = auto_detect_user_id()
            if detected_user_id != "anonymous":
                user_id = detected_user_id

        logger.info(f"🔍 RAG query: '{request.query[:100]}...' user: {user_id}")

        result = await rag_service.generate_rag_response(request.query, user_id, request.context_limit)

        return RAGResponse(
            success=True,
            query=request.query,
            response=result["response"],
            sources=result["sources"],
            has_context=result["has_context"],
            context_chunks=result.get("context_chunks", 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ RAG chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/debug/session")
async def debug_session_endpoint(request_data: dict, request: Request, api_key: bool = Depends(verify_api_key)):
    """Professional debug endpoint for session analysis"""
    
    logger.info("🔍 DEBUG ENDPOINT: Session analysis requested")
    
    # Full request analysis
    headers_dict = dict(request.headers) if hasattr(request, 'headers') else {}
    session_id, user_id, is_librechat = extract_session_from_request(request_data, headers_dict)
    conversation_context = analyze_conversation_context(request_data.get('messages', []))
    
    debug_info = {
        "extraction_result": {
            "session_id": session_id,
            "user_id": user_id,
            "is_librechat_request": is_librechat
        },
        "request_analysis": {
            "keys": list(request_data.keys()),
            "has_messages": 'messages' in request_data,
            "message_count": len(request_data.get('messages', [])),
            "model": request_data.get('model', 'not_specified')
        },
        "conversation_context": conversation_context,
        "headers_analysis": {
            "relevant_headers": [k for k in headers_dict.keys() 
                               if any(term in k.lower() for term in ['session', 'user', 'conversation'])],
            "user_agent": headers_dict.get('user-agent', 'not_provided')
        },
        "conversational_rag_status": {
            "available": CONVERSATIONAL_RAG_AVAILABLE,
            "would_be_used": CONVERSATIONAL_RAG_AVAILABLE and session_id is not None
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(f"🔍 DEBUG RESULT: {debug_info}")
    return debug_info

@router.get("/health/conversational")
async def conversational_health():
    """Professional health check for conversational features"""
    return {
        "status": "operational",
        "conversational_rag_available": CONVERSATIONAL_RAG_AVAILABLE,
        "session_management": "advanced_librechat_integration",
        "features": {
            "context_retention": CONVERSATIONAL_RAG_AVAILABLE,
            "session_management": True,
            "conversation_intelligence": True,
            "librechat_integration": True,
            "professional_debugging": True,
            "smart_user_detection": True
        },
        "endpoints": {
            "chat_completions": "/completions",
            "rag_chat": "/rag", 
            "debug_session": "/debug/session"
        },
        "version": "2.0.3-professional",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/debug")
async def debug_health():
    """Debug health endpoint with comprehensive system status"""
    return {
        "system_status": "operational",
        "conversational_rag": {
            "available": CONVERSATIONAL_RAG_AVAILABLE,
            "status": "ready" if CONVERSATIONAL_RAG_AVAILABLE else "fallback_mode"
        },
        "services": {
            "rag_service": get_rag_service() is not None,
            "response_generator": get_response_generator() is not None
        },
        "session_management": {
            "extraction_methods": 6,
            "librechat_intelligence": True,
            "conversation_analysis": True
        },
        "debug_features": {
            "comprehensive_logging": True,
            "request_analysis": True,
            "session_debugging": True,
            "conversation_context": True
        },
        "timestamp": datetime.utcnow().isoformat()
    }
