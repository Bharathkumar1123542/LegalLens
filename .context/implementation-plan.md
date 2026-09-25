# LegalLens Implementation Plan

**Created**: 2025-01-19  
**Status**: Phases 0-5 Complete, Phases 6-8 Planned  
**Estimated Completion**: 2-3 weeks for MVP, 4-6 weeks for production-ready

---

## Current Status: 75% Complete

### ✅ Completed (Phases 0-5)
- Authentication & document upload
- Text extraction, chunking, embeddings
- Simplification (3 reading levels)
- Clause extraction (10 types, 3 risk levels)
- Document Q&A with RAG
- Comparison engine (2-5 documents)
- Export module (Markdown)
- 25+ API endpoints
- 158+ tests

### 🔧 In Progress (Missing Pieces)
- Celery workers (noted but not implemented)
- PDF/DOCX export rendering
- 6 failing simplification tests
- Docker Compose full stack

### 📋 Remaining (Phases 6-8)
- Security hardening
- Testing to 80% coverage
- CI/CD pipelines
- Production deployment

---

## Phase 6: Complete Missing Features (Priority 1)

**Goal**: Complete deferred MVP features to make the system fully functional  
**Duration**: 3-5 days  
**Priority**: HIGH - Required for MVP

### Task 6.1: Implement Celery Workers (8-12 hours)

**Why**: Currently endpoints return 202 but don't actually process async jobs

**Tasks**:
1. **Celery Configuration** (2 hours)
   - Create `apps/api/app/workers/__init__.py` with Celery app
   - Configure Redis broker and result backend
   - Set up task routing and retry policies
   
   ```python
   # apps/api/app/workers/__init__.py
   from celery import Celery
   from app.core.config import settings
   
   celery_app = Celery(
       "legallens",
       broker=settings.CELERY_BROKER_URL,
       backend=settings.REDIS_URL,
   )
   
   celery_app.conf.update(
       task_serializer="json",
       result_serializer="json",
       accept_content=["json"],
       timezone="UTC",
       enable_utc=True,
       task_track_started=True,
       task_time_limit=1800,  # 30 minutes
       task_soft_time_limit=1500,  # 25 minutes
   )
   ```

2. **Update Comparison Worker** (3 hours)
   - Import Celery app in `comparison_worker.py`
   - Add `@celery_app.task` decorator
   - Update endpoint to call `.delay()`
   - Add status polling mechanism
   
   ```python
   # apps/api/app/workers/comparison_worker.py
   from app.workers import celery_app
   
   @celery_app.task(name="run_comparison", bind=True, max_retries=3)
   def run_comparison_task(self, comparison_job_id: str):
       import asyncio
       from app.services.comparison import run_comparison
       # ... implementation
   ```

3. **Update Export Worker** (3 hours)
   - Similar Celery integration
   - Add export generation task
   - Update endpoint to enqueue job
   
4. **Update API Endpoints** (2 hours)
   - Change from placeholder comments to actual `.delay()` calls
   - Update `/api/v1/comparisons.py`: `comparison_worker.run_comparison_task.delay(job.id)`
   - Update `/api/v1/exports.py`: `export_worker.generate_export_task.delay(export_id)`

5. **Testing** (2 hours)
   - Test Celery worker startup
   - Test job enqueue and processing
   - Test status transitions (queued → running → completed)

**Files to Modify**:
- `apps/api/app/workers/__init__.py` (new)
- `apps/api/app/workers/comparison_worker.py`
- `apps/api/app/workers/export_worker.py`
- `apps/api/app/api/v1/comparisons.py`
- `apps/api/app/api/v1/exports.py`

**Acceptance Criteria**:
- ✅ Celery workers start without errors
- ✅ POST /comparisons enqueues Celery task
- ✅ POST /exports enqueues Celery task
- ✅ GET endpoints show status transitions
- ✅ Jobs complete successfully with results

---

### Task 6.2: PDF/DOCX Export Rendering (6-8 hours)

**Why**: Currently only Markdown export works; need PDF and DOCX for professional use

