# LegalLens API — Dockerfile
# architecture.md §4: Docker, ECS Fargate or Kubernetes (prod).
# Build: docker build -t legallens-api .
# Secrets: never baked into image — all from environment at runtime.

FROM python:3.11-slim AS base

# Tesseract OCR runtime (architecture.md §4 — OCR fallback)
# libmagic for magic-byte file validation (code-standards.md security rule)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dependencies layer (cached unless requirements.txt changes) ───────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY app/ ./app/

# Non-root user for least-privilege (security best practice)
RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8000

# health check so docker compose / ECS knows when the container is ready
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
