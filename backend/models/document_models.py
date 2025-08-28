#!/usr/bin/env python3
"""
Document-related Pydantic models for IntraNest 2.0
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class DocumentUploadRequest(BaseModel):
    user_id: str

class DocumentStatusRequest(BaseModel):
    user_id: str

class DocumentListRequest(BaseModel):
    user_id: str

class DocumentSearchRequest(BaseModel):
    query: str
    user_id: str
    limit: Optional[int] = 5

class DocumentDeleteRequest(BaseModel):
    document_id: str
    user_id: str

class DocumentUploadResponse(BaseModel):
    success: bool
    document_id: str
    filename: str
    status: str
    message: str
    chunks_created: Optional[int] = 0
    word_count: Optional[int] = 0
    error: Optional[str] = None

class DocumentStatusResponse(BaseModel):
    success: bool
    document_id: str
    status: str
    progress: int
    message: str
    filename: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    chunks_created: Optional[int] = 0
    word_count: Optional[int] = 0

class DocumentMetadata(BaseModel):
    id: str
    filename: str
    size: int
    uploadDate: str
    status: str
    userId: str
    documentId: str
    chunks: int
    wordCount: int
    fileType: str

class DocumentListResponse(BaseModel):
    success: bool
    documents: List[DocumentMetadata]
    total: int
    userId: str
    source: Optional[str] = None

class SearchResult(BaseModel):
    content: str
    filename: str
    chunk_id: int
    page_number: int
    similarity_score: float
    document_id: str
    node_id: str

class DocumentSearchResponse(BaseModel):
    success: bool
    query: str
    results: List[SearchResult]
    total: int

class RAGSource(BaseModel):
    filename: str
    page: int
    chunk: int
    relevance: float
    node_id: str

class RAGResponse(BaseModel):
    success: bool
    query: str
    response: str
    sources: List[RAGSource]
    has_context: bool
    context_chunks: Optional[int] = 0