**Tasks**:
1. **Add Dependencies** (30 minutes)
   - Add to `requirements.txt`:
     ```
     reportlab==4.0.7      # PDF generation
     python-docx==1.1.0    # DOCX generation
     Pillow==10.1.0        # Image support for PDF
     ```
   - Test installation

2. **PDF Renderer** (3 hours)
   - Create `apps/api/app/services/renderers/pdf_renderer.py`
   - Use reportlab to generate PDF from Markdown
   - Support headings, lists, tables
   - Add page numbers and headers
   
   ```python
   # apps/api/app/services/renderers/pdf_renderer.py
   from reportlab.lib.pagesizes import letter
   from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
   from reportlab.lib.styles import getSampleStyleSheet
   
   def render_markdown_to_pdf(markdown_content: str) -> bytes:
       # Convert Markdown to PDF
       # Return PDF bytes
       pass
   ```

3. **DOCX Renderer** (3 hours)
   - Create `apps/api/app/services/renderers/docx_renderer.py`
   - Use python-docx to generate DOCX from Markdown
   - Support formatting, lists, tables
   
   ```python
   # apps/api/app/services/renderers/docx_renderer.py
   from docx import Document
   from docx.shared import Inches, Pt
   
   def render_markdown_to_docx(markdown_content: str) -> bytes:
       # Convert Markdown to DOCX
       # Return DOCX bytes
       pass
   ```

4. **Update Export Service** (1 hour)
   - Modify `apps/api/app/services/export.py`
   - Route to appropriate renderer based on format
   - Update content type headers
   
   ```python
   # In export.py
   if file_format == "pdf":
       from app.services.renderers.pdf_renderer import render_markdown_to_pdf
       content_bytes = render_markdown_to_pdf(markdown_content)
   elif file_format == "docx":
       from app.services.renderers.docx_renderer import render_markdown_to_docx
       content_bytes = render_markdown_to_docx(markdown_content)
   else:  # md
       content_bytes = markdown_content.encode('utf-8')
   ```

5. **Testing** (1.5 hours)
   - Test PDF generation for all export types
   - Test DOCX generation
   - Verify files open correctly in viewers
   - Test with comparison reports (complex formatting)

**Files to Create**:
- `apps/api/app/services/renderers/__init__.py`
- `apps/api/app/services/renderers/pdf_renderer.py`
- `apps/api/app/services/renderers/docx_renderer.py`

**Files to Modify**:
- `apps/api/requirements.txt`
- `apps/api/app/services/export.py`

**Acceptance Criteria**:
- ✅ PDF exports generate and open correctly
- ✅ DOCX exports generate and open correctly
- ✅ Formatting preserved (headings, lists, emphasis)
- ✅ All 4 export types work in all 3 formats

---

### Task 6.3: Fix Failing Simplification Tests (2-3 hours)

**Why**: 6/14 tests fail due to async DB mock issues

**Tasks**:
1. **Review Failing Tests** (30 minutes)
   - Identify the 6 failing tests
   - Understand the async mock pattern needed
   
2. **Apply Async Mock Pattern** (1.5 hours)
   - Update DB mocks to use `async def mock_execute`
   - Apply pattern consistently across all 6 tests
   - Reference working pattern from passing tests
   
   ```python
   # Correct pattern (from passing test)
   mock_result = MagicMock()
   mock_result.scalars.return_value.all.return_value = chunks
   
   async def mock_execute(*args, **kwargs):
       return mock_result
   
   db.execute = mock_execute
   ```

3. **Run Tests** (30 minutes)
   - Run full test suite: `pytest tests/unit/test_simplification.py -v`
   - Verify all 14 tests pass
   - Check no regressions in other test files

4. **Document Pattern** (30 minutes)
   - Add comment in test file explaining async mock pattern
   - Update test documentation

**Files to Modify**:
- `apps/api/tests/unit/test_simplification.py`

**Acceptance Criteria**:
- ✅ All 14 simplification tests pass
- ✅ No regressions in other tests
- ✅ Pattern documented for future reference

---

### Task 6.4: Docker Compose Full Stack (4-6 hours)

**Why**: Need complete local development environment

