# config/conversational_settings.py
"""
Separate configuration for conversational RAG features
This avoids modifying the existing settings.py
"""

import os
from typing import Dict, Any

def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    # Set environment variable
                    os.environ[key] = value
        print(f"✅ Loaded {env_file} for conversational config")
    else:
        print(f"⚠️  {env_file} not found")

def get_conversational_config() -> Dict[str, Any]:
    """Get conversational RAG configuration from environment variables"""
    
    # Always load .env file first
    load_env_file()
    
    config = {
        # Redis Configuration
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "cache_ttl": int(os.getenv("CACHE_TTL", "3600")),
        "short_term_limit": int(os.getenv("SHORT_TERM_LIMIT", "10")),
        
        # Memory Management
        "summary_threshold": int(os.getenv("SUMMARY_THRESHOLD", "5")),
        "max_context_messages": int(os.getenv("MAX_CONTEXT_MESSAGES", "10")),
        
        # Query Rewriting
        "rewrite_model": os.getenv("REWRITE_MODEL", "gpt-3.5-turbo"),
        "classification_model": os.getenv("CLASSIFICATION_MODEL", "gpt-3.5-turbo"),
        
        # RAG Configuration
        "response_model": os.getenv("RESPONSE_MODEL", "gpt-4"),
        "max_retrieved_docs": int(os.getenv("MAX_RETRIEVED_DOCS", "5")),
        "hybrid_alpha": float(os.getenv("HYBRID_ALPHA", "0.7")),
        "context_window_limit": int(os.getenv("CONTEXT_WINDOW_LIMIT", "4000")),
        
        # Database
        "database_url": os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./intranest_conversations.db"),
        
        # OpenAI and Weaviate (from existing settings)
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "weaviate_url": os.getenv("WEAVIATE_URL", "http://localhost:8080"),
        "weaviate_api_key": os.getenv("WEAVIATE_API_KEY")
    }
    
    # Debug output
    if config["openai_api_key"]:
        print(f"✅ OpenAI API key loaded (length: {len(config['openai_api_key'])})")
    else:
        print("❌ OpenAI API key not found!")
        print("Available env vars:", [k for k in os.environ.keys() if 'OPENAI' in k])
    
    return config
