# Instructions for Creating Remaining Pull Requests

## ✅ Completed
- **PR 1: Project Foundation** - Branch `feat/project-foundation` pushed to GitHub

## 📋 Remaining PRs to Create

Below are the commands to create and push the remaining PR branches. Run these commands in your terminal:

### PR 2: Backend API - Phase 0 (Scaffolding)
```powershell
git checkout feat/project-foundation
git checkout -b feat/backend-phase0-scaffolding
git add apps/api/app/main.py apps/api/app/core/ apps/api/app/db/ apps/api/requirements.txt apps/api/pytest.ini apps/api/Dockerfile apps/api/conftest.py apps/api/app/__init__.py
git commit -m "feat(api): add core scaffolding and configuration

- Initialize FastAPI application with middleware
- Add structured logging with structlog  
- Configure database session with SQLAlchemy async
- Add JWT security utilities
- Set up pytest configuration
- Create Dockerfile for containerization"
git push -u origin feat/backend-phase0-scaffolding
```

### PR 3: Backend API - Phase 1 (Auth & Upload)
```powershell
git checkout feat/backend-phase0-scaffolding
git checkout -b feat/backend-phase1-auth-upload
git add apps/api/app/models/user.py apps/api/app/models/document.py apps/api/app/models/audit_log.py apps/api/app/api/v1/auth.py apps/api/app/api/v1/documents.py apps/api/app/services/auth.py apps/api/app/services/storage.py apps/api/app/services/audit.py apps/api/app/services/ingestion.py apps/api/alembic/versions/001_phase1_initial.py apps/api/tests/unit/test_auth.py
git commit -m "feat(api): implement authentication and document upload

- Add user model with Argon2id password hashing
- Implement JWT token generation and validation
- Add document upload with S3/MinIO storage
- Implement audit logging for state changes
- Create Phase 1 database migration
- Add authentication unit tests"
git push -u origin feat/backend-phase1-auth-upload
```

### PR 4: Backend API - Phase 2 (RAG Pipeline)
```powershell
git checkout feat/backend-phase1-auth-upload
git checkout -b feat/backend-phase2-rag-pipeline
git add apps/api/app/models/document_chunk.py apps/api/app/services/text_extraction.py apps/api/app/services/chunking.py apps/api/app/services/embedding.py apps/api/alembic/versions/002_phase2_chunks.py apps/api/tests/unit/test_text_extraction.py apps/api/tests/unit/test_chunking.py apps/api/tests/unit/test_embedding.py
git commit -m "feat(api): implement RAG pipeline with embeddings

- Add text extraction for PDF/DOCX with OCR fallback
- Implement semantic chunking with sentence boundaries
- Add Voyage AI embedding generation
- Configure pgvector for similarity search
- Create Phase 2 database migration
- Add comprehensive tests for RAG components"
git push -u origin feat/backend-phase2-rag-pipeline
```

### PR 5: Backend API - Phase 3 (Simplification & Clauses)
```powershell
git checkout feat/backend-phase2-rag-pipeline
git checkout -b feat/backend-phase3-simplification-clauses
git add apps/api/app/models/clause.py apps/api/app/services/llm_orchestration.py apps/api/app/services/simplification.py apps/api/app/services/clause_extraction.py apps/api/app/prompts/ apps/api/alembic/versions/003_phase3_clauses.py apps/api/tests/unit/test_llm_orchestration.py apps/api/tests/unit/test_simplification.py apps/api/tests/unit/test_clause_extraction.py
git commit -m "feat(api): add LLM-powered simplification and clause extraction

- Implement 3-level simplification (elementary, plain, detailed)
- Add clause extraction with 10 types and 3 risk levels
- Integrate Claude Sonnet-4 and Haiku-4-5
- Add keyword pre-filtering for clause detection
- Create Phase 3 database migration
- Add comprehensive LLM service tests"
git push -u origin feat/backend-phase3-simplification-clauses
```

