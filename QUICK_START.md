# LegalLens Quick Start Guide

Get LegalLens up and running in 15 minutes.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 16+ with pgvector extension
- Redis
- S3-compatible storage (AWS S3 or MinIO)
- Anthropic API key
- Voyage AI API key

---

## Option 1: Quick Test (No Docker)

### Step 1: Install Dependencies

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your values:
# - DATABASE_URL=postgresql+asyncpg://user:pass@localhost/legallens
# - REDIS_URL=redis://localhost:6379/0
# - S3_BUCKET=legallens
# - ANTHROPIC_API_KEY=sk-ant-...
# - VOYAGE_API_KEY=pa-...
# - JWT_SECRET=<generate-256-bit-secret>
```

### Step 3: Setup Database

```bash
# Create database and enable pgvector
psql -U postgres
CREATE DATABASE legallens;
\c legallens
CREATE EXTENSION vector;
\q

# Run migrations
alembic upgrade head
```

### Step 4: Start API Server

```bash
uvicorn app.main:app --reload --port 8000
```

### Step 5: Test the API

Open http://localhost:8000/docs to access Swagger UI.

**Test Flow**:
1. POST `/auth/register` - Create account
2. POST `/auth/login` - Get JWT token
3. Click "Authorize" button, paste token
4. POST `/documents` - Upload a PDF
5. GET `/documents/{id}/status` - Wait for status=ready
6. POST `/documents/{id}/simplify` - Get plain language version
7. POST `/documents/{id}/extract-clauses` - Extract clauses
8. GET `/documents/{id}/clauses` - View extracted clauses
9. POST `/documents/{id}/chat/sessions` - Start chat
10. POST `/chat/sessions/{id}/messages` - Ask questions

---

## Option 2: Docker Compose (Recommended)

### Step 1: Configure Environment

```bash
# Create .env file in project root
cat > .env << EOF
# Database
POSTGRES_USER=legallens
POSTGRES_PASSWORD=legallens
POSTGRES_DB=legallens
DATABASE_URL=postgresql+asyncpg://legallens:legallens@postgres:5432/legallens

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# S3/MinIO
S3_BUCKET=legallens
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin

# API Keys (add your real keys)
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...

# JWT
JWT_SECRET=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256

# App
ENVIRONMENT=development
EOF
```

### Step 2: Start Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL with pgvector
- Redis
- MinIO (S3-compatible storage)
- LegalLens API

### Step 3: Run Migrations

```bash
docker-compose exec api alembic upgrade head
```

### Step 4: Create MinIO Bucket

```bash
# Access MinIO console at http://localhost:9001
# Login: minioadmin / minioadmin
# Create bucket named "legallens"

# Or via CLI:
docker-compose exec minio mc alias set myminio http://localhost:9000 minioadmin minioadmin
docker-compose exec minio mc mb myminio/legallens
```

### Step 5: Test

Visit http://localhost:8000/docs

---

## Option 3: Manual Services (For Development)

If you want to run services separately:

### Terminal 1: PostgreSQL
```bash
docker run -d \
  --name legallens-postgres \
  -e POSTGRES_DB=legallens \
  -e POSTGRES_USER=legallens \
  -e POSTGRES_PASSWORD=legallens \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Enable pgvector
docker exec -it legallens-postgres psql -U legallens -d legallens -c "CREATE EXTENSION vector;"
```

### Terminal 2: Redis
```bash
docker run -d \
  --name legallens-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### Terminal 3: MinIO
```bash
docker run -d \
  --name legallens-minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Create bucket
docker exec legallens-minio mc alias set myminio http://localhost:9000 minioadmin minioadmin
docker exec legallens-minio mc mb myminio/legallens
```

### Terminal 4: API Server
```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Terminal 5: Celery Worker (Optional)
```bash
cd apps/api
source .venv/bin/activate
celery -A app.workers worker --loglevel=info
```

---

## Testing Your Setup

### 1. Health Check
```bash
curl http://localhost:8000/health
# Should return: {"status":"ok","environment":"development"}
```

### 2. Register User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!",
    "full_name": "Test User"
  }'
```

### 3. Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123!"
  }'

# Save the access_token from response
```

### 4. Upload Document
```bash
TOKEN="<your-access-token>"

curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/contract.pdf"

# Save document_id from response
```

### 5. Check Status
```bash
DOC_ID="<document-id>"

curl http://localhost:8000/api/v1/documents/$DOC_ID/status \
  -H "Authorization: Bearer $TOKEN"

# Wait until status="ready"
```

### 6. Simplify Document
```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/simplify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reading_level": "plain_english"
  }'
```

### 7. Extract Clauses
```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/extract-clauses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clause_types": [
      "indemnification",
      "termination",
      "payment_terms"
    ]
  }'

# This returns 202 (async processing)
# Poll GET /documents/$DOC_ID/clauses until clauses appear
```

### 8. Chat with Document
```bash
# Create session
SESSION_RESPONSE=$(curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/chat/sessions \
  -H "Authorization: Bearer $TOKEN")

SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.session.id')

# Ask question
curl -X POST http://localhost:8000/api/v1/chat/sessions/$SESSION_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the payment terms in this contract?"
  }'
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill process or use different port
uvicorn app.main:app --port 8001
```

### Database Connection Error
```bash
# Verify PostgreSQL is running
psql -U legallens -d legallens -c "SELECT 1;"

# Check pgvector extension
psql -U legallens -d legallens -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### Redis Connection Error
```bash
# Verify Redis is running
redis-cli ping
# Should return: PONG
```

### MinIO Connection Error
```bash
# Check MinIO is running
curl http://localhost:9000/minio/health/live

# Verify bucket exists
aws s3 ls s3://legallens \
  --endpoint-url http://localhost:9000 \
  --no-verify-ssl
```

### Import Errors
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Verify installations
python -c "import anthropic; print('Anthropic OK')"
python -c "import voyageai; print('Voyage OK')"
python -c "from pgvector.sqlalchemy import Vector; print('pgvector OK')"
```

### Migration Errors
```bash
# Reset database (CAUTION: destroys data)
alembic downgrade base
alembic upgrade head

# Or create fresh database
dropdb legallens
createdb legallens
psql -d legallens -c "CREATE EXTENSION vector;"
alembic upgrade head
```

---

## Next Steps

1. ✅ Verify all services running
2. ✅ Test complete flow with Swagger UI
3. ✅ Upload a real contract PDF
4. ✅ Review extracted clauses
5. ✅ Chat with the document

**Then proceed to**:
- Complete missing features (Celery workers, PDF export)
- Add security hardening (rate limiting, malware scanning)
- Set up CI/CD pipelines
- Deploy to staging

See `implementation-plan.md` for detailed roadmap.

---

## Getting Help

- **Documentation**: See `.context/` directory for architecture, design docs
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Status Summary**: `.context/project-status-summary.md`
- **Implementation Plan**: `.context/implementation-plan.md`

---

## Key Files

```
apps/api/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── core/config.py       # Environment configuration
│   ├── api/v1/              # API endpoints
│   ├── services/            # Business logic
│   ├── models/              # SQLAlchemy ORM models
│   └── prompts/             # LLM prompt templates
├── alembic/                 # Database migrations
├── tests/                   # Test suites
└── requirements.txt         # Python dependencies
```

---

**Ready to start!** 🚀

Pick an option above and get LegalLens running in minutes.
