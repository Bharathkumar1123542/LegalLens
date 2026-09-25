# LegalLens Monitoring & Observability — Phase 8

Comprehensive monitoring setup for production deployment with health checks, metrics collection, error tracking, and alerting.

## Health Check Endpoints

### 1. Liveness Probe: `GET /health`
**Purpose**: Basic application health check for load balancers  
**Response**: `{"status": "ok", "environment": "production"}`  
**Status Codes**:
- `200`: Application is running
- `5xx`: Application is down

**Usage**:
```bash
curl https://api.legallens.com/health
```

**Cloud Run Configuration**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

---

### 2. Readiness Probe: `GET /health/ready`
**Purpose**: Dependency health check — verifies database, Redis, and storage connectivity  
**Response**:
```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "storage": "ok"
  },
  "environment": "production"
}
```

**Status Codes**:
- `200`: All dependencies healthy
- `503`: One or more dependencies unavailable

**Checks Performed**:
1. **Database**: `SELECT 1` query to verify PostgreSQL connectivity
2. **Redis**: `PING` command to verify cache/rate limiter availability
3. **Storage**: S3/GCS list bucket operation (limited to 1 object)

**Usage**:
```bash
curl https://api.legallens.com/health/ready
```

**Cloud Run Configuration**:
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 10
  successThreshold: 1
  failureThreshold: 3
```

---

### 3. Metrics Endpoint: `GET /metrics`
**Purpose**: Application metrics for Prometheus/monitoring systems  
**Response**:
```json
{
  "process_info": {
    "environment": "production",
    "version": "0.1.0"
  },
  "database": {
    "total_connections": 45,
    "active_connections": 8
  },
  "application": {
    "total_documents": 1247,
    "total_users": 89,
    "total_chat_sessions": 523
  }
}
```

**Metrics Collected**:
- Database connection pool statistics
- Application entity counts (documents, users, sessions)
- Process information (version, environment)

**Future Enhancement**:
```python
# Install prometheus_client for standardized metrics
pip install prometheus-client

# Add to main.py:
from prometheus_client import Counter, Histogram, Gauge, generate_latest

request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
active_users = Gauge('active_users', 'Currently active users')
```

---

## Error Tracking: Sentry Integration

### Configuration
**Environment Variables**:
```bash
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
ENVIRONMENT=production  # Tags all events
```

**Features Enabled**:
- FastAPI integration (automatic request tracking)
- SQLAlchemy integration (database query tracking)
- Exception capture with stack traces
- Performance monitoring (transaction tracing)

**Privacy**:
- `send_default_pii=False` — Never captures request bodies or user data
- Headers filtered to exclude `Authorization` tokens

### Sentry Dashboard
**Key Metrics**:
1. **Error Rate**: Errors per minute/hour
2. **Affected Users**: Unique users experiencing errors
3. **Response Time**: P50, P95, P99 latency percentiles
4. **Release Tracking**: Error rates by deployment version

**Alerting Rules**:
```yaml
# Sentry Alert: High Error Rate
condition: error_rate > 10 per minute
notify: slack, email
severity: critical

# Sentry Alert: New Issue
condition: first_seen AND level = error
notify: slack
severity: warning
```

---

## Structured Logging

### Log Format
**Development** (human-readable):
```
2024-01-15 14:23:45 INFO http_request method=POST path=/api/v1/documents status_code=201 duration_ms=145.23
```

**Production** (JSON):
```json
{
  "timestamp": "2024-01-15T14:23:45.123Z",
  "level": "info",
  "event": "http_request",
  "method": "POST",
  "path": "/api/v1/documents",
  "status_code": 201,
  "duration_ms": 145.23,
  "environment": "production"
}
```

### Log Levels
- `DEBUG`: Detailed diagnostic information (development only)
- `INFO`: General application events (default)
- `WARNING`: Unexpected but handled situations
- `ERROR`: Error events that need attention
- `CRITICAL`: Critical failures requiring immediate action

### Key Log Events
```python
# Startup/shutdown
logger.info("legallens_api_starting", environment="production")

# HTTP requests (middleware)
logger.info("http_request", method="POST", path="/api/v1/auth/login", 
            status_code=200, duration_ms=42.5)

# Rate limiting
logger.warning("rate_limit_exceeded", identifier="user:123", 
               limit="20 per hour", endpoint="/api/v1/documents/upload")

# File validation
logger.warning("file_validation_failed", reason="invalid_magic_bytes", 
               claimed_type="pdf", actual_type="text/plain")

# Database operations
logger.info("s3.uploaded", key="documents/abc123.pdf", content_type="application/pdf")
logger.error("s3.upload_failed", key="documents/xyz789.pdf", error="AccessDenied")

