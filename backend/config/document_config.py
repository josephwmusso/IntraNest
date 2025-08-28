#!/usr/bin/env python3
"""
Document configuration constants for IntraNest 2.0
"""

class DocumentConfig:
    """Document management configuration"""
    STORAGE_TYPE = "local"
    UPLOAD_DIR = "/tmp/intranest_uploads"
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'text/html',
        'text/markdown',
        'application/json'
    }
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