**Tasks**:
1. **Update Docker Compose** (2 hours)
   - Enhance `infra/docker-compose.yml`
   - Add all services: api, postgres, redis, minio, celery worker
   - Configure networking and volumes
   - Add health checks
   
   ```yaml
   version: '3.8'
   
   services:
     postgres:
       image: pgvector/pgvector:pg16
       environment:
         POSTGRES_DB: legallens
         POSTGRES_USER: legallens
         POSTGRES_PASSWORD: legallens
       volumes:
         - postgres_data:/var/lib/postgresql/data
       healthcheck:
         test: ["CMD", "pg_isready", "-U", "legallens"]
     
     redis:
       image: redis:7-alpine
       healthcheck:
         test: ["CMD", "redis-cli", "ping"]
     
     minio:
       image: minio/minio:latest
       command: server /data --console-address ":9001"
       environment:
         MINIO_ROOT_USER: minioadmin
         MINIO_ROOT_PASSWORD: minioadmin
       volumes:
         - minio_data:/data
     
     api:
       build: ./apps/api
       depends_on:
         - postgres
         - redis
         - minio
       environment:
         DATABASE_URL: postgresql+asyncpg://legallens:legallens@postgres/legallens
         REDIS_URL: redis://redis:6379/0
         CELERY_BROKER_URL: redis://redis:6379/1
         S3_ENDPOINT_URL: http://minio:9000
       ports:
         - "8000:8000"
     
     celery_worker:
       build: ./apps/api
       command: celery -A app.workers worker --loglevel=info
       depends_on:
         - postgres
         - redis
         - minio
       environment:
         # Same as api
   
   volumes:
     postgres_data:
     minio_data:
   ```

2. **Update API Dockerfile** (1 hour)
   - Ensure all dependencies installed
   - Add Tesseract and libmagic
   - Configure non-root user
   - Add health check

3. **Environment File Template** (1 hour)
   - Create `.env.docker` template
   - Document all required variables
   - Add validation script