# Readiness checks
logger.error("readiness_check_database_failed", error="connection timeout")
```

### Log Retention
- **Development**: Console output (not persisted)
- **Staging**: Cloud Logging, 30 days retention
- **Production**: Cloud Logging, 90 days retention with BigQuery export

---

## Cloud Monitoring (GCP)

### Metrics to Track

#### 1. **Request Metrics**
```yaml
# Cloud Run automatic metrics
- cloudrun.googleapis.com/request_count
- cloudrun.googleapis.com/request_latencies (P50, P95, P99)
- cloudrun.googleapis.com/billable_instance_time
- cloudrun.googleapis.com/container/cpu/utilizations
- cloudrun.googleapis.com/container/memory/utilizations
```

#### 2. **Database Metrics** (Cloud SQL)
```yaml
- cloudsql.googleapis.com/database/cpu/utilization
- cloudsql.googleapis.com/database/memory/utilization
- cloudsql.googleapis.com/database/network/connections
- cloudsql.googleapis.com/database/disk/utilization
```

#### 3. **Storage Metrics** (GCS/S3)
```yaml
- storage.googleapis.com/api/request_count
- storage.googleapis.com/network/sent_bytes_count
- storage.googleapis.com/network/received_bytes_count
```

#### 4. **Redis Metrics** (Memorystore)
```yaml
- redis.googleapis.com/stats/memory/usage
- redis.googleapis.com/stats/cpu_utilization
- redis.googleapis.com/stats/connections/total
```

### Alerting Policies

#### 1. **High Error Rate**
```yaml
name: High HTTP Error Rate (5xx)
condition: |
  cloudrun.request_count
  WHERE response_code >= 500
  > 10 per minute for 5 minutes
notification: slack, email
severity: critical
```

#### 2. **High Latency**
```yaml
name: High Request Latency (P95)
condition: |
  cloudrun.request_latencies (P95)
  > 2000ms for 10 minutes
notification: slack
severity: warning
```

#### 3. **Database Connection Pool Exhaustion**
```yaml
name: Database Connection Pool Near Limit
condition: |
  cloudsql.connections
  > 80% of max_connections for 5 minutes
notification: slack, pagerduty
severity: critical
```

#### 4. **Low Instance Count**
```yaml
name: All Instances Unhealthy
condition: |
  cloudrun.container/instance_count
  = 0 for 2 minutes
notification: slack, pagerduty, sms
severity: critical
```

#### 5. **Disk Usage**
```yaml
name: High Disk Usage (Cloud SQL)
condition: |
  cloudsql.disk.utilization
  > 85% for 15 minutes
notification: email
severity: warning
```

---

## Uptime Monitoring

### External Uptime Checks
Use third-party service (e.g., Pingdom, UptimeRobot, StatusCake):

```yaml
checks:
  - name: API Health
    url: https://api.legallens.com/health
    interval: 1 minute
    timeout: 10 seconds
    expected_status: 200
    locations: [US-East, US-West, EU-West]
  
  - name: Web Application
    url: https://legallens.com
    interval: 1 minute
    timeout: 15 seconds
    expected_status: 200
    locations: [US-East, US-West, EU-West]
  
  - name: API Readiness
    url: https://api.legallens.com/health/ready
    interval: 5 minutes
    timeout: 30 seconds
    expected_status: 200
    locations: [US-East]
```

---

## Dashboards

### 1. **System Health Dashboard**
**Panels**:
- Request rate (requests/sec over time)
- Error rate (5xx errors/min)
- Latency percentiles (P50, P95, P99)
- Instance count (current/min/max)
- CPU utilization
- Memory utilization

### 2. **Database Dashboard**
**Panels**:
- Connection count (active/idle/total)
- Query latency (avg/p95/p99)
- Slow queries (> 1s)
- Disk I/O (read/write MB/s)
- Replication lag (if applicable)

### 3. **Application Dashboard**
**Panels**:
- Document uploads (count/hour)
- User registrations (count/day)
- Chat sessions (active/total)
- Rate limit hits (by category)
- File validation failures (by reason)
- LLM API latency (Anthropic/Voyage)

### 4. **Business Metrics Dashboard**
**Panels**:
- Total users (trend)
- Total documents (trend)
- Document processing time (avg)
- Feature usage (uploads, chat, comparisons, exports)
- User retention (DAU/MAU)

---

## Incident Response

### Runbook: High Error Rate

**Detection**: Alert "High HTTP Error Rate (5xx)" fired

**Investigation Steps**:
1. Check Sentry dashboard for error details
2. Review Cloud Logging for error patterns:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision \
     AND severity>=ERROR" --limit 50 --format json
   ```
