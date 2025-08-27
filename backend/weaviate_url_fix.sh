#!/bin/bash
# weaviate_url_fix.sh - Fix Weaviate URL parsing issue

cd /home/ec2-user/IntraNest2.0/backend

echo "🔧 Fixing Weaviate URL parsing issue..."

# Check current Weaviate URL in .env
echo "Current WEAVIATE_URL in .env:"
grep "WEAVIATE_URL" .env || echo "Not found in .env"

# Let's also check what's in the existing main.py
echo ""
echo "Checking existing WEAVIATE_URL definition in main.py..."
grep -n "WEAVIATE_URL" main.py | head -5

# The issue is likely in how we're parsing the URL
# Let's create a more robust fix by updating the store_chunks_simple function

echo ""
echo "🔧 Creating a fixed version of the Weaviate connection..."

# Create a patch file to fix the Weaviate connection
cat > weaviate_fix_patch.py << 'EOF'
# Fixed Weaviate connection function - replace the existing one

async def store_chunks_simple(chunks: List[Dict]) -> int:
    """Store chunks in Weaviate with fixed URL parsing"""
    
    # Get Weaviate URL and clean it properly
    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY", "b8f2c4e8a9d3f7e1b5c9a6e2f8d4b7c3e9a5f1d8b2c6e9f3a7b4e8c2d6f9a3b5c8")
    
    # Parse URL properly - remove protocol and extract host/port
    if "://" in weaviate_url:
        host_part = weaviate_url.split("://")[1]
    else:
        host_part = weaviate_url
    
    # Handle host:port format
    if ":" in host_part:
        host, port = host_part.split(":", 1)
        # Make sure port is just the port number
        port = port.split("/")[0]  # Remove any path after port
    else:
        host = host_part
        port = "8080"
    
    print(f"Connecting to Weaviate: {host}:{port}")
    
    try:
        client = weaviate.connect_to_local(
            host=host,
            port=int(port),
            auth_credentials=weaviate.auth.AuthApiKey(weaviate_api_key) if weaviate_api_key else None
        )
        
        documents_collection = client.collections.get("Documents")
        success_count = 0
        
        for chunk in chunks:
            try:
                documents_collection.data.insert(chunk)
                success_count += 1
                print(f"✅ Inserted chunk {chunk['chunk_id']}")
            except Exception as e:
                print(f"⚠️  Failed to insert chunk {chunk.get('chunk_id', '?')}: {e}")
        
        print(f"📊 Successfully stored {success_count}/{len(chunks)} chunks")
        return success_count
        
    except Exception as e:
        print(f"❌ Weaviate connection failed: {e}")
        raise
    finally:
        try:
            client.close()
        except:
            pass
EOF

# Now let's replace the function in main.py
echo "🔄 Updating main.py with fixed Weaviate connection..."

# Create a backup first
cp main.py main.py.weaviate_backup

# Use Python to replace the function more reliably
python3 << 'PYTHON_SCRIPT'
import re

# Read the current main.py
with open('main.py', 'r') as f:
    content = f.read()

# Read the new function
with open('weaviate_fix_patch.py', 'r') as f:
    new_function = f.read().strip()

# Remove the comment line from new function
new_function = new_function.replace('# Fixed Weaviate connection function - replace the existing one\n\n', '')

# Find and replace the existing store_chunks_simple function
pattern = r'async def store_chunks_simple\(.*?\n.*?finally:\s*\n.*?client\.close\(\)\s*\n.*?pass'
replacement = new_function

# Use re.DOTALL to match across multiple lines
updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write back to main.py
with open('main.py', 'w') as f:
    f.write(updated_content)

print("✅ Function replaced successfully")
PYTHON_SCRIPT

# Clean up
rm weaviate_fix_patch.py

echo "✅ Weaviate connection fix applied!"

echo ""
echo "🔄 Please restart your backend server:"
echo "  uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
echo ""
echo "Then test again:"
echo "  python3 test_upload.py"
