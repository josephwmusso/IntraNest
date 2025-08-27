#!/bin/bash
# Start necessary Docker containers

# Start Weaviate if it exists and is not running
if docker ps -a | grep -q "intranest-weaviate"; then
    if ! docker ps | grep -q "intranest-weaviate"; then
        echo "Starting Weaviate container..."
        docker start intranest-weaviate
        sleep 5
    fi
fi

# Check if Weaviate is responding
if curl -s http://localhost:8080/v1/.well-known/ready | grep -q "true"; then
    echo "Weaviate is ready"
else
    echo "Weaviate is not responding"
fi