3. Check database connectivity: `GET /health/ready`
4. Review recent deployments (potential bad deploy)

**Mitigation**:
- If bad deployment: Rollback via Cloud Run console or:
  ```bash
  gcloud run services update-traffic legallens-api-production \
    --to-revisions=<previous-revision>=100
  ```
- If database issue: Check Cloud SQL status, scale up if needed
- If external API issue: Check Anthropic/Voyage status pages

---

### Runbook: High Latency

**Detection**: Alert "High Request Latency (P95)" fired

**Investigation Steps**:
1. Check Cloud Run metrics for CPU/memory usage
2. Review Cloud SQL connection pool metrics
3. Check Redis latency (if rate limiter slow)
4. Review slow query logs in Cloud SQL

**Mitigation**:
- Scale up Cloud Run instances: Increase max instances
- Scale up database: Increase CPU/memory allocation
- Optimize slow queries: Add indexes, rewrite queries
- Enable Cloud SQL query insights

---

### Runbook: Database Connection Pool Exhaustion

**Detection**: Alert "Database Connection Pool Near Limit" fired

**Investigation Steps**:
1. Check active connections in Cloud SQL:
   ```sql
   SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active';
   ```
2. Review long-running queries:
   ```sql
   SELECT pid, now() - query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'active'
   ORDER BY duration DESC;
   ```

**Mitigation**:
- Terminate idle/stuck connections (with caution)
- Increase connection pool size in Cloud SQL
- Review connection pool settings in SQLAlchemy (`pool_size`, `max_overflow`)
- Add connection pool monitoring

---

## Testing Monitoring

### Health Check Tests
```bash
# Liveness
curl https://api.legallens.com/health
# Expected: {"status": "ok", "environment": "production"}

# Readiness
curl https://api.legallens.com/health/ready
# Expected: 200 with all checks "ok"

# Metrics
curl https://api.legallens.com/metrics
# Expected: JSON with database/application metrics
```

### Sentry Error Test
```bash
# Trigger test error (development only)
curl -X POST https://api-staging.legallens.com/api/v1/test/error
# Check Sentry dashboard for captured event
```

### Load Test
```bash
# Install hey (HTTP load generator)
go install github.com/rakyll/hey@latest

# Run load test
hey -n 1000 -c 10 -m GET https://api.legallens.com/health

# Expected:
# - 200 OK responses
# - P95 latency < 100ms
# - No 5xx errors
```

---

## Monitoring Checklist

**Pre-Launch**:
- [ ] Sentry DSN configured with correct environment
- [ ] Cloud Logging enabled with 90-day retention
- [ ] Uptime monitoring configured (external service)
- [ ] Alert notifications connected (Slack, email, PagerDuty)
- [ ] Dashboards created in Cloud Monitoring
- [ ] Health check endpoints tested (`/health`, `/health/ready`)
- [ ] Runbooks documented for common incidents

**Post-Launch**:
- [ ] Monitor error rates for first 24 hours
- [ ] Review slow query logs weekly
- [ ] Analyze latency percentiles monthly
- [ ] Review and tune alerting thresholds quarterly
- [ ] Update runbooks based on real incidents

---

## Future Enhancements

### 1. **Distributed Tracing**
```python
# Add OpenTelemetry for request tracing
pip install opentelemetry-api opentelemetry-sdk \
  opentelemetry-instrumentation-fastapi \
  opentelemetry-exporter-gcp-trace

# Trace requests across services (API → Database → S3 → LLM APIs)
```

### 2. **Custom Metrics**
```python
# Prometheus client library
from prometheus_client import Counter, Histogram

document_uploads = Counter('document_uploads_total', 'Total document uploads')
llm_latency = Histogram('llm_api_latency_seconds', 'LLM API call duration')
```

### 3. **Real User Monitoring (RUM)**
```javascript
// Frontend performance tracking
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "...",
  integrations: [new Sentry.BrowserTracing()],
  tracesSampleRate: 0.1,
});
```

### 4. **Synthetic Monitoring**
```yaml
# Google Cloud Monitoring uptime checks
- name: API Login Flow
  type: synthetic
  steps:
    - POST /api/v1/auth/login
    - GET /api/v1/documents
  interval: 5 minutes
```

---

## References

- [Google Cloud Logging](https://cloud.google.com/logging/docs)
- [Cloud Run Monitoring](https://cloud.google.com/run/docs/monitoring)
- [Sentry Python SDK](https://docs.sentry.io/platforms/python/guides/fastapi/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Structlog Documentation](https://www.structlog.org/en/stable/)
