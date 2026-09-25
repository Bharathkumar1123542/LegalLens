# Security Hardening — LegalLens Phase 8

**Status**: ✅ Implemented  
**Last Updated**: Phase 8  
**Compliance**: OWASP Top 10, architecture.md §10

## Overview

Comprehensive security measures implemented across LegalLens to protect against common vulnerabilities and attacks.

## Security Layers

### 1. Rate Limiting (DDoS & Brute Force Protection)

**Implementation**: `app/core/rate_limiter.py`

**Features**:
- Redis-backed distributed rate limiting
- Per-user and per-IP limits
- Endpoint-specific limits (auth: 5-20/min, LLM: 20-60/hr)
- 429 responses with Retry-After headers

**See**: `.context/rate-limiting.md`

### 2. File Upload Security

**Implementation**: `app/core/file_validator.py`

#### Magic-Byte Validation

Per code-standards.md: "Files validated by magic-byte inspection, NOT extension"

```python
# Using python-magic (libmagic)
detected_mime = magic.from_buffer(file_bytes, mime=True)

# Cross-validate with extension
if extension doesn't match detected:
    raise FileValidationError("Type mismatch")
```

#### File Size Limits

| Type | Limit | Rationale |
|------|-------|-----------|
| PDF | 50 MB | Multi-page legal documents |
| DOCX | 25 MB | Smaller than PDFs typically |
| TXT | 10 MB | Plain text is compact |
| Global | 100 MB | Absolute maximum |

#### Dangerous Pattern Detection

Blocks files containing:
- `<script>` tags (XSS attempts)
- `<?php` code (code injection)
- `#!/bin/bash` scripts (shell injection)
- PE/ELF executable headers
- Null bytes in text files

#### Structure Validation

**PDF**:
- Must start with `%PDF-`
- Should contain `%%EOF` marker
- Version extracted and logged

**DOCX**:
- Must have ZIP signature (`PK\x03\x04`)
- Must contain `word/` directory structure
- Verifies `word/document.xml` reference

**Text**:
- Must be valid UTF-8
- No null bytes
- No binary content

### 3. Authentication Security

**Implementation**: `app/core/security.py`, `app/api/v1/auth.py`

#### Password Requirements

- Minimum 8 characters
- Hashed with bcrypt (cost factor 12)
- Never logged or stored in plaintext

#### Token Security

- JWT with HS256 algorithm
- Access token: 15-minute expiry
- Refresh token: 7-day expiry with rotation
- Tokens signed with 256-bit secret

#### Brute Force Protection

- Login: 10 attempts/minute
- Register: 5 attempts/minute
- Rate limits enforced before DB queries

#### User Enumeration Prevention

- Identical error messages for wrong email vs wrong password
- No "user not found" vs "wrong password" distinction
- Timing-safe comparisons

### 4. Authorization

**Implementation**: `app/core/deps.py`, all API endpoints

#### Ownership Enforcement

Every resource-scoped endpoint:
```python
async def _get_owned_doc(document_id, current_user, db):
    doc = await db.get(Document, document_id)
    if doc.owner_id != current_user.id:
        raise HTTPException(404)  # Not 403!
```

**404 not 403**: Don't reveal resource existence to unauthorized users

#### JWT Validation

- Signature verified on every request
- Expiry checked
- User ID extracted and validated
- Invalid tokens → 401 Unauthorized

### 5. Database Security

**Implementation**: SQLAlchemy with async PostgreSQL

#### SQL Injection Prevention

- ORM queries (parameterized automatically)
- No raw SQL with user input
- Input validated by Pydantic before queries

#### Connection Security

- SSL/TLS for production connections
- Connection pooling with limits
- Credentials never logged

### 6. API Security

#### CORS Configuration

**Development**:
```python
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

**Production**:
```python
CORS_ORIGINS=https://legallens.com,https://app.legallens.com
# NEVER use * in production
```

#### Security Headers

```python
# In next.config.js (frontend)
headers: [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-XSS-Protection", value: "1; mode=block" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
]
```

#### Input Validation

- All inputs validated by Pydantic schemas
- Type checking enforced
- Size limits on all fields
- No HTML/script tags in text fields

### 7. Secrets Management

#### Environment Variables

**Never commit**:
- `JWT_SECRET`
- `ANTHROPIC_API_KEY`
- `VOYAGE_API_KEY`
- `DATABASE_URL` (with password)
- `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`

**Storage**:
- Development: `.env` file (gitignored)
- Staging: GitHub Secrets
- Production: Cloud Secret Manager (GCP/AWS)

#### Logging

Per code-standards.md: "Secrets never logged"

```python
# ✅ Good
logger.info("user_authenticated", user_id=user.id)

