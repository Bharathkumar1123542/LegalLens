# LegalLens CI/CD Workflows

This directory contains GitHub Actions workflows for automated testing, deployment, and quality assurance.

## Workflows

### `ci.yml` — Continuous Integration

**Triggers**: Every push and pull request to `main` or `develop`

**Jobs**:
1. **api-lint** — Backend code quality
   - Ruff linting
   - MyPy type checking
   - Bandit security scanning
   - Safety dependency vulnerability check

2. **api-test** — Backend testing
   - Unit tests
   - Integration tests (with PostgreSQL + Redis)
   - Coverage reporting (80% minimum)
   - Codecov upload

3. **web-lint-test** — Frontend quality
   - TypeScript type checking
   - ESLint linting
   - Jest unit tests
   - Coverage reporting

4. **build-check** — Docker build verification
   - API Docker image build
   - Web Docker image build
   - Layer caching for speed

5. **ci-success** — Status gate
   - Required check for PR merge
   - Fails if any job fails

**Environment Variables**:
- `DATABASE_URL`: Test database connection
- `REDIS_URL`: Redis connection
- `ANTHROPIC_API_KEY`: Mocked in tests
- `JWT_SECRET`: GitHub secret or default

**Artifacts**:
- Security scan reports (30 days)
- Coverage HTML reports (30 days)

### `deploy-staging.yml` — Staging Deployment

**Triggers**: Merge to `main` branch

**Steps**:
1. Build Docker images
2. Push to container registry
3. Deploy to staging environment
4. Run smoke tests
5. Notify on success/failure

### `deploy-production.yml` — Production Deployment

**Triggers**: Manual approval (workflow_dispatch)

**Steps**:
1. Build production images
2. Run database migrations
3. Blue-green deployment
4. Health check verification
5. Rollback on failure

## Setup Instructions

### 1. Required GitHub Secrets

Add these secrets to your GitHub repository:

```
Settings → Secrets and variables → Actions → New repository secret
```

**Required**:
- `CI_JWT_SECRET` — JWT secret for tests (32+ character random string)
- `CODECOV_TOKEN` — Codecov.io API token (optional, for coverage reporting)

**For Deployment** (Phase 8 Tasks 8.4-8.5):
- `GCP_PROJECT_ID` — Google Cloud project ID
- `GCP_SA_KEY` — Service account JSON key (base64 encoded)
- `DOCKER_REGISTRY` — Container registry URL
- `STAGING_CLUSTER` — GKE staging cluster name
- `PROD_CLUSTER` — GKE production cluster name

**For Monitoring**:
- `SENTRY_DSN` — Sentry error tracking DSN
- `SLACK_WEBHOOK` — Slack notifications webhook

### 2. Branch Protection Rules

Configure branch protection for `main`:

```
Settings → Branches → Add rule
```

**Rules**:
- ✅ Require a pull request before merging
- ✅ Require approvals: 1
- ✅ Require status checks to pass:
  - `CI Success`
  - `api-lint`
  - `api-test`
  - `web-lint-test`
  - `build-check`
- ✅ Require branches to be up to date
- ✅ Include administrators

### 3. Codecov Integration (Optional)

1. Sign up at https://codecov.io
2. Connect your GitHub repository
3. Add `CODECOV_TOKEN` secret
4. Coverage reports will appear on PRs

### 4. Local Testing

Test CI pipeline locally before pushing:

```bash
# Backend linting
cd apps/api
ruff check app/ tests/
mypy app/ --ignore-missing-imports
bandit -r app/

# Backend tests with coverage
pytest tests/ --cov=app --cov-report=html --cov-fail-under=80

# Frontend checks
cd apps/web
npm run type-check
npm run lint
npm test

# Docker build test
docker build -t legallens-api:test apps/api
docker build -t legallens-web:test apps/web
```

## CI Performance

### Typical Run Times

| Job | Duration | Cacheable |
|-----|----------|-----------|
| api-lint | 1-2 min | ✅ pip cache |
| api-test | 3-5 min | ✅ pip cache |
| web-lint-test | 2-3 min | ✅ npm cache |
| build-check | 2-4 min | ✅ Docker layers |
| **Total** | **8-14 min** | |

### Optimization Tips

1. **Cache Dependencies**
   - Already enabled: pip, npm, Docker layers
   
2. **Parallel Jobs**
   - Lint and test jobs run in parallel
   
3. **Fail Fast**
   - Lint runs before tests (faster feedback)
   
4. **Concurrency Control**
   - Cancels in-progress runs for same PR

## Troubleshooting

### "Coverage below 80%"

```bash
# Generate coverage report locally
pytest tests/ --cov=app --cov-report=html

# Open htmlcov/index.html to see uncovered lines
```

Add tests for uncovered code or adjust threshold in `pyproject.toml`.

### "Bandit security issues"

Review security warnings:
```bash
bandit -r app/ -f screen
```

Fix issues or add `# nosec` comment with justification if false positive.

### "Mypy type errors"

```bash
mypy app/ --ignore-missing-imports
```

Add type hints or ignore specific modules in `pyproject.toml`.

### "Docker build failed"

Test locally:
```bash
docker build -t test apps/api
docker run --rm test python -c "import app; print('OK')"
```

### "Database connection failed"

Check PostgreSQL service is running:
```yaml
services:
  postgres:
    options: >-
      --health-cmd pg_isready
```

## Notifications

### Pull Request Comments

- Coverage report commented on every PR
- Shows coverage change (increase/decrease)
- Highlights uncovered lines

### Status Checks

- ✅ Green check: All tests passed
- ❌ Red X: Tests failed (click for details)
- 🟡 Yellow circle: Tests running

## Best Practices

1. **Run tests locally before pushing**
   ```bash
   ./scripts/test-coverage.sh  # or .ps1 on Windows
   ```

2. **Keep PRs small** for faster CI runs

3. **Write fast tests** — aim for <5 min total

4. **Mock external APIs** (Anthropic, Voyage) in tests

5. **Use fixtures** for common test data

6. **Tag slow tests** with `@pytest.mark.slow`

7. **Monitor CI metrics** — optimize if >15 min

## Security Scanning

### Bandit (Static Analysis)

Checks for:
- SQL injection vulnerabilities
- Hardcoded secrets
- Unsafe deserialization
- Command injection
- Weak cryptography

### Safety (Dependencies)

Checks for:
- Known vulnerabilities in dependencies
- CVEs from National Vulnerability Database
- Recommended version upgrades

### Recommended: Add SAST

For production, consider:
- **Snyk** — Dependency and container scanning
- **SonarCloud** — Code quality and security
- **GitHub Advanced Security** — CodeQL analysis

## Continuous Improvement

### Phase 8 Enhancements

- [x] Comprehensive CI pipeline
- [ ] Staging deployment (Task 8.4)
- [ ] Production deployment (Task 8.5)
- [ ] Performance tests in CI
- [ ] E2E tests with Playwright
- [ ] Visual regression tests

### Future Enhancements

- Nightly golden dataset evaluation
- Mutation testing (mutmut)
- License compliance checking
- API contract testing
- Load testing in CI

## Support

For CI issues:
1. Check GitHub Actions logs
2. Review this documentation
3. Test locally with same commands
4. Check `.context/progress-tracker.md` for known issues

## See Also

- `.context/phase7-test-summary.md` — Test coverage details
- `apps/api/tests/README.md` — Test organization
- `apps/api/pyproject.toml` — Tool configurations
- `scripts/test-coverage.sh` — Local coverage script
