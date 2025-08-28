#!/usr/bin/env python3
"""
Weaviate helper utilities for IntraNest 2.0
"""

import logging
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class WeaviateHelper:
    """Helper class for Weaviate operations with robust property access"""

    @staticmethod
    def get_client():
        """Get Weaviate client with proper connection"""
        try:
            # Connect without authentication for anonymous access
            client = weaviate.connect_to_local(
                host="localhost",
                port=8080,
                auth_credentials=None  # Anonymous access - no authentication
            )
            
            # Verify connection
            if client.is_ready():
                logger.debug("✅ Weaviate client connected (anonymous access)")
                return client
            else:
                raise Exception("Weaviate is not ready")
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to Weaviate: {e}")
            raise

    @staticmethod
    def safe_get_property(props, prop_name: str, default=''):
        """Safely get property value using multiple access methods"""
        try:
            # Method 1: Dictionary access
            if isinstance(props, dict):
                return props.get(prop_name, default)
            
            # Method 2: Attribute access
            if hasattr(props, prop_name):
                value = getattr(props, prop_name, default)
                return value if value is not None else default
            
            # Method 3: Check if it has __dict__
            if hasattr(props, '__dict__'):
                return props.__dict__.get(prop_name, default)
            
            return default
            
        except Exception as e:
            logger.warning(f"⚠️ Error accessing property {prop_name}: {e}")
            return default

    @staticmethod
    def safe_query_with_filter(collection, user_id: str, limit: int = 1000):
        """Query with user filter - handles different Weaviate versions"""
        try:
            logger.debug(f"🔍 Querying Weaviate for user: {user_id}")
            response = collection.query.fetch_objects(limit=limit)
            
            # Manual filtering with robust property access
            filtered_objects = []
            for obj in response.objects:
                try:
                    props = obj.properties if hasattr(obj, 'properties') else {}
                    obj_user_id = WeaviateHelper.safe_get_property(props, 'user_id', '')
                    
                    if obj_user_id == user_id:
                        filtered_objects.append(obj)
                except Exception as e:
                    logger.warning(f"⚠️ Error filtering object: {e}")
                    continue
            
            response.objects = filtered_objects
            logger.debug(f"✅ Filtered to {len(filtered_objects)} objects for user: {user_id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Weaviate query failed: {e}")
            raise

    @staticmethod
    def setup_weaviate_schema(client):
        """Setup Weaviate schema - simplified for anonymous access"""
        try:
            collections = client.collections.list_all()
            collection_names = [col for col in collections.keys()] if hasattr(collections, 'keys') else [col.name for col in collections]
            
            if "Documents" not in collection_names:
                logger.info("📋 Creating Documents collection...")
                
                # Create collection WITHOUT OpenAI vectorizer (use manual embeddings)
                collection = client.collections.create(
                    name="Documents",
                    # No vectorizer config - we'll provide vectors manually
                    properties=[
                        Property(name="content", data_type=DataType.TEXT),
                        Property(name="filename", data_type=DataType.TEXT),
                        Property(name="user_id", data_type=DataType.TEXT),
                        Property(name="document_id", data_type=DataType.TEXT),
                        Property(name="node_id", data_type=DataType.TEXT),
                        Property(name="chunk_id", data_type=DataType.TEXT),  # Changed to TEXT
                        Property(name="chunk_index", data_type=DataType.INT),
                        Property(name="page_number", data_type=DataType.INT),
                        Property(name="metadata", data_type=DataType.OBJECT)
                    ]
                )
                logger.info("✅ Documents collection created")
            else:
                logger.info("✅ Documents collection already exists")
                
        except Exception as e:
            logger.error(f"❌ Schema setup error: {e}")
            # Try alternative schema creation for older Weaviate versions
            try:
                logger.info("Trying alternative schema creation...")
                schema = {
                    "class": "Documents",
                    "properties": [
                        {"name": "content", "dataType": ["text"]},
                        {"name": "filename", "dataType": ["string"]},
                        {"name": "user_id", "dataType": ["string"]},
                        {"name": "document_id", "dataType": ["string"]},
                        {"name": "node_id", "dataType": ["string"]},
                        {"name": "chunk_id", "dataType": ["string"]},
                        {"name": "chunk_index", "dataType": ["int"]},
                        {"name": "page_number", "dataType": ["int"]},
                        {"name": "metadata", "dataType": ["object"]}
                    ]
                }
                client.schema.create_class(schema)
                logger.info("✅ Documents collection created (v3 method)")
            except Exception as e2:
                logger.error(f"❌ Alternative schema creation also failed: {e2}")
                # Schema might already exist, continue anyway
                pass
