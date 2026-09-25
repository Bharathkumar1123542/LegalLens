# LegalLens Deployment Guide — Phase 8

Complete deployment guide for LegalLens including infrastructure setup, CI/CD configuration, secrets management, and operational procedures.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Secrets Management](#secrets-management)
4. [CI/CD Configuration](#cicd-configuration)
5. [Deployment Procedures](#deployment-procedures)
6. [Rollback Procedures](#rollback-procedures)
7. [Troubleshooting](#troubleshooting)
8. [Operational Runbooks](#operational-runbooks)

---

## Prerequisites

### Required Accounts
- **Google Cloud Platform**: Project with billing enabled
- **GitHub**: Repository with Actions enabled
- **Sentry** (optional): Error tracking account
- **Slack** (optional): Webhook for deployment notifications

### Required Tools
```bash
# Google Cloud SDK
curl https://sdk.cloud.google.com | bash
gcloud init

# GitHub CLI
brew install gh  # macOS
# or download from https://cli.github.com/

# Docker
# Download from https://www.docker.com/products/docker-desktop

# Python 3.11+
python --version  # Should be 3.11 or higher

# Node.js 18+
node --version  # Should be 18 or higher
```

### GCP APIs to Enable
```bash
gcloud services enable \
  run.googleapis.com \
  sql-component.googleapis.com \
  sqladmin.googleapis.com \
  storage-api.googleapis.com \
  secretmanager.googleapis.com \
  redis.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

---

## Infrastructure Setup

### 1. Google Cloud Project

```bash
# Set project ID
export PROJECT_ID="legallens-production"
export REGION="us-central1"

# Create project (if new)
gcloud projects create $PROJECT_ID --name="LegalLens Production"

# Set as active project
gcloud config set project $PROJECT_ID
```

### 2. Cloud SQL (PostgreSQL)

#### Staging Database
```bash
gcloud sql instances create legallens-staging \
  --database-version=POSTGRES_15 \
  --tier=db-g1-small \
  --region=$REGION \
  --network=default \
  --database-flags=max_connections=100 \
  --backup-start-time=03:00 \
  --backup-location=$REGION \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=4 \
  --enable-bin-log

# Create database
gcloud sql databases create legallens \
  --instance=legallens-staging

# Create user
gcloud sql users create legallens \
  --instance=legallens-staging \
  --password=$(openssl rand -base64 32)

# Get connection name
gcloud sql instances describe legallens-staging \
  --format="value(connectionName)"
```

#### Production Database
```bash
gcloud sql instances create legallens-production \
  --database-version=POSTGRES_15 \
  --tier=db-custom-4-16384 \
  --region=$REGION \
  --network=default \
  --database-flags=max_connections=200 \
  --backup-start-time=02:00 \
  --backup-location=$REGION \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=3 \
  --enable-bin-log \
  --availability-type=REGIONAL \
  --replica-type=READ \
  --retained-backups-count=14

# Create database
gcloud sql databases create legallens \
  --instance=legallens-production

# Create user
gcloud sql users create legallens \
  --instance=legallens-production \
  --password=$(openssl rand -base64 32)
```

**Database URL Format**:
```
postgresql://legallens:PASSWORD@/legallens?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
```

### 3. Redis (Memorystore)

#### Staging Redis
```bash
gcloud redis instances create legallens-staging \
  --size=1 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --tier=basic

# Get connection info
gcloud redis instances describe legallens-staging \
  --region=$REGION \
  --format="value(host,port)"
```

#### Production Redis
```bash
gcloud redis instances create legallens-production \
  --size=5 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --tier=standard-ha \
  --replica-count=1

# Get connection info
gcloud redis instances describe legallens-production \
  --region=$REGION \
  --format="value(host,port)"
```

**Redis URL Format**:
```
redis://HOST:PORT
```

### 4. Cloud Storage (GCS)

```bash
# Staging bucket
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://legallens-staging
gsutil versioning set on gs://legallens-staging
gsutil lifecycle set - gs://legallens-staging <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      }
    ]
  }
}
EOF

# Production bucket
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://legallens-production
gsutil versioning set on gs://legallens-production
gsutil lifecycle set - gs://legallens-production <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 365}
      }
    ]
  }
}
EOF

