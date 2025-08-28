# models/conversation_models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import uuid

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ConversationIntent(str, Enum):
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    IMPROVEMENT = "improvement"
    EXPANSION = "expansion"
    SUMMARIZATION = "summarization"
    CLARIFICATION = "clarification"
    GENERAL = "general"

class ConversationState(BaseModel):
    """Current conversation state tracking"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_topic: Optional[str] = None
    current_entities: Dict[str, Any] = Field(default_factory=dict)
    current_intent: ConversationIntent = ConversationIntent.GENERAL
    intent_history: List[ConversationIntent] = Field(default_factory=list)
    unresolved_references: List[str] = Field(default_factory=list)
    context_summary: Optional[str] = None
    last_retrieved_docs: List[str] = Field(default_factory=list)
    conversation_depth: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ChatMessage(BaseModel):
    """Individual chat message"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    content: str
    role: MessageRole
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent: Optional[ConversationIntent] = None
    entities: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatSession(BaseModel):
    """Complete chat session"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: Optional[str] = None
    state: ConversationState
    messages: List[ChatMessage] = Field(default_factory=list)
    summary: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ConversationMemory(BaseModel):
    """Long-term conversation memory entry"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    topic: str
    summary: str
    key_entities: Dict[str, Any] = Field(default_factory=dict)
    importance_score: float = 0.0
    access_count: int = 0
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QueryRewriteRequest(BaseModel):
    """Request for query rewriting"""
    original_query: str
    conversation_context: List[ChatMessage]
    current_state: ConversationState

class QueryRewriteResponse(BaseModel):
    """Response from query rewriting"""
    original_query: str
    rewritten_query: str
    resolved_entities: Dict[str, str] = Field(default_factory=dict)
    confidence_score: float = 0.0
    reasoning: Optional[str] = None
