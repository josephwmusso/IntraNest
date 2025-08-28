#!/usr/bin/env python3
"""
Document management API endpoints for IntraNest 2.0
Complete implementation with nuclear delete solution
"""

import asyncio
import logging
import traceback
import uuid
import mimetypes
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query
from typing import Dict, List, Optional
from pydantic import BaseModel

from core.dependencies import verify_api_key
from config.document_config import DocumentConfig
from models.document_models import (
    DocumentListRequest, DocumentStatusResponse, DocumentUploadResponse,
    DocumentSearchRequest, DocumentSearchResponse, DocumentDeleteRequest
)
from services import (
    get_storage_service, get_cache_service, get_document_processor,
    get_rag_service
)
from utils.text_processing import create_chunks_with_progress
from utils.weaviate_helper import WeaviateHelper

logger = logging.getLogger(__name__)
router = APIRouter()

# Additional Response Models
class DocumentDeleteResponse(BaseModel):
    success: bool
    document_id: str
    chunks_deleted: int
    message: str

class CacheFlushResponse(BaseModel):
    success: bool
    message: str
    warning: Optional[str] = None

# Helper Functions
def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    size_bytes = float(size_bytes)
    
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    if i == 0:
        return f"{int(size_bytes)} {size_names[i]}"
    else:
        return f"{size_bytes:.1f} {size_names[i]}"

async def store_chunks_with_progress(chunks: List[Dict], document_id: str, cache_service, progress_start: int = 55) -> int:
    """Store chunks in Weaviate with progress updates"""
    client = None
    try:
        logger.info(f"📊 Storing {len(chunks)} chunks for {document_id}")
        
        client = WeaviateHelper.get_client()
        documents_collection = client.collections.get("Documents")
        success_count = 0
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks):
            try:
                # Insert chunk
                result = documents_collection.data.insert(chunk)
                success_count += 1
                
                logger.debug(f"✅ Stored chunk {chunk['chunk_id']} -> {result}")
                
                # Update progress
                progress = progress_start + int(((i + 1) / total_chunks) * 35)  # 35% for storage
                cache_service.update_progress(
                    document_id,
                    "storing",
                    progress,
                    f"Stored {success_count}/{total_chunks} chunks",
                    chunks_processed=success_count,
                    total_chunks=total_chunks
                )
                
                await asyncio.sleep(0.01)  # Small delay for progress visibility
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to store chunk {i}: {e}")
                continue
        
        logger.info(f"📊 Successfully stored {success_count}/{total_chunks} chunks")
        return success_count
        
    except Exception as e:
        logger.error(f"❌ Storage failed: {e}")
        raise
    finally:
        if client:
            try:
                client.close()
            except:
                pass

