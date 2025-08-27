# backend/config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    """Application settings with professional configuration management"""
    
    # Application Configuration
    app_name: str = "IntraNest 2.0"
    app_version: str = "2.0.2-conversational"  # Updated for conversational RAG
    debug: bool = False
    environment: str = "production"
    
    # API Authentication
    intranest_api_key: Optional[str] = None
    
    # Weaviate Configuration
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: Optional[str] = None
    
    # OpenAI Configuration
    openai_api_key: str
    openai_organization: Optional[str] = None
    
    # Microsoft OAuth Configuration
    microsoft_client_id: str = "your-client-id"
    microsoft_client_secret: str = "your-client-secret"
    microsoft_tenant_id: str = "your-tenant-id"
    microsoft_redirect_uri: str = "http://localhost:8001/api/auth/callback"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    
    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Document Processing Configuration
    document_chunk_size: int = 1000
    document_chunk_overlap: int = 200
    max_file_size: int = 52428800
    supported_file_types: str = "pdf,docx,txt,html,md"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Performance Configuration
    request_timeout: int = 30
    max_concurrent_requests: int = 10
    rate_limit_per_minute: int = 60
    reload_on_change: bool = True
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Security Configuration
    cors_origins: str = "*"
    allowed_hosts: str = "*"
    
    # Storage Configuration
    storage_type: str = "minio"
    s3_bucket: str = "intranest-documents"
    s3_region: str = "us-west-2"
    s3_access_key: str = "intranest"
    s3_secret_key: str = "intranest123"
    s3_endpoint: str = "http://localhost:9000"
    
    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    class Config:
        """Professional configuration management"""
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # Professional standard: ignore unknown environment variables

# Global settings instance with proper singleton pattern
_settings = None

def get_settings() -> Settings:
    """
    Get application settings using singleton pattern
    
    Returns:
        Settings: Application configuration instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