4. **Startup Script** (1 hour)
   - Create `scripts/dev-start.sh`
   - Run migrations automatically
   - Initialize MinIO buckets
   - Seed test data (optional)
   
   ```bash
   #!/bin/bash
   # scripts/dev-start.sh
   
   # Wait for services
   until pg_isready -h postgres; do sleep 1; done
   
   # Run migrations
   cd /app
   alembic upgrade head
   
   # Create MinIO bucket
   mc alias set myminio http://minio:9000 minioadmin minioadmin
   mc mb myminio/legallens || true
   
   # Start API
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

5. **Documentation** (1 hour)
   - Update README with Docker instructions
   - Add troubleshooting section
   - Document port mappings

**Files to Create**:
- `scripts/dev-start.sh`
- `.env.docker`

**Files to Modify**:
- `infra/docker-compose.yml`
- `apps/api/Dockerfile`
- `README.md`

**Acceptance Criteria**:
- ✅ `docker-compose up` starts all services
- ✅ API accessible at http://localhost:8000
- ✅ Migrations run automatically
- ✅ All services healthy
- ✅ Can upload, process, and query documents

---

## Phase 7: Testing & Quality (Priority 2)

**Goal**: Achieve 80% test coverage and validate LLM quality  
**Duration**: 4-6 days  
**Priority**: MEDIUM - Important for production confidence

### Task 7.1: Increase Test Coverage (12-16 hours)

**Current**: ~60% coverage  
**Target**: 80% coverage

**Tasks**:
1. **Measure Current Coverage** (1 hour)
   ```bash
   pytest --cov=app --cov-report=html --cov-report=term-missing
   ```
   - Identify uncovered modules
   - Prioritize critical paths

2. **Add Missing Unit Tests** (8 hours)
   - Storage service: 5 tests
   - Audit service: 3 tests
   - Text extraction edge cases: 5 tests
   - Chunking boundary conditions: 4 tests
   - Comparison service: 6 tests
   - Export service: 6 tests

3. **Add Integration Tests** (4 hours)
   - Full document lifecycle: 2 tests
   - Error scenarios: 3 tests
   - Concurrent operations: 2 tests
   - Rate limiting: 2 tests

4. **Add E2E Tests** (3 hours)
   - Complete user journey: 1 test
   - Multi-user scenarios: 1 test
   - Performance benchmarks: 1 test

**Acceptance Criteria**:
- ✅ 80%+ line coverage
- ✅ All critical paths covered
- ✅ No flaky tests
- ✅ Tests run in <5 minutes

---

### Task 7.2: LLM Quality Evaluation (8-12 hours)

**Goal**: Validate LLM outputs meet quality thresholds

**Tasks**:
1. **Create Golden Dataset** (4 hours)
   - Collect 50 legal documents
   - Manually annotate clause spans and types
   - Create expected Q&A pairs
   - Store in `tests/eval/golden_dataset/`

2. **Build Evaluation Harness** (4 hours)
   - Create `tests/eval/test_llm_quality.py`
   - Automated clause extraction scoring
   - Citation validity checker for Q&A
   - Simplification readability scorer

3. **Run Evaluation** (2 hours)
   - Execute against golden dataset
   - Generate metrics report
   - Identify failure cases

4. **Tune Prompts** (2 hours)
   - Adjust prompts based on failures
   - Re-run evaluation
   - Iterate until targets met

**Targets** (from architecture.md):
- Clause extraction precision: ≥ 0.85
- Clause extraction recall: ≥ 0.80
- Q&A groundedness: ≥ 95% (valid citations)
- Simplification: 0% fabricated content

**Files to Create**:
- `tests/eval/golden_dataset/` (directory)
- `tests/eval/test_llm_quality.py`
- `tests/eval/metrics.py`

**Acceptance Criteria**:
- ✅ Golden dataset with 50 documents
- ✅ Automated evaluation runs
- ✅ All quality targets met
- ✅ Report generated

---

### Task 7.3: Performance Testing (6-8 hours)

**Goal**: Validate latency and throughput targets

**Tasks**:
1. **Setup Load Testing** (2 hours)
   - Install locust or k6
   - Create test scenarios
   - Configure realistic load

2. **Define Scenarios** (2 hours)
   - Document upload (various sizes)
   - Simplification (various page counts)
   - Chat (various conversation lengths)
   - Comparison (2-5 documents)

3. **Run Load Tests** (2 hours)
   - Execute scenarios
   - Monitor resource usage
   - Capture metrics

4. **Analyze & Optimize** (2 hours)
   - Identify bottlenecks
   - Optimize slow queries
   - Add caching where needed
   - Re-test

**Targets** (from architecture.md):
- Simplification: p95 ≤ 15s for ≤20 pages
- Chat response: p95 ≤ 5s per turn
- Throughput: 100 concurrent users

**Acceptance Criteria**:
- ✅ All latency targets met
- ✅ No crashes under load
- ✅ Resource usage reasonable
- ✅ Performance report generated

---

## Phase 8: Security Hardening (Priority 2)

**Goal**: Production-ready security features  
**Duration**: 3-5 days  
**Priority**: MEDIUM - Required before public launch

### Task 8.1: Rate Limiting (4-6 hours)

**Tasks**:
1. **Install Dependencies** (30 minutes)
   ```
   slowapi==0.1.9
   ```

2. **Implement Rate Limiter** (2 hours)
   - Create `apps/api/app/core/rate_limiter.py`
   - Configure Redis backend
   - Set per-endpoint limits
   
   ```python
   from slowapi import Limiter, _rate_limit_exceeded_handler
   from slowapi.util import get_remote_address
   
   limiter = Limiter(
       key_func=get_remote_address,
       storage_uri=settings.REDIS_URL,
   )
   
   # In main.py
   app.state.limiter = limiter
   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
   ```

3. **Apply to Endpoints** (2 hours)
   - Auth endpoints: 5/minute per IP
   - Upload: 10/hour per user
   - LLM calls: 30/hour per user
   - Read endpoints: 100/minute per user

4. **Testing** (1.5 hours)
   - Test rate limit enforcement
   - Test 429 responses
   - Test different limits per endpoint

**Acceptance Criteria**:
- ✅ Rate limits enforced
- ✅ Proper 429 responses
- ✅ Redis stores rate limit state
- ✅ Limits configurable via settings

---

### Task 8.2: File Validation & Malware Scanning (6-8 hours)

**Tasks**:
1. **Strict Magic-Byte Validation** (2 hours)
   - Enforce in upload endpoint
   - Reject files with mismatched extension
   - Test with disguised files

2. **ClamAV Integration** (4 hours)
   - Add ClamAV to Docker Compose
   - Create `apps/api/app/services/malware_scanner.py`
   - Scan uploads before processing
   - Quarantine infected files
   
   ```python
   import pyclamd
   
   async def scan_file(file_path: str) -> bool:
       cd = pyclamd.ClamdAgnostic()
       result = cd.scan_file(file_path)
       return result is None  # None means clean
   ```

3. **Testing** (2 hours)
   - Test with EICAR test file
   - Test with clean files
   - Test quarantine workflow

**Acceptance Criteria**:
- ✅ Magic-byte validation enforced
- ✅ Malware scanning works
- ✅ Infected files quarantined
- ✅ Clean files processed normally

---

### Task 8.3: Security Audit (8-10 hours)

**Tasks**:
1. **Endpoint Review** (4 hours)
   - Verify ownership checks on all endpoints
   - Check for SQL injection vulnerabilities
   - Review input validation
   - Test for XSS in outputs

2. **Authentication Review** (2 hours)
   - Verify token expiration
   - Test refresh token rotation
   - Check password requirements
   - Review session management

3. **Data Protection** (2 hours)
   - Verify no secrets in logs
   - Check for PII leakage
   - Review presigned URL expiration
   - Validate encryption at rest

4. **Penetration Testing** (2 hours)
   - Run OWASP ZAP
   - Test common vulnerabilities
   - Document findings
   - Fix critical issues

**Acceptance Criteria**:
- ✅ No critical vulnerabilities
- ✅ All endpoints secure
- ✅ Security report documented
- ✅ Compliance with OWASP top 10

---

## Phase 9: CI/CD & Deployment (Priority 3)

**Goal**: Automated testing and deployment  
**Duration**: 3-5 days  
**Priority**: MEDIUM - Needed for team collaboration

### Task 9.1: GitHub Actions CI (4-6 hours)

**Tasks**:
1. **Test Pipeline** (2 hours)
   - Create `.github/workflows/ci.yml`
   - Run tests on every PR
   - Check code coverage
   - Lint code
   
   ```yaml
   name: CI
   on: [pull_request, push]
   
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Set up Python
           uses: actions/setup-python@v4
         - name: Install dependencies
           run: pip install -r apps/api/requirements.txt
         - name: Run tests
           run: pytest --cov=app --cov-report=xml
         - name: Upload coverage
           uses: codecov/codecov-action@v3
   ```

2. **Lint Pipeline** (1 hour)
   - Add black, flake8, mypy
   - Configure rules
   - Enforce in CI

3. **Security Scan** (1 hour)
   - Add bandit for security checks
   - Add safety for dependency vulnerabilities

4. **Documentation** (1 hour)
   - Document CI process
   - Add badges to README

**Acceptance Criteria**:
- ✅ CI runs on every PR
- ✅ Tests must pass to merge
- ✅ Coverage reported
- ✅ Linting enforced

---

### Task 9.2: Deployment Pipeline (6-8 hours)

**Tasks**:
1. **Staging Deployment** (3 hours)
   - Create `.github/workflows/deploy-staging.yml`
   - Deploy to staging on merge to main
   - Run smoke tests

2. **Production Deployment** (3 hours)
   - Create `.github/workflows/deploy-production.yml`
   - Manual approval required
   - Blue-green deployment
   - Rollback capability

3. **Database Migrations** (2 hours)
   - Automated migration on deploy
   - Backup before migration
   - Rollback on failure

**Acceptance Criteria**:
- ✅ Staging deploys automatically
- ✅ Production requires approval
- ✅ Migrations run safely
- ✅ Rollback works

---

### Task 9.3: Kubernetes Setup (Optional, 12-16 hours)

**If deploying to Kubernetes**:

1. **Manifests** (6 hours)
   - Create k8s/ directory
   - Deployment configs
   - Service configs
   - Ingress rules
   - ConfigMaps and Secrets

2. **Helm Charts** (4 hours)
   - Create Helm chart
   - Configurable values
   - Environment-specific overrides

3. **Monitoring** (4 hours)
   - Prometheus metrics
   - Grafana dashboards
   - Alerting rules

4. **Testing** (2 hours)
   - Deploy to test cluster
   - Verify scaling
   - Test failover

---

## Timeline & Milestones

### Sprint 1: Complete MVP (Week 1)
- Day 1-2: Task 6.1 - Celery Workers
- Day 3: Task 6.2 - PDF/DOCX Export
- Day 4: Task 6.3 - Fix Tests + Task 6.4 - Docker Compose
- Day 5: Testing & bug fixes

**Milestone**: Fully functional MVP with all features working

### Sprint 2: Quality & Security (Week 2)
- Day 1-2: Task 7.1 - Test Coverage
- Day 3: Task 7.2 - LLM Evaluation
- Day 4: Task 7.3 - Performance Testing
- Day 5: Task 8.1-8.3 - Security Hardening

**Milestone**: Production-ready quality with 80% coverage

### Sprint 3: Deployment (Week 3)
- Day 1-2: Task 9.1 - CI Pipeline
- Day 3-4: Task 9.2 - Deployment Pipeline
- Day 5: Task 9.3 - Kubernetes (if needed)

**Milestone**: Automated CI/CD, deployed to staging

---

## Success Criteria

### MVP Ready (After Sprint 1)
- ✅ All features work end-to-end
- ✅ Async processing via Celery
- ✅ PDF/DOCX exports generate correctly
- ✅ All tests passing
- ✅ Docker Compose starts complete stack
- ✅ Manual testing successful

### Production Ready (After Sprint 2)
- ✅ 80%+ test coverage
- ✅ LLM quality targets met
- ✅ Performance targets met
- ✅ Security audit passed
- ✅ Rate limiting enforced
- ✅ Malware scanning active

### Deployed (After Sprint 3)
- ✅ CI/CD pipelines working
- ✅ Staging environment live
- ✅ Production deployment process documented
- ✅ Monitoring and alerting configured
- ✅ Rollback procedure tested

---

## Resource Requirements

### Infrastructure
- PostgreSQL with pgvector (16GB RAM recommended)
- Redis (4GB RAM)
- S3/MinIO storage (500GB initial)
- Celery workers (8GB RAM each, 2-4 workers)
- API servers (16GB RAM each, 2+ instances)

### External APIs
- Anthropic Claude API (budget: $100-500/month depending on usage)
- Voyage AI embeddings (budget: $50-200/month)
- S3 storage (budget: $20-50/month)

### Development
- 1-2 backend developers
- 1 DevOps engineer (part-time)
- 1 QA engineer (part-time)

---

## Risk Mitigation

### Technical Risks
1. **LLM API costs**
   - Mitigation: Implement caching, set budget alerts
   
2. **Performance under load**
   - Mitigation: Horizontal scaling, async processing, caching

3. **Data privacy**
   - Mitigation: Encryption at rest and in transit, access controls

### Schedule Risks
1. **Scope creep**
   - Mitigation: Strict MVP definition, defer non-critical features
   
2. **Dependency issues**
   - Mitigation: Pin all versions, test upgrades in staging

3. **Integration complexity**
   - Mitigation: Modular architecture, extensive testing

---

## Next Actions

**Immediate** (This week):
1. Review this plan with team
2. Set up development environment
3. Begin Task 6.1 (Celery Workers)

**This Month**:
1. Complete Sprint 1 (MVP)
2. Begin Sprint 2 (Quality)
3. Plan production deployment

**This Quarter**:
1. Deploy to production
2. Onboard initial users
3. Gather feedback
4. Plan v2 features

---

## Conclusion

With Phases 0-5 complete (75% of core features), LegalLens is well-positioned for rapid completion. The remaining work focuses on:

1. **Operational readiness** (Celery, Docker)
2. **Quality assurance** (testing, evaluation)
3. **Production hardening** (security, CI/CD)

Following this plan, the project can be MVP-ready in 1 week, production-ready in 2-3 weeks, and fully deployed in 3-4 weeks.

The architecture is solid, the code is clean, and the foundation is strong. The path to completion is clear and achievable.
