# Rate Limiting — LegalLens Phase 8

**Status**: ✅ Implemented  
**Module**: `app/core/rate_limiter.py`  
**Backend**: Redis (fixed-window strategy)

## Overview

Rate limiting prevents abuse, protects against DDoS attacks, and controls LLM API costs. Implemented using `slowapi` with Redis storage for distributed rate limiting across multiple API instances.

## Implementation

### Identifier Strategy

Per architecture.md §10, rate limits use:
1. **Authenticated users**: User ID (`user:{uuid}`)
2. **Unauthenticated**: IP address (`ip:{address}`)

This prevents authenticated users from bypassing limits by changing IPs.

### Rate Limit Categories

| Category | Limit | Rationale |
|----------|-------|-----------|
| **Authentication** | | Prevent brute force attacks |
| Register | 5/minute | Strict limit on account creation |
| Login | 10/minute | Moderate limit on login attempts |
| Refresh | 20/minute | Higher limit for token refreshes |
| **Upload** | | Prevent storage abuse |
| Document Upload | 10/hour | Reasonable upload frequency |
| **LLM Operations** | | Control API costs |
| Simplify | 30/hour | Expensive LLM operation |
| Extract Clauses | 30/hour | Expensive LLM operation |
| Chat | 60/hour | Moderate LLM usage |
| Compare | 20/hour | Very expensive (multi-doc LLM) |
| **Export** | | Moderate limits |
| Create Export | 50/hour | Reasonable export frequency |
| **Read Operations** | | Generous limits |
| List/Get | 200/minute | Normal browsing patterns |
| **Health Check** | | Very high limit |
| Health | 1000/minute | Monitoring tools |

## Configuration

### Environment Variables

```bash
# Redis connection (shared with Celery)
REDIS_URL=redis://localhost:6379/0
```

### Customization

To adjust limits, edit `app/core/rate_limiter.py`:

```python
class RateLimits:
    AUTH_LOGIN = "10/minute"  # Increase to 20/minute if needed
    SIMPLIFY = "30/hour"      # Adjust based on API budget
```

## Response Headers

Rate limit status included in every response:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1695123456
```

## Error Response

When rate limit exceeded, API returns 429:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

With headers:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
```

## Testing

### Unit Tests

Located in `tests/unit/test_rate_limiter.py`:
- Identifier extraction (user ID vs IP)
- Endpoint limit configuration
- Limit format validation
- Security: Auth limits strictest

### Integration Testing

Test rate limiting with real requests:

```bash
# Test login rate limit (10/minute)
for i in {1..15}; do
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}' \
    -w "\nStatus: %{http_code}\n"
done

# First 10: 401 (Unauthorized)
# Next 5: 429 (Rate Limit Exceeded)
```

### Load Testing

Locust tests include rate limit scenarios:

```python
# apps/api/tests/performance/locustfile.py
class LegalLensUser(FastHttpUser):
    @task
    def test_rate_limit(self):
        # Intentionally hit rate limits to test behavior
        for i in range(15):
            self.client.post("/api/v1/auth/login", ...)
```

## Monitoring

### Logs

Rate limit events logged for monitoring:

```json
{
  "event": "http_request",
  "path": "/api/v1/auth/login",
  "status_code": 429,
  "identifier": "ip:192.168.1.1",
  "level": "warning"
}
```

### Metrics

Track rate limit metrics:
- Total 429 responses
- 429 responses by endpoint
- Top rate-limited IPs/users
- Average remaining requests

### Alerts

Set up alerts for:
- High 429 response rate (>5% of requests)
- Specific user hitting limits repeatedly
- Suspicious patterns (distributed brute force)

## Production Considerations

### Redis High Availability

For production, use Redis cluster or sentinel:

```yaml
# docker-compose.yml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
  restart: unless-stopped
```

### Distributed Deployment

Rate limits work across multiple API instances (shared Redis state):

```
Load Balancer
    ├── API Instance 1 ─┐
    ├── API Instance 2 ─┼─► Redis (shared state)
    └── API Instance 3 ─┘
```

### Rate Limit Bypass

For internal services or trusted IPs, bypass limits:

```python
# In rate_limiter.py
def get_identifier(request: Request) -> str:
    # Bypass for internal services
    if request.headers.get("X-Internal-Service") == settings.INTERNAL_SECRET:
        return "internal:bypass"
    
    # Normal identifier logic...
```

### Dynamic Limits

Adjust limits based on user tier:

```python
def get_user_tier_limit(user_id: str) -> str:
    user = get_user(user_id)
    if user.subscription == "premium":
        return "100/hour"  # Higher limit
    return "30/hour"  # Standard limit
```

## Security Benefits

### DDoS Protection

- Limits prevent resource exhaustion
- Per-IP limits catch distributed attacks
- Redis quickly rejects excessive requests

### Brute Force Prevention

- Login: 10 attempts/minute (600 attempts/hour max)
- After 10 failed logins, user must wait 1 minute
- Register: 5/minute prevents mass account creation

### Cost Control

- LLM endpoints limited to 30-60 requests/hour
- Prevents runaway API bills from malicious users
- Budget predictable based on user count

### Resource Protection

- Upload limits prevent storage filling
- Export limits prevent CPU/memory exhaustion
- Read limits prevent database overload

## Troubleshooting

### "Redis connection failed"

Rate limiter continues working (swallow_errors=True) but:
- Falls back to in-memory storage (not distributed)
- Limits only enforced per API instance
- Warning logged

Check Redis:
```bash
redis-cli ping  # Should return PONG
```

### "Rate limit not working"

Check:
1. Redis URL correct in settings
2. Rate limiter initialized in main.py
3. Decorator applied to endpoint
4. Request object passed to endpoint

### "Too restrictive limits"

Adjust in `rate_limiter.py` or add user tiers.

### "Rate limit bypassed"

Verify:
1. Redis shared across all API instances
2. No proxy stripping X-Forwarded-For
3. Identifier correctly extracted

## Future Enhancements

### Phase 9+ Improvements

1. **User Tiers**: Different limits for free/premium
2. **Dynamic Limits**: Adjust based on system load
3. **Whitelist/Blacklist**: IP-based access control
4. **Rate Limit Dashboard**: Real-time monitoring
5. **Smart Limits**: ML-based anomaly detection

### Advanced Features

```python
# Geographic rate limiting
if ip_to_country(ip) in HIGH_RISK_COUNTRIES:
    limit = "5/hour"  # More restrictive

# Time-based limits
if is_business_hours():
    limit = "100/hour"  # Higher during business
else:
    limit = "50/hour"   # Lower at night
```

## Compliance

### GDPR

- IP addresses logged for security only
- Retained for 30 days maximum
- Not shared with third parties

### Terms of Service

Document rate limits in ToS:
- "API limited to X requests per hour"
- "Excessive use may result in throttling"
- "Commercial use requires premium tier"

## See Also

- `architecture.md §10` — Mitigation Strategies
- `app/core/rate_limiter.py` — Implementation
- `tests/unit/test_rate_limiter.py` — Unit tests
- `.github/workflows/README.md` — CI/CD integration

## Support

For rate limit issues:
1. Check Redis connectivity
2. Review endpoint configuration
3. Monitor rate limit logs
4. Adjust limits if legitimate traffic affected