### PR 6: Backend API - Phase 4 (Chat & Q&A)
```powershell
git checkout feat/backend-phase3-simplification-clauses
git checkout -b feat/backend-phase4-chat-qa
git add apps/api/app/models/chat.py apps/api/app/services/chat.py apps/api/app/api/v1/chat.py apps/api/alembic/versions/004_phase4_chat.py apps/api/tests/unit/test_chat.py apps/api/tests/integration/test_chat_flow.py
git commit -m "feat(api): implement conversational Q&A with RAG

- Add chat session and message models
- Implement RAG-based question answering
- Add conversation history management
- Require citations for all answers
- Create Phase 4 database migration
- Add unit and integration tests for chat"
git push -u origin feat/backend-phase4-chat-qa
```

### PR 7: Backend API - Phase 5 (Comparison & Export)
```powershell
git checkout feat/backend-phase4-chat-qa
git checkout -b feat/backend-phase5-comparison-export
git add apps/api/app/models/comparison.py apps/api/app/models/export.py apps/api/app/services/comparison.py apps/api/app/services/export.py apps/api/app/api/v1/comparisons.py apps/api/app/api/v1/exports.py apps/api/alembic/versions/005_phase5_comparison_export.py
git commit -m "feat(api): add document comparison and export

- Implement clause-aligned comparison for 2-5 documents
- Add materiality ratings (none, minor, significant, critical)
- Create export module with Markdown format
- Support summary, checklist, lawyer brief, and comparison reports
- Create Phase 5 database migration"
git push -u origin feat/backend-phase5-comparison-export
```

### PR 8: Frontend Web Application
```powershell
git checkout feat/backend-phase5-comparison-export
git checkout -b feat/frontend-web-app
git add apps/web/src/ apps/web/package.json apps/web/tsconfig.json apps/web/tailwind.config.ts apps/web/next.config.ts apps/web/postcss.config.mjs
git commit -m "feat(web): implement complete Next.js frontend

- Add React components for all features
- Implement document upload and management
- Add simplification and clause viewing
- Create chat interface with RAG Q&A
- Add document comparison UI
- Implement export functionality
- Configure Tailwind CSS styling
- Add TypeScript type definitions"
git push -u origin feat/frontend-web-app
```

### PR 9: Testing & CI/CD
```powershell
git checkout feat/frontend-web-app
git checkout -b feat/testing-cicd
git add .github/workflows/ apps/api/tests/ apps/web/src/components/__tests__/
git commit -m "feat: add comprehensive testing and CI/CD

- Add GitHub Actions workflows for CI
- Configure staging and production deployment
- Add backend unit and integration tests (158+ tests)
- Add frontend component tests
- Configure test coverage reporting"
git push -u origin feat/testing-cicd
```

### PR 10: Security & Production Readiness
```powershell
git checkout feat/testing-cicd
git checkout -b feat/security-production
git add apps/api/app/core/rate_limiter.py apps/api/app/core/file_validator.py apps/api/alembic/versions/006_phase9_mfa.py apps/api/alembic/versions/007_phase9_account_lockout.py apps/api/app/api/v1/mfa.py apps/api/UI-BUILD-COMPLETE.md apps/api/UI-IMPLEMENTATION-SUMMARY.md apps/api/NEXT-STEPS-COMPLETE.md
git commit -m "feat: add security hardening and production readiness

- Implement rate limiting with Redis
- Add file magic-byte validation
- Implement MFA (TOTP-based)
- Add account lockout protection
- Create security migrations (Phase 9)
- Add deployment readiness documentation"
git push -u origin feat/security-production
```

## 🔗 Creating Pull Requests on GitHub

After pushing all branches, create pull requests manually:

1. Go to: https://github.com/Bharathkumar1123542/LegalLens/pulls
2. Click "New pull request"
3. For each PR:
   - **Base**: `main`
   - **Compare**: select the feature branch (e.g., `feat/project-foundation`)
   - **Title**: Use the PR title from PR_STRATEGY.md
   - **Description**: Copy the description from PR_STRATEGY.md

### PR Descriptions

#### PR 1: Project Foundation & Documentation
```
Initial project setup including comprehensive documentation, planning documents, and project structure.

**Includes**:
- Comprehensive README with project overview
- Deployment and quick start guides
- PR strategy document
- Project context and planning documents
- Environment variable configuration template
- Agent configuration files
```

#### PR 2: Backend API - Phase 0 (Scaffolding & Core)
```
Core backend scaffolding with FastAPI setup, database configuration, logging, and security basics.

**Includes**:
- FastAPI application initialization
- Structured logging with structlog
- Database session management (SQLAlchemy async)
- JWT security utilities
- Pytest configuration
- Docker containerization setup
```

