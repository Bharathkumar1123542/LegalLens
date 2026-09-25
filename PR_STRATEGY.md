# LegalLens GitHub Pull Request Strategy

## Overview
This document outlines the strategy for pushing the LegalLens codebase to GitHub as multiple logical pull requests.

## Repository Structure
- **Repository**: https://github.com/Bharathkumar1123542/LegalLens
- **Base Branch**: `main`
- **Total PRs**: 10 organized by feature/phase

## Pull Request Plan

### PR 1: Project Foundation & Documentation
**Branch**: `feat/project-foundation`
**Files**:
- README.md
- .gitignore
- .env.example
- DEPLOYMENT.md
- QUICK_START.md
- .context/ (all planning documents)
- .agents/ (agent configuration)

**Description**: Initial project setup including comprehensive documentation, planning documents, and project structure.

---

### PR 2: Backend API - Phase 0 (Scaffolding & Core)
**Branch**: `feat/backend-phase0-scaffolding`
**Files**:
- apps/api/app/main.py
- apps/api/app/core/ (config, logging, security)
- apps/api/app/db/ (database session)
- apps/api/requirements.txt
- apps/api/pytest.ini
- apps/api/Dockerfile

**Description**: Core backend scaffolding with FastAPI setup, database configuration, logging, and security basics.

---

### PR 3: Backend API - Phase 1 (Authentication & Upload)
**Branch**: `feat/backend-phase1-auth-upload`
**Files**:
- apps/api/app/models/user.py
- apps/api/app/models/document.py
- apps/api/app/models/audit_log.py
- apps/api/app/api/v1/auth.py
- apps/api/app/api/v1/documents.py
- apps/api/app/services/auth.py
- apps/api/app/services/storage.py
- apps/api/app/services/audit.py
- apps/api/alembic/versions/001_phase1_initial.py
- apps/api/tests/unit/test_auth.py

**Description**: User authentication with JWT tokens, document upload with S3 storage, and audit logging.

---

### PR 4: Backend API - Phase 2 (RAG Pipeline)
**Branch**: `feat/backend-phase2-rag-pipeline`
**Files**:
- apps/api/app/models/document_chunk.py
- apps/api/app/services/text_extraction.py
- apps/api/app/services/chunking.py
- apps/api/app/services/embedding.py
- apps/api/alembic/versions/002_phase2_chunks.py
- apps/api/tests/unit/test_text_extraction.py
- apps/api/tests/unit/test_chunking.py

**Description**: Text extraction (PDF/DOCX), OCR fallback, semantic chunking, and embedding generation with pgvector.

---

### PR 5: Backend API - Phase 3 (Simplification & Clauses)
**Branch**: `feat/backend-phase3-simplification-clauses`
**Files**:
- apps/api/app/models/clause.py
- apps/api/app/services/llm_orchestration.py
- apps/api/app/services/simplification.py
- apps/api/app/services/clause_extraction.py
- apps/api/app/prompts/simplify.md
- apps/api/app/prompts/extract_clauses.md
- apps/api/alembic/versions/003_phase3_clauses.py
- apps/api/tests/unit/test_simplification.py
- apps/api/tests/unit/test_clause_extraction.py

**Description**: LLM-powered simplification (3 reading levels) and clause extraction (10 types, 3 risk levels).

---

### PR 6: Backend API - Phase 4 (Chat & Q&A)
**Branch**: `feat/backend-phase4-chat-qa`
**Files**:
- apps/api/app/models/chat.py
- apps/api/app/services/chat.py
- apps/api/app/api/v1/chat.py
- apps/api/app/prompts/chat.md
- apps/api/alembic/versions/004_phase4_chat.py
- apps/api/tests/unit/test_chat.py
- apps/api/tests/integration/test_chat_flow.py

**Description**: Conversational Q&A with RAG retrieval, conversation history, and citation requirements.

---

### PR 7: Backend API - Phase 5 (Comparison & Export)
**Branch**: `feat/backend-phase5-comparison-export`
**Files**:
- apps/api/app/models/comparison.py
- apps/api/app/models/export.py
- apps/api/app/services/comparison.py
- apps/api/app/services/export.py
- apps/api/app/api/v1/comparisons.py
- apps/api/app/api/v1/exports.py
- apps/api/app/prompts/compare.md
- apps/api/alembic/versions/005_phase5_comparison_export.py