# Set CORS policy (if needed for web uploads)
gsutil cors set - gs://legallens-production <<EOF
[
  {
    "origin": ["https://legallens.com"],
    "method": ["GET", "HEAD", "PUT", "POST"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF
```

### 5. Service Accounts

#### CI/CD Service Account
```bash
# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions CI/CD"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions@$PROJECT_ID.iam.gserviceaccount.com

# This key will be stored as GCP_SA_KEY GitHub secret
```

#### Application Service Accounts
```bash
# Staging
gcloud iam service-accounts create legallens-staging \
  --display-name="LegalLens Staging App"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:legallens-staging@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:legallens-staging@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gsutil iam ch \
  serviceAccount:legallens-staging@$PROJECT_ID.iam.gserviceaccount.com:objectAdmin \
  gs://legallens-staging

# Production
gcloud iam service-accounts create legallens-production \
  --display-name="LegalLens Production App"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:legallens-production@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:legallens-production@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gsutil iam ch \
  serviceAccount:legallens-production@$PROJECT_ID.iam.gserviceaccount.com:objectAdmin \
  gs://legallens-production
```

---

## Secrets Management

### 1. Google Cloud Secret Manager

#### Create Secrets
```bash
# Database URLs
echo -n "postgresql://legallens:PASSWORD@/legallens?host=/cloudsql/..." | \
  gcloud secrets create staging-database-url --data-file=-

echo -n "postgresql://legallens:PASSWORD@/legallens?host=/cloudsql/..." | \
  gcloud secrets create prod-database-url --data-file=-

# JWT Secret
openssl rand -base64 64 | tr -d '\n' | \
  gcloud secrets create staging-jwt-secret --data-file=-

openssl rand -base64 64 | tr -d '\n' | \
  gcloud secrets create prod-jwt-secret --data-file=-

# API Keys
echo -n "YOUR_ANTHROPIC_KEY" | \
  gcloud secrets create anthropic-api-key --data-file=-

echo -n "YOUR_VOYAGE_KEY" | \
  gcloud secrets create voyage-api-key --data-file=-

# S3 Credentials (if using S3 instead of GCS)
echo -n "YOUR_AWS_ACCESS_KEY" | \
  gcloud secrets create s3-access-key --data-file=-

echo -n "YOUR_AWS_SECRET_KEY" | \
  gcloud secrets create s3-secret-key --data-file=-
```

#### Grant Access
```bash
# Staging
for secret in staging-database-url staging-jwt-secret anthropic-api-key \
              voyage-api-key s3-access-key s3-secret-key; do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:legallens-staging@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done

# Production
for secret in prod-database-url prod-jwt-secret anthropic-api-key \
              voyage-api-key s3-access-key s3-secret-key; do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:legallens-production@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 2. GitHub Secrets

Navigate to **GitHub Repository → Settings → Secrets and variables → Actions**

#### Required Secrets
```bash
# Using GitHub CLI
gh secret set GCP_PROJECT_ID -b"legallens-production"
gh secret set GCP_SA_KEY < github-actions-key.json

# Staging
gh secret set STAGING_DATABASE_URL -b"postgresql://..."
gh secret set STAGING_REDIS_URL -b"redis://HOST:PORT"
gh secret set STAGING_SERVICE_ACCOUNT -b"legallens-staging@PROJECT.iam.gserviceaccount.com"

# Production
gh secret set PROD_DATABASE_URL -b"postgresql://..."
gh secret set PROD_REDIS_URL -b"redis://HOST:PORT"
gh secret set PROD_SERVICE_ACCOUNT -b"legallens-production@PROJECT.iam.gserviceaccount.com"

# Optional: Sentry
gh secret set SENTRY_DSN -b"https://xxxxx@sentry.io/xxxxx"

# Optional: Codecov
gh secret set CODECOV_TOKEN -b"your-codecov-token"

# Optional: Slack notifications
gh secret set SLACK_WEBHOOK -b"https://hooks.slack.com/services/..."
```

### 3. Environment Variables

#### Staging (`.env.staging`)
```bash
ENVIRONMENT=staging
LOG_LEVEL=INFO

# Database
DATABASE_URL=<from-secret-manager>

# Redis
REDIS_URL=redis://HOST:PORT
CELERY_BROKER_URL=redis://HOST:PORT

# JWT
JWT_SECRET=<from-secret-manager>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30

# Storage
S3_BUCKET=legallens-staging
S3_ENDPOINT_URL=  # Empty for GCS
S3_ACCESS_KEY_ID=<from-secret-manager>
S3_SECRET_ACCESS_KEY=<from-secret-manager>

# LLM APIs
ANTHROPIC_API_KEY=<from-secret-manager>
VOYAGE_API_KEY=<from-secret-manager>

# CORS
CORS_ORIGINS=https://staging.legallens.com

# Monitoring
SENTRY_DSN=<optional>
```

#### Production (`.env.production`)
```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING

# Database
DATABASE_URL=<from-secret-manager>

# Redis
REDIS_URL=redis://HOST:PORT
CELERY_BROKER_URL=redis://HOST:PORT

# JWT
JWT_SECRET=<from-secret-manager>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30

# Storage
S3_BUCKET=legallens-production
S3_ENDPOINT_URL=  # Empty for GCS
S3_ACCESS_KEY_ID=<from-secret-manager>
S3_SECRET_ACCESS_KEY=<from-secret-manager>

# LLM APIs
ANTHROPIC_API_KEY=<from-secret-manager>
VOYAGE_API_KEY=<from-secret-manager>

# CORS
CORS_ORIGINS=https://legallens.com

# Monitoring
SENTRY_DSN=<required>
```

---

## CI/CD Configuration

### 1. GitHub Environments

#### Create Production Environment
1. Go to **Settings → Environments → New environment**
2. Name: `production`
3. **Protection rules**:
   - ✅ Required reviewers (add team members)
   - ✅ Wait timer: 0 minutes
   - ✅ Branch restrictions: `main` only

#### Configure Branch Protection
```bash
# Using GitHub API or web interface:
# Settings → Branches → Add rule

# Branch name pattern: main
# Require status checks to pass:
#   - ci-success
# Require pull request reviews: 1 approval
# Require conversation resolution
# Include administrators
```

### 2. Codecov Integration (Optional)

```bash
# Sign up at https://codecov.io
# Add repository
# Copy token

# Add to GitHub secrets
gh secret set CODECOV_TOKEN -b"YOUR_TOKEN"

# codecov.yml is already in repository
```

### 3. Sentry Integration (Optional)

```bash
# Create project at https://sentry.io
# Copy DSN

# Add to GitHub secrets
gh secret set SENTRY_DSN -b"https://xxxxx@sentry.io/xxxxx"

# Sentry is automatically configured in main.py
```

---

## Deployment Procedures

### Staging Deployment (Automatic)

**Trigger**: Push to `main` branch

**Process**:
1. Merge PR to `main`
2. GitHub Actions automatically:
   - Builds Docker images
   - Runs database migrations
   - Deploys to Cloud Run staging
   - Runs smoke tests
   - Rolls back on failure

**Monitoring**:
```bash
# View logs
gcloud run services logs read legallens-api-staging \
  --region=$REGION --limit=50

# Check deployment status
gcloud run services describe legallens-api-staging \
  --region=$REGION --format="value(status.url,status.latestReadyRevisionName)"
```

### Production Deployment (Manual)

**Trigger**: Manual workflow dispatch with version tag

**Prerequisites**:
- All tests passing on `main`
- Version tag created (e.g., `v1.0.0`)
- Manual approval from designated reviewers

**Process**:
```bash
# 1. Create and push version tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# 2. Trigger deployment
# Go to: Actions → Deploy to Production → Run workflow
# Input version: v1.0.0

# 3. Approve deployment
# Wait for approval request in GitHub UI
# Review deployment summary
# Click "Approve and deploy"

# 4. Monitor deployment
# Blue-green deployment automatically:
#   - Deploys new revision (0% traffic)
#   - Runs comprehensive tests
#   - Gradually shifts traffic: 10% → 50% → 100%
#   - Monitors for errors

# 5. Verify production
curl https://api.legallens.com/health
curl https://api.legallens.com/health/ready
```

### Database Migrations

**Staging** (automatic):
```bash
# Migrations run automatically in CI/CD
# View migration logs in GitHub Actions

# Manual migration (if needed)
cd apps/api
export DATABASE_URL="postgresql://..."
alembic upgrade head
```

**Production** (automatic with backup):
```bash
# Automatic backup created before migration
# Manual backup (if needed)
gcloud sql backups create \
  --instance=legallens-production \
  --description="Manual backup before migration"

# Manual migration (emergency only)
cd apps/api
export DATABASE_URL="postgresql://..."
alembic upgrade head

# Rollback migration (emergency only)
alembic downgrade -1
```

---

## Rollback Procedures

### Automatic Rollback

**When**: Smoke tests fail during staging deployment

**Process**: Automatic (no action needed)
- GitHub Actions detects failure
- Reverts to previous Cloud Run revision
- Sends notification

### Manual Rollback: Cloud Run Revision

```bash
# 1. List recent revisions
gcloud run revisions list \
  --service=legallens-api-production \
  --region=$REGION \
  --limit=5

# 2. Identify stable revision
# Look for revision before failed deployment

# 3. Rollback traffic
gcloud run services update-traffic legallens-api-production \
  --region=$REGION \
  --to-revisions=STABLE_REVISION_NAME=100

# 4. Verify
curl https://api.legallens.com/health
```

### Manual Rollback: Database Migration

```bash
# 1. Check current revision
cd apps/api
export DATABASE_URL="postgresql://..."
alembic current

# 2. View migration history
alembic history

# 3. Rollback to specific revision
alembic downgrade REVISION_ID

# Or rollback one step
alembic downgrade -1

# 4. Verify
psql $DATABASE_URL -c "SELECT * FROM alembic_version;"
```

### Rollback: Restore Database Backup

```bash
# 1. List backups
gcloud sql backups list \
  --instance=legallens-production

# 2. Restore backup
gcloud sql backups restore BACKUP_ID \
  --backup-instance=legallens-production \
  --backup-id=BACKUP_ID

# 3. Verify
# Check application logs
# Test critical endpoints
```

---

## Troubleshooting

### Deployment Fails: Image Build Error

**Symptoms**: Docker build fails in GitHub Actions

**Solutions**:
```bash
# Test build locally
cd apps/api
docker build -t test-build .

# Check for:
# - Missing dependencies in requirements.txt
# - Syntax errors in Dockerfile
# - Large file sizes (exceeds layer limits)

# Clear GitHub Actions cache
# Go to: Actions → Caches → Delete all caches
```

### Deployment Fails: Database Migration Error

**Symptoms**: Alembic upgrade fails

**Solutions**:
```bash
# 1. Check migration logs
# GitHub Actions → deploy-staging → migrate job

# 2. Test migration locally
cd apps/api
export DATABASE_URL="postgresql://..."
alembic upgrade head --sql  # Dry run

# 3. Common issues:
# - Duplicate column/table (check if migration already ran)
# - Foreign key constraint violation (data inconsistency)
# - Syntax error in migration file

# 4. Fix and retry
# Update migration file
# Push to branch
# Re-run deployment
```

### Deployment Fails: Smoke Tests

**Symptoms**: Health checks return 503 or timeout

**Solutions**:
```bash
# 1. Check Cloud Run logs
gcloud run services logs read legallens-api-staging \
  --region=$REGION --limit=100

# 2. Common issues:
# - Database connection failed (check DATABASE_URL secret)
# - Redis connection failed (check REDIS_URL)
# - Storage access denied (check service account permissions)
# - Missing environment variable

# 3. Test locally with staging config
cd apps/api
export DATABASE_URL="..."  # Use staging values
export REDIS_URL="..."
uvicorn app.main:app --reload

curl http://localhost:8000/health/ready
```

### Production: High Error Rate

**Symptoms**: 5xx errors, alert fired

**Solutions**:
```bash
# 1. Check error details in Sentry
# Go to: Sentry dashboard → Filter by time range

# 2. Check recent deployments
gcloud run revisions list \
  --service=legallens-api-production \
  --region=$REGION

# 3. Rollback if recent deployment
# See "Rollback Procedures" above

# 4. Check resource limits
gcloud run services describe legallens-api-production \
  --region=$REGION \
  --format="yaml(spec.template.spec.containers[0].resources)"

# 5. Scale up if needed
gcloud run services update legallens-api-production \
  --region=$REGION \
  --max-instances=50 \
  --memory=4Gi
```

### Production: High Latency

**Symptoms**: Slow response times, P95 > 2s

**Solutions**:
```bash
# 1. Check Cloud Run metrics
# Go to: Cloud Console → Cloud Run → Select service → Metrics

# 2. Check database performance
gcloud sql operations list \
  --instance=legallens-production \
  --limit=10

# 3. Check slow queries
# Cloud SQL → Query Insights

# 4. Scale up database
gcloud sql instances patch legallens-production \
  --tier=db-custom-8-32768

# 5. Add database indexes (if needed)
# Create migration with indexes for slow queries
```

---

## Operational Runbooks

### Weekly Maintenance

```bash
# 1. Review error rates (Sentry)
# Check for new error patterns

# 2. Review performance metrics
# Cloud Console → Monitoring → Dashboards

# 3. Check disk usage
gcloud sql instances describe legallens-production \
  --format="value(settings.dataDiskSizeGb,currentDiskSize)"

# 4. Review and delete old revisions
gcloud run revisions list \
  --service=legallens-api-production \
  --region=$REGION

# Delete revisions older than 30 days (keep at least 5)

# 5. Check backup status
gcloud sql backups list --instance=legallens-production

# 6. Review logs for warnings
gcloud logging read "severity>=WARNING" --limit=50
```

### Monthly Maintenance

```bash
# 1. Rotate secrets
# Generate new JWT secret
# Update in Secret Manager
# Redeploy application

# 2. Review IAM permissions
gcloud projects get-iam-policy $PROJECT_ID

# 3. Security audit
# Run: npm audit (web)
# Run: safety check (API)
# Review Dependabot alerts

# 4. Update dependencies
# Update package.json (web)
# Update requirements.txt (API)
# Test in staging before production

# 5. Review costs
# Cloud Console → Billing → Reports
# Check for unexpected increases

# 6. Disaster recovery test
# Restore staging from production backup
# Verify data integrity
```

### Incident Response Checklist

**When alert fires**:

- [ ] Acknowledge alert (Slack/PagerDuty)
- [ ] Check Sentry for error details
- [ ] Check Cloud Run logs for patterns
- [ ] Identify affected services (API/Web/Database)
- [ ] Determine severity (P0-P4)
- [ ] Notify stakeholders if P0/P1
- [ ] Implement mitigation (rollback/scale/fix)
- [ ] Verify resolution (health checks, metrics)
- [ ] Document in incident log
- [ ] Schedule post-mortem if P0/P1

**Severity Levels**:
- **P0**: Complete outage, all users affected
- **P1**: Major feature broken, many users affected
- **P2**: Minor feature broken, some users affected
- **P3**: Performance degradation
- **P4**: Minor issue, no user impact

---

## DNS and Domain Setup

### Custom Domain Configuration

#### Staging
```bash
# Map staging domain
gcloud run services update legallens-api-staging \
  --region=$REGION \
  --platform=managed \
  --add-custom-domain=api-staging.legallens.com

# Follow instructions to add DNS records
# Wait for SSL certificate provisioning (15-60 min)
```

#### Production
```bash
# Map production domain
gcloud run services update legallens-api-production \
  --region=$REGION \
  --platform=managed \
  --add-custom-domain=api.legallens.com

# DNS records (add to your DNS provider):
# A record: api.legallens.com → Cloud Run IP
# AAAA record: api.legallens.com → Cloud Run IPv6 (if applicable)
```

---

## Additional Resources

### Documentation
- [Architecture Overview](.context/architecture.md)
- [Security Guide](.context/security.md)
- [Monitoring Guide](.context/monitoring.md)
- [Rate Limiting](.context/rate-limiting.md)
- [CI/CD README](.github/workflows/README.md)

### External Links
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Best Practices](https://cloud.google.com/sql/docs/postgres/best-practices)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Sentry Documentation](https://docs.sentry.io/)

### Support Contacts
- **On-call**: [Configure PagerDuty]
- **Slack**: #legallens-alerts, #legallens-deploys
- **Email**: ops@legallens.com

---

## Deployment Checklist

### Pre-Launch
- [ ] Infrastructure provisioned (database, Redis, storage)
- [ ] Secrets configured (Secret Manager + GitHub)
- [ ] Service accounts created with correct permissions
- [ ] CI/CD pipelines tested (staging deployment successful)
- [ ] Monitoring configured (Sentry, Cloud Monitoring, alerts)
- [ ] Documentation reviewed and updated
- [ ] Backup and restore procedures tested
- [ ] Load testing completed
- [ ] Security audit completed

### Launch Day
- [ ] Create v1.0.0 release tag
- [ ] Trigger production deployment
- [ ] Approve deployment (manual gate)
- [ ] Monitor deployment progress
- [ ] Verify health checks pass
- [ ] Test critical user flows
- [ ] Monitor error rates for 1 hour
- [ ] Update status page
- [ ] Announce launch

### Post-Launch
- [ ] Monitor for 24 hours
- [ ] Review error rates daily (first week)
- [ ] Gather user feedback
- [ ] Document lessons learned
- [ ] Schedule post-launch retrospective

---

**Last Updated**: Phase 8 — January 2025  
**Maintained By**: DevOps Team  
**Review Cycle**: Monthly