#### PR 3: Backend API - Phase 1 (Authentication & Upload)
```
User authentication with JWT tokens, document upload with S3 storage, and audit logging.

**Includes**:
- User model with Argon2id password hashing
- JWT token generation and validation
- Document upload with S3/MinIO storage
- Audit logging for all state changes
- Phase 1 database migration
- Authentication unit tests
```

#### PR 4: Backend API - Phase 2 (RAG Pipeline)
```
Text extraction (PDF/DOCX), OCR fallback, semantic chunking, and embedding generation with pgvector.

**Includes**:
- PDF/DOCX text extraction with PyMuPDF/python-docx
- Tesseract OCR fallback for scanned documents
- Semantic chunking with sentence boundaries
- Voyage AI embedding generation
- pgvector similarity search
- Phase 2 database migration
- Comprehensive RAG tests
```

#### PR 5: Backend API - Phase 3 (Simplification & Clauses)
```
LLM-powered simplification (3 reading levels) and clause extraction (10 types, 3 risk levels).

**Includes**:
- 3-level document simplification
- Clause extraction with 10 types and 3 risk levels
- Claude Sonnet-4 and Haiku-4-5 integration
- Keyword pre-filtering for clause detection
- Map-reduce pattern for long documents
- Phase 3 database migration
- LLM service tests
```

#### PR 6: Backend API - Phase 4 (Chat & Q&A)
```
Conversational Q&A with RAG retrieval, conversation history, and citation requirements.

**Includes**:
- Chat session and message models
- RAG-based question answering (top-k=8)
- Conversation history management
- Citation requirement for all answers
- Phase 4 database migration
- Unit and integration tests
```

#### PR 7: Backend API - Phase 5 (Comparison & Export)
```
Document comparison engine (2-5 docs) and export module (Markdown, PDF, DOCX formats).

**Includes**:
- Clause-aligned comparison (2-5 documents)
- Materiality ratings (none, minor, significant, critical)
- Export module with multiple formats
- Summary, checklist, lawyer brief, and comparison reports
- Phase 5 database migration
- Presigned URL generation for downloads
```

#### PR 8: Frontend Web Application
```
Complete Next.js frontend with React components, Tailwind CSS styling, and API integration.

**Includes**:
- React components for all features
- Document upload and management UI
- Simplification and clause viewing
- Chat interface with RAG Q&A
- Document comparison interface
- Export functionality
- Tailwind CSS styling
- TypeScript type definitions
- API client integration
```

#### PR 9: Testing & CI/CD
```
Comprehensive test suites for backend and frontend, plus GitHub Actions workflows for CI/CD.

**Includes**:
- GitHub Actions CI workflow
- Staging and production deployment workflows
- 158+ backend tests (unit + integration)
- Frontend component tests
- Test coverage reporting
- Automated linting and type checking
```

#### PR 10: Security & Production Readiness
```
Security hardening including rate limiting, MFA, account lockout, and production deployment checklist.

**Includes**:
- Rate limiting with Redis
- File magic-byte validation
- MFA (TOTP-based) implementation
- Account lockout protection
- Phase 9 security migrations
- Deployment readiness documentation
- Security audit checklist
```

## 📝 Notes

- Each branch builds on the previous one
- Merge PRs in order (1 → 2 → 3... → 10)
- Use "Squash and merge" to keep history clean
- Review tests pass before merging
- Update documentation after all PRs are merged

## ✅ Checklist

- [ ] Run all commands above to push branches
- [ ] Create PR 1 on GitHub
- [ ] Create PR 2 on GitHub  
- [ ] Create PR 3 on GitHub
- [ ] Create PR 4 on GitHub
- [ ] Create PR 5 on GitHub
- [ ] Create PR 6 on GitHub
- [ ] Create PR 7 on GitHub
- [ ] Create PR 8 on GitHub
- [ ] Create PR 9 on GitHub
- [ ] Create PR 10 on GitHub
- [ ] Review and merge all PRs in order
- [ ] Create release tag v1.0.0
- [ ] Deploy to staging
- [ ] Deploy to production