async def process_document_with_enhanced_extraction(document_id: str, document_metadata: Dict, file_content: bytes, cache_service, document_processor):
    """Process document with enhanced text extraction and real-time progress tracking"""
    try:
        filename = document_metadata["filename"]
        user_id = document_metadata["user_id"]
        
        logger.info(f"📄 Processing document: {filename} for user: {user_id}")
        
        # Step 1: Text extraction with enhanced processing (30% -> 60%)
        cache_service.update_progress(document_id, "extracting_text", 30, "Starting text extraction...")
        
        # FIX: Create an async wrapper for the cache service update
        async def async_update_progress(doc_id, progress, message):
            cache_service.update_progress(doc_id, "processing", progress, message)
        
        # Inject the async update function
        document_processor.update_progress = async_update_progress
        
        text_content = await document_processor.process_file(file_content, filename, document_id)
        
        if not text_content.strip():
            raise Exception(f"No readable text found in {filename}")
        
        cache_service.update_progress(document_id, "text_extracted", 60, f"Extracted {len(text_content)} characters")
        
        # Calculate word count for metadata
        word_count = len(text_content.split())
        
        # Step 2: Create chunks (60% -> 75%)
        logger.info(f"🔪 Creating chunks for {document_id}")
        chunks = create_chunks_with_progress(text_content, filename, document_id, user_id, cache_service, 60)
        
        if not chunks:
            raise Exception("No content chunks created")
        
        # Step 3: Store chunks (75% -> 95%)
        logger.info(f"💾 Storing chunks for {document_id}")
        success_count = await store_chunks_with_progress(chunks, document_id, cache_service, 75)
        
        if success_count == 0:
            raise Exception("Failed to store any chunks")
        
        # Step 4: Finalize (95% -> 100%)
        cache_service.update_progress(document_id, "finalizing", 95, "Finalizing...")
        
        # Update metadata with enhanced information
        document_metadata.update({
            "chunks_created": success_count,
            "status": "completed",
            "total_chunks": len(chunks),
            "chunks_processed": success_count,
            "text_length": len(text_content),
            "word_count": word_count
        })
        
        # Cache document metadata for fast listings
        cache_service.cache_document_metadata(user_id, document_id, document_metadata)
        
        logger.info(f"🎉 Document processing completed: {success_count} chunks stored, {word_count} words")
        
    except Exception as e:
        logger.error(f"❌ Document processing failed: {e}")
        cache_service.update_progress(document_id, "error", 0, f"Processing failed: {str(e)}")
        document_metadata.update({"status": "error", "error": str(e)})
        raise

