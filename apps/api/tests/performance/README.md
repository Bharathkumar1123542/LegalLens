# LegalLens Performance Tests

Load and performance testing suite using Locust.

## Overview

This directory contains load tests for validating LegalLens can handle:
- **100 concurrent users** (architecture.md requirement)
- **P95 latency < 2s** for read operations
- **P95 latency < 5s** for write operations

## Setup

### Install Locust

```bash
pip install locust
```

Or add to requirements:
```bash
echo "locust>=2.15.0" >> requirements.txt
pip install -r requirements.txt
```

### Start LegalLens Stack

Before running tests, ensure the full stack is running:

```bash
# Start with Docker Compose
./scripts/dev-start.sh  # Linux/Mac
./scripts/dev-start.ps1  # Windows

# Or manually
docker-compose -f infra/docker-compose.yml up -d
```

## Running Tests

### Web UI Mode (Recommended)

Start Locust web interface:

```bash
cd apps/api/tests/performance
locust -f locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser:
1. Set number of users: **100**
2. Set spawn rate: **10** users/second
3. Click "Start Swarming"

### Headless Mode (CI/CD)

Run automated test:

```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless \
  --html=performance_report.html
```

Parameters:
- `--users=100`: Total concurrent users
- `--spawn-rate=10`: Add 10 users/second until reaching 100
- `--run-time=5m`: Run for 5 minutes
- `--headless`: No web UI
- `--html`: Generate HTML report

### Quick Test

For quick validation (10 users, 1 minute):

```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users=10 \
  --spawn-rate=5 \
  --run-time=1m \
  --headless
```

## User Types

### LegalLensUser (Default)
Simulates typical user workflow:
- Upload documents (weight: 1)
- List documents (weight: 3)
- Get document details (weight: 2)
- Simplify documents (weight: 1)
- Extract clauses (weight: 1)
- Chat with documents (weight: 2)
- Create comparisons (weight: 1)
- Create exports (weight: 1)

### ReadHeavyUser
Focuses on read operations:
- List documents frequently (weight: 10)
- Health checks (weight: 1)

### WriteHeavyUser
Focuses on write operations:
- Upload documents (weight: 5)
- Extract clauses (weight: 3)
- Create exports (weight: 2)

## Test Scenarios

### Scenario 1: Mixed Load (Default)
```bash
locust -f locustfile.py --host=http://localhost:8000
```
Uses `LegalLensUser` for balanced read/write mix.

### Scenario 2: Read-Heavy Load
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --class-picker --users=100 --spawn-rate=10 \
  --run-time=5m --headless
```
Manually select `ReadHeavyUser` in web UI or use tag:

```python
# In locustfile.py
locust -f locustfile.py --host=http://localhost:8000 \
  --tags read-heavy
```

### Scenario 3: Write-Heavy Load
Similar to above but with `WriteHeavyUser`.

### Scenario 4: Spike Test
Rapid user increase:
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users=100 --spawn-rate=50 \
  --run-time=3m --headless
```

### Scenario 5: Endurance Test
Long-running stability test:
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users=50 --spawn-rate=5 \
  --run-time=30m --headless
```

## Performance Targets

Per architecture.md requirements:

| Metric | Target | Notes |
|--------|--------|-------|
| Concurrent Users | 100 | Max simultaneous users |
| Read Operations P95 | < 2s | GET /documents, /clauses, etc. |
| Write Operations P95 | < 5s | POST /documents, /comparisons, etc. |
| API Availability | > 99.5% | < 0.5% error rate |
| Throughput | > 10 req/sec/user | Sustained load |

## Metrics to Monitor

### Latency
- **P50 (Median)**: Typical response time
- **P95**: 95th percentile (target thresholds)
- **P99**: 99th percentile (tail latencies)
- **Max**: Worst-case latency

### Throughput
- **Requests/second**: Overall system throughput
- **Requests/user**: Per-user throughput

### Errors
- **Failure rate**: % of failed requests
- **Error types**: HTTP 4xx vs 5xx errors

### Resource Utilization
Monitor these in parallel with Locust:
- CPU usage (API, worker, DB)
- Memory usage
- Database connections
- Redis memory
- S3/MinIO operations

## Interpreting Results

### Good Results ✅
```
Total Requests: 50,000+
Failure Rate: <0.5%
Median: <500ms
P95: <2000ms (reads), <5000ms (writes)
RPS: >10 per user
```

### Warning Signs ⚠️
```
Failure Rate: 0.5% - 2%
P95: 2-3s (reads), 5-7s (writes)
Increasing response times over test duration
```

### Critical Issues ❌
```
Failure Rate: >2%
P95: >3s (reads), >7s (writes)
Timeout errors
503 Service Unavailable
Connection errors
```

## Troubleshooting

### High Latency
1. Check database query performance (`EXPLAIN ANALYZE`)
2. Verify Redis caching is working
3. Check LLM API latency (mock for load tests)
4. Review worker queue depth

### High Error Rate
1. Check API logs: `docker logs legallens-api`
2. Check database connections
3. Verify worker capacity
4. Check rate limiting

### Resource Exhaustion
1. Scale workers: Increase Celery worker instances
2. Scale API: Add more API containers
3. Database: Increase connection pool
4. Redis: Increase memory limit

## CI/CD Integration

Add to GitHub Actions:

```yaml
- name: Run Performance Tests
  run: |
    locust -f apps/api/tests/performance/locustfile.py \
      --host=http://localhost:8000 \
      --users=50 \
      --spawn-rate=10 \
      --run-time=3m \
      --headless \
      --html=performance_report.html \
      --csv=performance_metrics
    
- name: Upload Performance Report
  uses: actions/upload-artifact@v3
  with:
    name: performance-report
    path: performance_report.html
```

## Best Practices

1. **Consistent Environment**: Always test against same infrastructure
2. **Baseline First**: Run baseline tests before changes
3. **Gradual Ramp**: Use realistic spawn rates (5-10 users/sec)
4. **Sufficient Duration**: Run for at least 5 minutes
5. **Monitor Resources**: Watch CPU, memory, DB during tests
6. **Isolated Tests**: Don't run on production or shared dev environments
7. **Mock External APIs**: Mock LLM calls for consistent results

## Advanced Configuration

### Custom User Distribution

```python
from locust import User

class MyLoadTest(User):
    tasks = {
        LegalLensUser: 7,      # 70% mixed users
        ReadHeavyUser: 2,       # 20% read-heavy
        WriteHeavyUser: 1,      # 10% write-heavy
    }
```

### Custom Wait Times

```python
from locust import constant, constant_pacing

# Fixed 1 second wait
wait_time = constant(1)

# Ensure requests every 2 seconds
wait_time = constant_pacing(2)
```

### Tags for Selective Testing

```python
@task(3)
@tag('read', 'fast')
def list_documents(self):
    pass

@task(1)
@tag('write', 'slow')
def upload_document(self):
    pass
```

Run only fast tests:
```bash
locust -f locustfile.py --tags fast
```

## Report Analysis

After test completion:
1. Open `performance_report.html`
2. Check "Charts" tab for time series
3. Review "Failures" tab for error patterns
4. Compare with baseline metrics
5. Document P95/P99 latencies

## See Also

- Locust documentation: https://docs.locust.io/
- Architecture.md: Performance requirements
- Implementation-plan.md: Phase 7 performance goals
