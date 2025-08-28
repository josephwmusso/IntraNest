#!/bin/bash
# fix_env_vars.sh - Add missing environment variables

cd /home/ec2-user/IntraNest2.0/backend

echo "🔧 Adding missing environment variables to .env..."

# Add the missing WEAVIATE variables that should already exist
cat >> .env << 'EOF'

# Ensure Weaviate variables are defined (if not already)
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=b8f2c4e8a9d3f7e1b5c9a6e2f8d4b7c3e9a5f1d8b2c6e9f3a7b4e8c2d6f9a3b5c8
EOF

echo "✅ Environment variables updated"

# Also let's create a quick fix for the main.py to handle this better
echo "🔧 Adding safety check to main.py..."

# Create a patch to add the missing variables at the top of the document management section
cat > temp_env_fix.py << 'EOF'
# Add this at the beginning of the document management section in main.py

# Ensure required environment variables are available
if 'WEAVIATE_URL' not in globals():
    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "b8f2c4e8a9d3f7e1b5c9a6e2f8d4b7c3e9a5f1d8b2c6e9f3a7b4e8c2d6f9a3b5c8")
EOF

# Insert this fix into main.py right after the document management imports
sed -i '/# === DOCUMENT MANAGEMENT IMPORTS ===/a\\n# Ensure required environment variables are available\nif "WEAVIATE_URL" not in globals():\n    WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")\n    WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY", "b8f2c4e8a9d3f7e1b5c9a6e2f8d4b7c3e9a5f1d8b2c6e9f3a7b4e8c2d6f9a3b5c8")\n' main.py

echo "✅ Safety check added to main.py"

rm temp_env_fix.py

echo ""
echo "🎉 Fix complete! The document processing should work now."
echo ""
echo "🔄 Restart your backend server:"
echo "  uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
echo ""
echo "Then test again:"
echo "  python3 test_upload.py"
