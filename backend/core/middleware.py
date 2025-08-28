#!/usr/bin/env python3
"""
Middleware configuration for IntraNest 2.0
"""

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from config.settings import get_settings

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/intranest.log') if os.path.exists('/tmp') else logging.StreamHandler()
    ]
)

def setup_middleware(app: FastAPI):
    """Setup all middleware for the FastAPI app"""
    
    # Parse CORS origins from string
    cors_origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
    
    # GZip middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
