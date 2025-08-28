#!/usr/bin/env python3
"""
Text processing utilities for IntraNest 2.0
"""

import re
import uuid
import mimetypes
from typing import List, Dict
from datetime import datetime
from config.document_config import DocumentConfig

def clean_extracted_text(text: str) -> str:
    """Clean and normalize extracted text"""
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove common PDF artifacts but preserve important characters
    text = re.sub(r'[^\w\s\.,!?;:()\-\'"@#$%^&*+=<>/\\|`~\[\]{}]', '', text)

    # Fix common OCR errors
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    text = text.replace('–', '-').replace('—', '-')
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")

    return text.strip()

def create_chunks_with_progress(text_content: str, filename: str, document_id: str, user_id: str, cache_service, progress_start: int = 40) -> List[Dict]:
    """Create text chunks with progress updates"""
    try:
        if not text_content.strip():
            return []

        chunks = []
        chunk_size = DocumentConfig.CHUNK_SIZE
        overlap = DocumentConfig.CHUNK_OVERLAP

        cache_service.update_progress(
            document_id,
            "chunking",
            progress_start,
            "Breaking document into chunks..."
        )

        # Create chunks
        for i in range(0, len(text_content), chunk_size - overlap):
            chunk_text = text_content[i:i + chunk_size].strip()
            if not chunk_text:
                continue

            chunk_data = {
                "content": chunk_text,
                "filename": filename,
                "user_id": user_id,
                "document_id": document_id,
                "node_id": str(uuid.uuid4()),
                "chunk_id": len(chunks),
                "page_number": 1,
                "metadata": {
                    "upload_date": datetime.now().isoformat(),
                    "file_type": mimetypes.guess_type(filename)[0] or "text/plain",
                    "chunk_size": len(chunk_text),
                    "source": filename
                }
            }
            chunks.append(chunk_data)

        cache_service.update_progress(
            document_id,
            "chunks_created",
            progress_start + 15,
            f"Created {len(chunks)} text chunks"
        )

        return chunks

    except Exception as e:
        raise Exception(f"Chunking failed for {document_id}: {e}")

def generate_tokens(text: str):
    """Generator for streaming tokens"""
    sentences = text.split('. ')
    for i, sentence in enumerate(sentences):
        if i < len(sentences) - 1:
            sentence += '. '
        words = sentence.split(' ')
        for j, word in enumerate(words):
            if j == 0 and i == 0:
                yield word
            else:
                yield f" {word}"
