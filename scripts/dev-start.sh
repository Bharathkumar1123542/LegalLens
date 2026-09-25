#!/bin/bash
# LegalLens Development Stack Startup Script
# Starts all services with Docker Compose and performs initial setup

set -e

echo "🚀 Starting LegalLens Development Stack..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found!"
    echo "📝 Copying .env.example to .env..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
    echo "   - ANTHROPIC_API_KEY (required)"
    echo "   - VOYAGE_API_KEY (required)"
    echo "   - JWT_SECRET (generate with: openssl rand -hex 32)"
    echo ""
    read -p "Press Enter after you've updated .env with your keys..."
fi

# Check for required API keys
source .env
if [[ "$ANTHROPIC_API_KEY" == *"your-key-here"* ]] || [[ -z "$ANTHROPIC_API_KEY" ]]; then
    echo "❌ ERROR: ANTHROPIC_API_KEY not set in .env"
    echo "   Get your key from: https://console.anthropic.com/"
    exit 1
fi

if [[ "$VOYAGE_API_KEY" == *"your-key-here"* ]] || [[ -z "$VOYAGE_API_KEY" ]]; then
    echo "❌ ERROR: VOYAGE_API_KEY not set in .env"
    echo "   Get your key from: https://dash.voyageai.com/"
    exit 1
fi

if [[ "$JWT_SECRET" == *"your-"* ]] || [[ -z "$JWT_SECRET" ]]; then
    echo "❌ ERROR: JWT_SECRET not set in .env"
    echo "   Generate with: openssl rand -hex 32"
    exit 1
fi

echo "✅ Environment configuration validated"
echo ""

# Start Docker Compose
echo "🐳 Starting Docker services..."
cd infra
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
echo "   This may take 30-60 seconds on first run..."

# Wait for API to be healthy
max_attempts=60
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo "✅ All services are running!"
        break
    fi
    attempt=$((attempt + 1))
    echo -n "."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo ""
    echo "❌ Services failed to start. Check logs with:"
    echo "   docker-compose -f infra/docker-compose.yml logs"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ LegalLens Development Stack is Ready!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Services:"
echo "   API (FastAPI):      http://localhost:8000"
echo "   API Docs (Swagger): http://localhost:8000/docs"
echo "   PostgreSQL:         localhost:5432"
echo "   Redis:              localhost:6379"
echo "   MinIO Console:      http://localhost:9001"
echo "   MinIO S3 API:       http://localhost:9000"
echo ""
echo "🔑 MinIO Credentials:"
echo "   Username: minioadmin"
echo "   Password: minioadmin"
echo ""
echo "📦 Docker Services:"
echo "   postgres:  PostgreSQL 16 + pgvector"
echo "   redis:     Redis 7"
echo "   minio:     S3-compatible storage"
echo "   api:       FastAPI backend"
echo "   worker:    Celery worker (async tasks)"
echo "   migrate:   Database migrations (ran automatically)"
echo ""
echo "💡 Useful Commands:"
echo "   View logs:        docker-compose -f infra/docker-compose.yml logs -f"
echo "   View API logs:    docker-compose -f infra/docker-compose.yml logs -f api"
echo "   View worker logs: docker-compose -f infra/docker-compose.yml logs -f worker"
echo "   Stop services:    docker-compose -f infra/docker-compose.yml down"
echo "   Restart API:      docker-compose -f infra/docker-compose.yml restart api"
echo "   Run migrations:   docker-compose -f infra/docker-compose.yml run migrate"
echo "   Shell into API:   docker-compose -f infra/docker-compose.yml exec api sh"
echo ""
echo "🧪 Test the API:"
echo "   curl http://localhost:8000/health"
echo "   # Should return: {\"status\":\"ok\"}"
echo ""
echo "📚 Next Steps:"
echo "   1. Visit http://localhost:8000/docs for API documentation"
echo "   2. Register a user: POST /api/v1/auth/register"
echo "   3. Upload a document: POST /api/v1/documents"
echo "   4. Check the implementation plan: .context/implementation-plan.md"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