# ❌ Bad - NEVER DO THIS
logger.info("user_authenticated", email=email, token=token)
```

### 8. External API Security

#### LLM API Keys

- Stored in environment variables
- Never sent to frontend
- Rate limited to control costs
- Requests/responses logged (without PII)

#### S3/Storage

- Pre-signed URLs with short expiry (15 minutes)
- Bucket access restricted by IAM
- No public read access
- Encryption at rest enabled

### 9. Content Security

#### PII Protection

- User emails never returned in list endpoints
- Document content never logged
- Chat history sanitized in logs
- Audit logs retain user_id only (not content)

#### XSS Prevention

- Frontend: React auto-escapes by default
- Backend: No HTML in API responses (JSON only)
- Markdown sanitized before rendering

#### CSRF Protection

- JWT in Authorization header (not cookies)
- SameSite cookie attribute if used
- CORS restrictions enforced

## Security Testing

### Unit Tests

Located in `tests/unit/`:
- `test_rate_limiter.py` — 22 tests
- `test_file_validator.py` — 29 tests
- `test_security.py` — Password hashing, token generation

### Integration Tests

- Ownership enforcement (cross-user access blocked)
- Rate limit enforcement (429 responses)
- File upload validation (malicious files rejected)

### Security Scanning

**CI Pipeline**:
- Bandit: Static security analysis
- Safety: Dependency vulnerability checking
- Ruff: Code quality and security linting

**Run locally**:
```bash
bandit -r app/
safety check
```

## Vulnerability Disclosure

### Reporting

Email: security@legallens.com (if available)  
Or: GitHub Security Advisories (private disclosure)

### Response Time

- Critical: 24 hours
- High: 72 hours
- Medium: 1 week
- Low: 2 weeks

## Compliance

### OWASP Top 10 (2021)

| Vulnerability | Mitigation |
|--------------|------------|
| A01: Broken Access Control | Ownership checks on all endpoints |
| A02: Cryptographic Failures | bcrypt passwords, JWT tokens, TLS |
| A03: Injection | ORM queries, input validation |
| A04: Insecure Design | Rate limiting, file validation |
| A05: Security Misconfiguration | Secure defaults, no debug in prod |
| A06: Vulnerable Components | Safety checks, pinned versions |
| A07: Auth Failures | Strong passwords, token expiry |
| A08: Data Integrity Failures | File validation, checksums |
| A09: Logging Failures | Structured logs, no secrets |
| A10: SSRF | No user-controlled URLs |

### GDPR

- PII encrypted at rest and in transit
- User data deletable on request
- Audit logs for data access
- Data minimization (only necessary data stored)

### SOC 2 (Future)

- Access controls implemented
- Audit logging in place
- Encryption standards met
- Incident response plan ready

## Production Hardening

### Checklist

Before production deployment:

- [ ] All secrets in Secret Manager (not .env)
- [ ] CORS limited to production domains
- [ ] Debug mode disabled
- [ ] HTTPS enforced (no HTTP)
- [ ] Rate limiting enabled
- [ ] File validation active
- [ ] Database SSL/TLS enabled
- [ ] S3 bucket private (no public read)
- [ ] Monitoring and alerting configured
- [ ] Security headers added
- [ ] Dependency scan passed
- [ ] Penetration test completed

### Environment Variables

**Required for production**:
```bash
ENVIRONMENT=production
DEBUG=false
SENTRY_DSN=https://...  # Error tracking
JWT_SECRET=<256-bit-random>
DATABASE_URL=postgresql+asyncpg://...?ssl=require
CORS_ORIGINS=https://app.legallens.com
```

## Incident Response

### Detection

- Monitor for high 429 rate (DDoS)
- Alert on repeated 401s from same IP (brute force)
- Track failed file uploads (malicious uploads)
- Monitor Sentry for exceptions

### Response Steps

1. **Identify**: What type of attack?
2. **Contain**: Block offending IPs, disable features
3. **Eradicate**: Fix vulnerability, patch system
4. **Recover**: Restore from backups if needed
5. **Learn**: Post-mortem, update procedures

### Contacts

- On-call engineer: [PagerDuty/phone]
- Security lead: [email]
- Infrastructure: [email]
- Legal (breach disclosure): [email]

## Security Roadmap

### Phase 9+ Enhancements

1. **WAF (Web Application Firewall)**
   - Cloud Armor (GCP) or AWS WAF
   - Bot detection
   - DDoS mitigation

2. **Advanced Authentication**
   - Multi-factor authentication (MFA/2FA)
   - OAuth2 social login
   - Session management improvements

3. **Content Scanning**
   - ClamAV malware scanning
   - Document anomaly detection
   - Encrypted file handling

4. **Audit & Compliance**
   - SOC 2 audit preparation
   - HIPAA compliance (if medical documents)
   - Regular penetration testing

5. **Zero-Trust Architecture**
   - Service mesh (Istio)
   - mTLS between services
   - Policy-based access control

## Resources

### Documentation

- `architecture.md §10` — Mitigation Strategies
- `code-standards.md §Security` — Security rules
- `.context/rate-limiting.md` — Rate limiting details
- `.github/workflows/README.md` — Security scanning in CI

### Tools

- [OWASP ZAP](https://www.zaproxy.org/) — Security scanner
- [Bandit](https://bandit.readthedocs.io/) — Python security linter
- [Safety](https://pyup.io/safety/) — Dependency checker
- [Snyk](https://snyk.io/) — Vulnerability scanning

### Training

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [PortSwigger Web Security Academy](https://portswigger.net/web-security)
- [Google Cloud Security Best Practices](https://cloud.google.com/security/best-practices)

## Support

For security questions or concerns:
1. Review this documentation
2. Check `architecture.md §10`
3. Run security scans locally
4. Contact security team

**Remember**: Security is everyone's responsibility. When in doubt, ask!
