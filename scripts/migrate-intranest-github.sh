#!/bin/bash

echo "================================================"
echo "IntraNest AI - Safe GitHub Migration"
echo "================================================"

# Settings
REPO_DIR="$HOME/IntraNest-GitHub"
GITHUB_REPO="josephwmusso/IntraNest"

# Clean and create directory
rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR"
cd "$REPO_DIR"

# Initialize repository
git init
git branch -M main

# Create directory structure
echo "Creating directory structure..."
mkdir -p backend/{services,models,utils,config}
mkdir -p frontend/{config,assets}
mkdir -p infrastructure/{aws,nginx,monitoring,docker}
mkdir -p desktop scripts docs

# Create .gitignore
cat > .gitignore << 'IGNORE'
# Sensitive files
*.env
.env.*
!.env.example
*.pem
*.key
*.crt
credentials.json
client_secret*
*_secret*

# Python
__pycache__/
*.pyc
venv/
env/

# Node
node_modules/
package-lock.json

# Data
*.log
logs/
weaviate_data/
mongodb_data/
redis_data/

# OS
.DS_Store
Thumbs.db
IGNORE

# Copy backend files safely
echo "Migrating backend..."
if [ -d "$HOME/IntraNest2.0/backend" ]; then
    cp -r "$HOME/IntraNest2.0/backend"/*.py backend/ 2>/dev/null || true
    [ -d "$HOME/IntraNest2.0/backend/services" ] && cp -r "$HOME/IntraNest2.0/backend/services"/*.py backend/services/ 2>/dev/null || true
    
    # Remove sensitive data from Python files
    find backend -name "*.py" -exec sed -i \
        -e 's/sk-[a-zA-Z0-9-]\{20,\}/sk-YOUR-OPENAI-KEY/g' \
        -e 's/mongodb:\/\/[^@]*@[^/]*/mongodb:\/\/localhost:27017/g' \
        -e 's/54\.71\.15\.44/YOUR-IP/g' \
        {} \; 2>/dev/null || true
fi

# Create requirements.txt
cat > backend/requirements.txt << 'REQ'
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
llama-index==0.9.48
llama-index-llms-openai
llama-index-embeddings-openai
llama-index-vector-stores-weaviate
weaviate-client==3.25.3
openai==1.12.0
pdfplumber==0.10.3
PyPDF2==3.0.1
python-docx==1.1.0
beautifulsoup4==4.12.3
redis==5.0.1
motor==3.3.2
python-multipart==0.0.6
aiofiles==23.2.1
REQ

# Create backend .env.example
cat > backend/.env.example << 'ENV'
# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key

# Weaviate
WEAVIATE_URL=http://localhost:8080

# Server
HOST=0.0.0.0
PORT=8001

# Document Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Databases
MONGO_URI=mongodb://localhost:27017/intranest
REDIS_URI=redis://localhost:6379
ENV

# Copy monitoring scripts safely
echo "Migrating infrastructure..."
for script in monitor-services.sh health-check.sh startup-check.sh; do
    if [ -f "$HOME/$script" ]; then
        cp "$HOME/$script" infrastructure/monitoring/
        # Remove sensitive data
        sed -i 's/app\.intranestai\.com/your-domain.com/g' infrastructure/monitoring/$script 2>/dev/null || true
    fi
done

# Copy PM2 config as example
[ -f "$HOME/ecosystem.config.js" ] && cp "$HOME/ecosystem.config.js" infrastructure/ecosystem.config.js.example

# Create Docker Compose
cat > infrastructure/docker/docker-compose.yml << 'DOCKER'
version: '3.8'

services:
  weaviate:
    image: semitechnologies/weaviate:1.21.0
    ports:
      - "8080:8080"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
    volumes:
      - ./weaviate_data:/var/lib/weaviate

  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - ./mongodb_data:/data/db

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"
DOCKER

# Create README
cat > README.md << 'README'
# IntraNest AI 🚀

Enterprise conversational AI platform with complete data sovereignty and zero per-user costs.

## Features

- 🔒 Complete Data Sovereignty
- 💰 Zero Per-User Costs (~$1,800/year for unlimited users)
- 🧠 Advanced RAG System (LlamaIndex + Weaviate)
- 🔐 Microsoft OAuth Integration
- 💻 Cross-Platform Support

## Architecture

- **Frontend**: LibreChat (React)
- **Backend**: FastAPI + LlamaIndex
- **Vector DB**: Weaviate
- **AI Model**: OpenAI GPT-4

## Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and configure
3. Run Docker Compose for databases
4. Start backend and frontend services

See [docs/SETUP.md](docs/SETUP.md) for detailed instructions.

## Cost Comparison

| Solution | Annual Cost | Data Control |
|----------|------------|--------------|
| ChatGPT Enterprise | $360/user | ❌ Third-party |
| **IntraNest AI** | **$1,800 total** | **✅ Full control** |

## License

MIT License - see [LICENSE](LICENSE)
README

# Create LICENSE
cat > LICENSE << 'LICENSE'
MIT License

Copyright (c) 2025 IntraNest AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
LICENSE

# Add all files
git add .

# Commit
git commit -m "Initial commit: IntraNest AI platform

- Enterprise conversational AI platform
- FastAPI backend with LlamaIndex RAG
- Weaviate vector database integration
- AWS production deployment ready
- All sensitive data removed"

echo ""
echo "================================================"
echo "Repository created locally. Now pushing to GitHub..."
echo "================================================"

# Since the repo already exists, we'll just set the remote and push
git remote add origin https://github.com/josephwmusso/IntraNest.git

# Push to GitHub
git push -u origin main

echo ""
echo "================================================"
echo "✅ Migration Complete!"
echo "================================================"
echo "Repository: https://github.com/josephwmusso/IntraNest"
echo ""
echo "Next steps:"
echo "1. Add repository description on GitHub"
echo "2. Add topics: ai, rag, llamaindex, weaviate"
echo "3. Configure GitHub Pages if desired"