**Description**: Document comparison engine (2-5 docs) and export module (Markdown, PDF, DOCX formats).

---

### PR 8: Frontend Web Application
**Branch**: `feat/frontend-web-app`
**Files**:
- apps/web/ (all TypeScript/React code)
- apps/web/src/components/
- apps/web/src/lib/
- apps/web/src/app/
- apps/web/package.json
- apps/web/tsconfig.json
- apps/web/tailwind.config.ts

**Description**: Complete Next.js frontend with React components, Tailwind CSS styling, and API integration.

---

### PR 9: Testing & CI/CD
**Branch**: `feat/testing-cicd`
**Files**:
- .github/workflows/ci.yml
- .github/workflows/deploy-staging.yml
- .github/workflows/deploy-production.yml
- apps/api/tests/ (all test files)
- apps/web/src/components/__tests__/

**Description**: Comprehensive test suites for backend and frontend, plus GitHub Actions workflows for CI/CD.

---

### PR 10: Security & Production Readiness
**Branch**: `feat/security-production`
**Files**:
- apps/api/app/core/rate_limiter.py
- apps/api/app/core/file_validator.py
- apps/api/alembic/versions/006_phase9_mfa.py
- apps/api/alembic/versions/007_phase9_account_lockout.py
- apps/api/app/api/v1/mfa.py
- .context/security-audit.md
- .context/deployment-readiness-checklist.md

**Description**: Security hardening including rate limiting, MFA, account lockout, and production deployment checklist.

---

## Branch Creation & Push Commands

```bash
# PR 1: Foundation
git checkout -b feat/project-foundation
git add README.md .gitignore .env.example DEPLOYMENT.md QUICK_START.md .context/ .agents/
git commit -m "docs: add project foundation and documentation"
git push -u origin feat/project-foundation

# PR 2: Backend Phase 0
git checkout -b feat/backend-phase0-scaffolding
git add apps/api/app/main.py apps/api/app/core/ apps/api/app/db/ apps/api/requirements.txt apps/api/pytest.ini apps/api/Dockerfile
git commit -m "feat(api): add core scaffolding and configuration"
git push -u origin feat/backend-phase0-scaffolding

# PR 3: Backend Phase 1
git checkout -b feat/backend-phase1-auth-upload
git add apps/api/app/models/user.py apps/api/app/models/document.py apps/api/app/models/audit_log.py apps/api/app/api/v1/auth.py apps/api/app/api/v1/documents.py apps/api/app/services/auth.py apps/api/app/services/storage.py apps/api/app/services/audit.py apps/api/alembic/versions/001_phase1_initial.py apps/api/tests/unit/test_auth.py
git commit -m "feat(api): add authentication and document upload (Phase 1)"
git push -u origin feat/backend-phase1-auth-upload

# Continue for remaining PRs...
```

## Creating Pull Requests

Since GitHub CLI (`gh`) is not installed, create PRs manually:

1. Go to https://github.com/Bharathkumar1123542/LegalLens
2. Click "Pull requests" tab
3. Click "New pull request"
4. Select the feature branch as "compare"
5. Add title and description from this document
6. Create the pull request

## PR Review Checklist

For each PR, ensure:
- [ ] All tests pass
- [ ] Code follows project conventions
- [ ] Documentation is updated
- [ ] No sensitive data committed
- [ ] Dependencies are properly specified
- [ ] Migration files are included (for backend PRs)

## Merge Strategy

- **Merge Method**: Squash and merge (to keep main branch history clean)
- **Order**: Merge PRs sequentially (1 → 2 → 3... → 10)
- **Branch Protection**: Consider enabling branch protection rules on `main`

## Post-Merge Actions

After all PRs are merged:
1. Update project status document
2. Create a release tag (v1.0.0)
3. Deploy to staging environment
4. Run end-to-end tests
5. Deploy to production

---

## Notes

- Each PR is designed to be independent and reviewable
- Dependencies between PRs are minimal and documented
- Large files (node_modules, .venv) are excluded via .gitignore
- All PRs include relevant tests and documentation
