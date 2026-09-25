# LegalLens Development Stack Startup Script (PowerShell)
# Starts all services with Docker Compose and performs initial setup

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting LegalLens Development Stack..." -ForegroundColor Green
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  No .env file found!" -ForegroundColor Yellow
    Write-Host "📝 Copying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env and add your API keys:" -ForegroundColor Yellow
    Write-Host "   - ANTHROPIC_API_KEY (required)" -ForegroundColor Yellow
    Write-Host "   - VOYAGE_API_KEY (required)" -ForegroundColor Yellow
    Write-Host "   - JWT_SECRET (generate with: openssl rand -hex 32)" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter after you've updated .env with your keys"
}

# Load .env file
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

# Check for required API keys
$anthropicKey = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY', 'Process')
if ([string]::IsNullOrEmpty($anthropicKey) -or $anthropicKey -like "*your-key-here*") {
    Write-Host "❌ ERROR: ANTHROPIC_API_KEY not set in .env" -ForegroundColor Red
    Write-Host "   Get your key from: https://console.anthropic.com/" -ForegroundColor Red
    exit 1
}

$voyageKey = [Environment]::GetEnvironmentVariable('VOYAGE_API_KEY', 'Process')
if ([string]::IsNullOrEmpty($voyageKey) -or $voyageKey -like "*your-key-here*") {
    Write-Host "❌ ERROR: VOYAGE_API_KEY not set in .env" -ForegroundColor Red
    Write-Host "   Get your key from: https://dash.voyageai.com/" -ForegroundColor Red
    exit 1
}

$jwtSecret = [Environment]::GetEnvironmentVariable('JWT_SECRET', 'Process')
if ([string]::IsNullOrEmpty($jwtSecret) -or $jwtSecret -like "*your-*") {
    Write-Host "❌ ERROR: JWT_SECRET not set in .env" -ForegroundColor Red
    Write-Host "   Generate with: openssl rand -hex 32" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Environment configuration validated" -ForegroundColor Green
Write-Host ""

# Start Docker Compose
Write-Host "🐳 Starting Docker services..." -ForegroundColor Cyan
Set-Location infra
docker-compose up -d

Write-Host ""
Write-Host "⏳ Waiting for services to be healthy..." -ForegroundColor Yellow
Write-Host "   This may take 30-60 seconds on first run..." -ForegroundColor Yellow

# Wait for API to be healthy
$maxAttempts = 60
$attempt = 0
$healthy = $false

while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host ""
            Write-Host "✅ All services are running!" -ForegroundColor Green
            $healthy = $true
            break
        }
    }
    catch {
        # Service not ready yet
    }
    
    $attempt++
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
}

if (-not $healthy) {
    Write-Host ""
    Write-Host "❌ Services failed to start. Check logs with:" -ForegroundColor Red
    Write-Host "   docker-compose -f infra/docker-compose.yml logs" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✨ LegalLens Development Stack is Ready!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Services:" -ForegroundColor White
Write-Host "   API (FastAPI):      http://localhost:8000"
Write-Host "   API Docs (Swagger): http://localhost:8000/docs"
Write-Host "   PostgreSQL:         localhost:5432"
Write-Host "   Redis:              localhost:6379"
Write-Host "   MinIO Console:      http://localhost:9001"
Write-Host "   MinIO S3 API:       http://localhost:9000"
Write-Host ""
Write-Host "🔑 MinIO Credentials:" -ForegroundColor White
Write-Host "   Username: minioadmin"
Write-Host "   Password: minioadmin"
Write-Host ""
Write-Host "📦 Docker Services:" -ForegroundColor White
Write-Host "   postgres:  PostgreSQL 16 + pgvector"
Write-Host "   redis:     Redis 7"
Write-Host "   minio:     S3-compatible storage"
Write-Host "   api:       FastAPI backend"
Write-Host "   worker:    Celery worker (async tasks)"
Write-Host "   migrate:   Database migrations (ran automatically)"
Write-Host ""
Write-Host "💡 Useful Commands:" -ForegroundColor White
Write-Host "   View logs:        docker-compose -f infra/docker-compose.yml logs -f"
Write-Host "   View API logs:    docker-compose -f infra/docker-compose.yml logs -f api"
Write-Host "   View worker logs: docker-compose -f infra/docker-compose.yml logs -f worker"
Write-Host "   Stop services:    docker-compose -f infra/docker-compose.yml down"
Write-Host "   Restart API:      docker-compose -f infra/docker-compose.yml restart api"
Write-Host "   Run migrations:   docker-compose -f infra/docker-compose.yml run migrate"
Write-Host "   Shell into API:   docker-compose -f infra/docker-compose.yml exec api sh"
Write-Host ""
Write-Host "🧪 Test the API:" -ForegroundColor White
Write-Host "   Invoke-WebRequest -Uri http://localhost:8000/health"
Write-Host "   # Should return: {`"status`":`"ok`"}"
Write-Host ""
Write-Host "📚 Next Steps:" -ForegroundColor White
Write-Host "   1. Visit http://localhost:8000/docs for API documentation"
Write-Host "   2. Register a user: POST /api/v1/auth/register"
Write-Host "   3. Upload a document: POST /api/v1/documents"
Write-Host "   4. Check the implementation plan: .context/implementation-plan.md"
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