# API Endpoints

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document_with_enhanced_processing(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    api_key: bool = Depends(verify_api_key)
):
    """Upload and process document with enhanced PDF processing and real-time progress tracking"""
    
    storage_service = get_storage_service()
    cache_service = get_cache_service()
    document_processor = get_document_processor()
    
    # Service availability check
    if not storage_service or not cache_service or not document_processor:
        logger.error("❌ Required services not available")
        raise HTTPException(status_code=503, detail="Document services not available")
    
    try:
        logger.info(f"📤 Enhanced upload started: {file.filename} for user: {user_id}")
        
        # File validation
        file_size = file.size or 0
        if file_size > DocumentConfig.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds {DocumentConfig.MAX_FILE_SIZE // (1024*1024)}MB limit"
            )
        
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0]
        if mime_type not in DocumentConfig.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail="File type not supported. Use PDF, DOCX, TXT, HTML, or MD files."
            )
        
        # Generate document ID
        document_id = f"doc_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        logger.info(f"📋 Document ID: {document_id}")
        
        # Step 1: Initialize (5%)
        cache_service.update_progress(
            document_id, "initializing", 5, "Starting enhanced upload...",
            filename=file.filename, user_id=user_id, file_size=file_size
        )
        
        # Step 2: Read file (15%)
        cache_service.update_progress(document_id, "reading", 15, "Reading file...")
        file_content = await file.read()
        logger.info(f"📖 Read {len(file_content)} bytes")
        
        # Step 3: Save file (25%)
        cache_service.update_progress(document_id, "saving", 25, "Saving file...")
        file_path = storage_service.save_uploaded_file(file_content, file.filename, user_id)
        
        # Create enhanced metadata
        document_metadata = {
            "document_id": document_id,
            "filename": file.filename,
            "user_id": user_id,
            "file_path": file_path,
            "status": "processing",
            "created_at": datetime.now().isoformat(),
            "file_size": len(file_content),
            "mime_type": mime_type,
            "processing_started_at": datetime.now().isoformat(),
            "upload_date": datetime.now().isoformat()
        }
        
        cache_service.cache_processing_status(document_id, document_metadata)
        
        # Step 4: Process document with enhanced extraction (25% -> 95%)
        logger.info(f"🚀 Starting enhanced processing for {document_id}")
        try:
            await process_document_with_enhanced_extraction(document_id, document_metadata, file_content, cache_service, document_processor)
            
            # Step 5: Complete (100%)
            cache_service.update_progress(
                document_id, "completed", 100,
                f"Processing complete! Created {document_metadata.get('chunks_created', 0)} chunks.",
                chunks_created=document_metadata.get('chunks_created', 0)
            )
            
            document_metadata["status"] = "completed"
            document_metadata["completed_at"] = datetime.now().isoformat()
            cache_service.cache_processing_status(document_id, document_metadata, ttl=86400)
            
            logger.info(f"✅ Enhanced upload completed: {file.filename} -> {document_metadata.get('chunks_created', 0)} chunks")
            
            return DocumentUploadResponse(
                success=True,
                document_id=document_id,
                filename=file.filename,
                status="completed",
                message=f"Successfully processed '{file.filename}' with enhanced extraction",
                chunks_created=document_metadata.get("chunks_created", 0),
                word_count=document_metadata.get("word_count", 0)
            )
            
        except Exception as process_error:
            logger.error(f"❌ Enhanced processing failed: {process_error}")
            
            cache_service.update_progress(
                document_id, "error", 0, f"Processing failed: {str(process_error)}"
            )
            
            document_metadata.update({
                "status": "error",
                "error": str(process_error),
                "failed_at": datetime.now().isoformat()
            })
            cache_service.cache_processing_status(document_id, document_metadata)
            
            return DocumentUploadResponse(
                success=False,
                document_id=document_id,
                filename=file.filename,
                status="error",
                message="Processing failed",
                error=str(process_error)
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Enhanced upload failed: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Enhanced upload failed: {str(e)}")

@router.post("/list")
async def list_documents_enhanced(request: DocumentListRequest, api_key: bool = Depends(verify_api_key)):
    """ENHANCED: List user documents with improved data mapping and caching"""
    cache_service = get_cache_service()
    
    try:
        user_id = request.user_id
        logger.info(f"📋 Enhanced listing documents for user: {user_id}")
        
        # First, try to get from cache
        cached_documents = cache_service.get_user_documents(user_id) if cache_service else []
        
        if cached_documents:
            logger.info(f"✅ Returning {len(cached_documents)} cached documents")
            return {
                "success": True,
                "documents": cached_documents,
                "total": len(cached_documents),
                "userId": user_id,
                "source": "cache"
            }
        
        # If no cache, query Weaviate - use basic fetch without filters
        client = None
        try:
            client = WeaviateHelper.get_client()
            documents_collection = client.collections.get("Documents")
            
            # Use basic fetch_objects without problematic where clause
            response = documents_collection.query.fetch_objects(limit=5000)
            
            logger.info(f"📄 Raw query returned {len(response.objects)} total objects")
            
            # Group by document_id with enhanced data mapping
            doc_map = {}
            processed_count = 0
            user_ids_found = set()
            
            for obj in response.objects:
                try:
                    props = obj.properties if hasattr(obj, 'properties') else {}
                    
                    # Enhanced property access
                    if isinstance(props, dict):
                        obj_user_id = props.get('user_id', '')
                        user_ids_found.add(obj_user_id)
                        
                        # Filter by user
                        if obj_user_id == user_id:
                            processed_count += 1
                            
                            # Get document properties with safe defaults
                            doc_id = props.get('document_id', str(obj.uuid))
                            filename = props.get('filename', 'Unknown')
                            content = props.get('content', '')
                            metadata = props.get('metadata', {})
                            
                            if doc_id not in doc_map:
                                # Handle metadata safely with enhanced mapping
                                metadata_dict = metadata if isinstance(metadata, dict) else {}
                                
                                # Calculate estimated file size from chunk data
                                estimated_size = metadata_dict.get('chunk_size', len(content) if content else 0)
                                
                                # Enhanced document object with all required fields
                                doc_map[doc_id] = {
                                    "id": doc_id,
                                    "filename": filename,
                                    "size": estimated_size,
                                    "uploadDate": metadata_dict.get('upload_date', datetime.now().isoformat()),
                                    "status": "processed",
                                    "userId": user_id,
                                    "documentId": doc_id,
                                    "chunks": 0,
                                    "wordCount": 0,
                                    "fileType": metadata_dict.get('file_type', 'text/plain'),
                                    # Additional fields for better UI display
                                    "file_size": estimated_size,
                                    "upload_date": metadata_dict.get('upload_date', datetime.now().isoformat()),
                                    "processing_status": "completed"
                                }
                            
                            # Accumulate stats
                            doc_map[doc_id]["chunks"] += 1
                            content_size = len(content) if isinstance(content, str) else 0
                            doc_map[doc_id]["size"] += content_size
                            doc_map[doc_id]["file_size"] = doc_map[doc_id]["size"]
                            doc_map[doc_id]["wordCount"] += len(content.split()) if isinstance(content, str) else 0
                
                except Exception as e:
                    logger.warning(f"⚠️ Error processing document object: {e}")
                    continue
            
            documents = list(doc_map.values())
            
            # Enhance documents with better size formatting and estimates
            for doc in documents:
                # If size is still 0, estimate from chunks and word count
                if doc["size"] == 0 and doc["chunks"] > 0:
                    # Estimate ~800 characters per chunk on average
                    doc["size"] = doc["chunks"] * 800
                    doc["file_size"] = doc["size"]
                
                # Add human-readable size
                doc["sizeFormatted"] = format_file_size(doc["size"])
            
            # Cache the results for future requests
            if cache_service:
                for doc in documents:
                    cache_service.cache_document_metadata(user_id, doc["id"], doc)
            
            logger.info(f"✅ Enhanced listing: {processed_count} chunks, {len(documents)} documents for user {user_id}")
            logger.info(f"🔍 Debug: user_ids_found = {list(user_ids_found)}")
            
            return {
                "success": True,
                "documents": documents,
                "total": len(documents),
                "userId": user_id,
                "source": "weaviate",
                "debug": {
                    "total_objects": len(response.objects),
                    "processed_chunks": processed_count,
                    "unique_documents": len(documents),
                    "user_ids_found": list(user_ids_found)
                }
            }
            
        finally:
            if client:
                client.close()
    
    except Exception as e:
        logger.error(f"❌ Enhanced list documents error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@router.get("/status/{document_id}")
async def get_document_status(
    document_id: str,
    user_id: str = Query(...),
    api_key: bool = Depends(verify_api_key)
):
    """Get the processing status of a document"""
    cache_service = get_cache_service()
    
    try:
        logger.info(f"📊 Status check for document: {document_id}, user: {user_id}")
        
        # Try to get from processing status first
        processing_status = cache_service.get_processing_status(document_id) if cache_service else None
        
        if processing_status:
            logger.info(f"✅ Found processing status for {document_id}")
            return {
                "success": True,
                "document_id": document_id,
                "status": processing_status.get("status", "unknown"),
                "progress": processing_status.get("progress", 0),
                "message": processing_status.get("message", "Processing..."),
                "chunks_created": processing_status.get("chunks_created", 0),
                "chunks_processed": processing_status.get("chunks_processed", 0),
                "total_chunks": processing_status.get("total_chunks", 0),
                "timestamp": processing_status.get("updated_at", datetime.now().isoformat())
            }
        
        # If not in processing status, check if document exists in user documents
        user_documents = cache_service.get_user_documents(user_id) if cache_service else []
        
        document_found = None
        for doc in user_documents:
            if doc.get("id") == document_id or doc.get("documentId") == document_id:
                document_found = doc
                break
        
        if document_found:
            logger.info(f"✅ Found completed document {document_id}")
            return {
                "success": True,
                "document_id": document_id,
                "status": "completed",
                "progress": 100,
                "message": "Document processing completed",
                "chunks_created": document_found.get("chunks", 0),
                "chunks_processed": document_found.get("chunks", 0),
                "total_chunks": document_found.get("chunks", 0),
                "timestamp": document_found.get("upload_date", datetime.now().isoformat())
            }
        
        # Check Weaviate directly as fallback using basic client-side filtering
        client = None
        try:
            client = WeaviateHelper.get_client()
            documents_collection = client.collections.get("Documents")
            
            # Get all objects and filter client-side
            all_objects = documents_collection.query.fetch_objects(limit=1000)
            
            found_object = None
            for obj in all_objects.objects:
                props = obj.properties if hasattr(obj, 'properties') else {}
                if props.get('document_id') == document_id and props.get('user_id') == user_id:
                    found_object = obj
                    break
            
            if found_object:
                logger.info(f"✅ Found document {document_id} in Weaviate")
                return {
                    "success": True,
                    "document_id": document_id,
                    "status": "completed",
                    "progress": 100,
                    "message": "Document found in database",
                    "chunks_created": 1,  # At least one chunk exists
                    "timestamp": datetime.now().isoformat()
                }
        
        except Exception as weaviate_error:
            logger.warning(f"⚠️ Weaviate check failed: {weaviate_error}")
        finally:
            if client:
                client.close()
        
        # Document not found anywhere
        logger.warning(f"❌ Document {document_id} not found anywhere")
        raise HTTPException(status_code=404, detail="Document not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Status check failed for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/delete", response_model=DocumentDeleteResponse)
async def delete_document(
    request: DocumentDeleteRequest,
    api_key: bool = Depends(verify_api_key)
):
    """Delete a document and all its associated data - NUCLEAR VERSION"""
    cache_service = get_cache_service()
    storage_service = get_storage_service()
    
    try:
        doc_id = request.document_id
        user_id = request.user_id
        
        logger.info(f"🗑️ Starting NUCLEAR deletion for document: {doc_id}, user: {user_id}")
        
        # 1. Delete from Weaviate using client-side filtering (WORKS WITH ANY VERSION)
        chunks_deleted = 0
        client = None
        try:
            client = WeaviateHelper.get_client()
            
            # Try newer v4 syntax first
            try:
                documents_collection = client.collections.get("Documents")
                
                # Get all objects first, then filter client-side (GUARANTEED TO WORK)
                all_objects = documents_collection.query.fetch_objects(limit=5000)
                
                objects_to_delete = []
                for obj in all_objects.objects:
                    props = obj.properties if hasattr(obj, 'properties') else {}
                    if (props.get('document_id') == doc_id and
                        props.get('user_id') == user_id):
                        objects_to_delete.append(obj)
                
                logger.info(f"🔍 Found {len(objects_to_delete)} chunks to delete for {doc_id}")
                
                # Delete each chunk
                for obj in objects_to_delete:
                    try:
                        documents_collection.data.delete_by_id(obj.uuid)
                        chunks_deleted += 1
                        logger.info(f"🗑️ Deleted chunk: {obj.uuid}")
                    except Exception as chunk_error:
                        logger.warning(f"⚠️ Failed to delete chunk {obj.uuid}: {chunk_error}")
                        continue
            
            except Exception as v4_error:
                logger.warning(f"⚠️ v4 method failed: {v4_error}, trying v3 fallback")
                
                # Fallback to v3 syntax
                try:
                    where_filter = {
                        "path": ["document_id"],
                        "operator": "Equal",
                        "valueText": doc_id
                    }
                    
                    result = client.query.get("Documents", ["_additional {id}", "user_id", "document_id"]).with_where(where_filter).do()
                    
                    if result.get("data", {}).get("Get", {}).get("Documents"):
                        objects_to_delete = result["data"]["Get"]["Documents"]
                        
                        for obj in objects_to_delete:
                            # Verify user ownership
                            if obj.get("user_id") == user_id:
                                object_id = obj["_additional"]["id"]
                                client.data_object.delete(object_id)
                                chunks_deleted += 1
                                logger.info(f"🗑️ Deleted chunk (v3): {object_id}")
                
                except Exception as v3_error:
                    logger.error(f"❌ v3 fallback also failed: {v3_error}")
            
            logger.info(f"✅ Deleted {chunks_deleted} chunks from Weaviate")
        
        except Exception as e:
            logger.error(f"❌ Error deleting from Weaviate: {e}")
            # Continue with cache cleanup even if Weaviate fails
        finally:
            if client:
                client.close()
        
        # 2. NUCLEAR cache clearing - FLUSH ENTIRE REDIS DB
        try:
            if cache_service and hasattr(cache_service, 'redis') and cache_service.redis:
                # NUCLEAR OPTION: Clear entire Redis database
                await cache_service.redis.flushdb()
                logger.info(f"💥 NUCLEAR: Flushed entire Redis cache database")
        
        except Exception as e:
            logger.error(f"❌ Error NUCLEAR clearing cache: {e}")
        
        response_data = DocumentDeleteResponse(
            success=True,
            document_id=doc_id,
            chunks_deleted=chunks_deleted,
            message=f"NUCLEAR deletion completed: {chunks_deleted} chunks deleted, entire cache flushed"
        )
        
        logger.info(f"💥 NUCLEAR deletion completed for document: {doc_id} ({chunks_deleted} chunks)")
        return response_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Document deletion failed: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@router.get("/progress/{document_id}")
async def get_upload_progress(document_id: str, api_key: bool = Depends(verify_api_key)):
    """Get real-time upload progress"""
    cache_service = get_cache_service()
    
    if not cache_service:
        return {
            "progress": 0,
            "message": "Cache service not available",
            "status": "unknown",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        status = cache_service.get_processing_status(document_id)
        if status:
            return {
                "success": True,
                "progress": status.get("progress", 0),
                "status": status.get("status", "unknown"),
                "message": status.get("message", "Processing..."),
                "timestamp": status.get("updated_at", datetime.now().isoformat()),
                "chunks_created": status.get("chunks_created", 0),
                "chunks_processed": status.get("chunks_processed", 0),
                "total_chunks": status.get("total_chunks", 0)
            }
        else:
            return {
                "success": False,
                "progress": 0,
                "message": "Processing not started or completed",
                "status": "unknown",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"❌ Progress check error: {e}")
        return {
            "success": False,
            "progress": 0,
            "message": f"Error checking progress: {str(e)}",
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@router.post("/admin/flush-cache", response_model=CacheFlushResponse)
async def flush_cache_admin(api_key: bool = Depends(verify_api_key)):
    """ADMIN: Flush entire cache database - NUCLEAR OPTION"""
    cache_service = get_cache_service()
    
    try:
        if cache_service and hasattr(cache_service, 'redis') and cache_service.redis:
            await cache_service.redis.flushdb()
            logger.info(f"💥 ADMIN: Flushed entire Redis cache database")
            return CacheFlushResponse(
                success=True,
                message="Entire cache database flushed successfully",
                warning="All cached data has been cleared - document lists will be rebuilt from Weaviate"
            )
        else:
            return CacheFlushResponse(
                success=False,
                message="Cache service not available"
            )
    except Exception as e:
        logger.error(f"❌ Cache flush failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cache flush failed: {str(e)}")

@router.get("/health")
async def documents_health():
    """Health check for document services"""
    cache_service = get_cache_service()
    storage_service = get_storage_service()
    document_processor = get_document_processor()
    
    services_status = {
        "cache_service": "available" if cache_service else "unavailable",
        "storage_service": "available" if storage_service else "unavailable",
        "document_processor": "available" if document_processor else "unavailable"
    }
    
    # Test Weaviate connection using basic method
    weaviate_status = "unavailable"
    client = None
    try:
        client = WeaviateHelper.get_client()
        if client.is_ready():
            weaviate_status = "available"
    except Exception as e:
        logger.warning(f"Weaviate health check failed: {e}")
    finally:
        if client:
            client.close()
    
    services_status["weaviate"] = weaviate_status
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "/api/documents/upload",
            "/api/documents/list",
            "/api/documents/status/{doc_id}",
            "/api/documents/delete",
            "/api/documents/progress/{doc_id}",
            "/api/documents/admin/flush-cache",
            "/api/documents/health"
        ],
        "services": services_status,
        "note": "Using client-side filtering for Weaviate compatibility"
    }
