#!/usr/bin/env python3
"""
FastAPI dependencies for IntraNest 2.0
"""

from fastapi import HTTPException, Header
from typing import Optional
from config.settings import get_settings
import os

settings = get_settings()
INTRANEST_API_KEY = os.getenv("INTRANEST_API_KEY")

async def verify_api_key(authorization: Optional[str] = Header(None)):
    """Verify API key from Authorization header"""
    if not INTRANEST_API_KEY:
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    provided_key = authorization.replace("Bearer ", "")
    if provided_key != INTRANEST_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True
