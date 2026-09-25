# Content Security Policy (CSP) — Phase 9

Comprehensive security headers implementation for LegalLens web application to prevent XSS attacks and control resource loading.

## Overview

Content Security Policy (CSP) is a security standard that helps prevent:
- Cross-Site Scripting (XSS) attacks
- Data injection attacks
- Clickjacking
- Mixed content issues
- Unauthorized resource loading

## Implemented Headers

### 1. Content-Security-Policy

**Purpose**: Controls which resources the browser is allowed to load

**Configuration** (in `apps/web/next.config.js`):

```javascript
Content-Security-Policy: 
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  font-src 'self' data:;
  connect-src 'self' https://api.legallens.com;
  frame-src 'none';
  object-src 'none';
  base-uri 'self';
  form-action 'self' https://api.legallens.com;
  upgrade-insecure-requests;
  block-all-mixed-content
```

#### Directive Breakdown

**`default-src 'self'`**
- Default policy for all resource types
- Only allow resources from same origin
- Fallback for directives not explicitly set

**`script-src 'self' 'unsafe-inline'`**
- Allow scripts from same origin
- Allow inline scripts (required for Next.js, React)
- Development: Also includes `'unsafe-eval'` for hot reload
- **Trade-off**: `'unsafe-inline'` weakens CSP but required for React
- **Future**: Use nonces or hashes for inline scripts (strict CSP)

**`style-src 'self' 'unsafe-inline'`**
- Allow stylesheets from same origin
- Allow inline styles (required for Tailwind CSS, CSS-in-JS)
- **Trade-off**: `'unsafe-inline'` needed for dynamic styling

**`img-src 'self' data: https:`**
- Allow images from same origin
- Allow data URIs (base64-encoded images)
- Allow HTTPS images from any domain (document previews, user avatars)

**`font-src 'self' data:`**
- Allow fonts from same origin
- Allow data URI fonts (embedded fonts)

**`connect-src 'self' https://api.legallens.com`**
- Allow AJAX/fetch/WebSocket to same origin
- Allow API calls to backend server
- Blocks connections to unauthorized domains

**`frame-src 'none'`**
- Block all iframe embedding
- Prevents clickjacking attacks
- Enforced by `X-Frame-Options: DENY`

**`object-src 'none'`**
- Block `<object>`, `<embed>`, `<applet>` tags
- Prevents Flash and plugin-based attacks

**`base-uri 'self'`**
- Restrict `<base>` tag to same origin
- Prevents base tag hijacking

**`form-action 'self' https://api.legallens.com`**
- Allow form submissions to same origin or API
- Prevents forms from posting to attacker domains

**`upgrade-insecure-requests`** (production only)
- Automatically upgrade HTTP to HTTPS
- Only enabled in production builds

**`block-all-mixed-content`** (production only)
- Block mixed content (HTTP resources on HTTPS pages)
- Only enabled in production builds

---

### 2. X-Content-Type-Options

**Header**: `X-Content-Type-Options: nosniff`

**Purpose**: Prevents MIME type sniffing
- Browser must respect declared `Content-Type`
- Blocks execution of JavaScript served as `text/plain`

**Attack Prevented**: MIME confusion attacks

---

### 3. X-Frame-Options

**Header**: `X-Frame-Options: DENY`

**Purpose**: Prevents clickjacking
- Blocks page from being loaded in `<iframe>`, `<frame>`, `<embed>`, `<object>`
- Protects against UI redressing attacks

**Alternative**: CSP `frame-ancestors 'none'` (more modern)

---

### 4. Referrer-Policy

**Header**: `Referrer-Policy: strict-origin-when-cross-origin`

**Purpose**: Controls `Referer` header sent with requests

**Behavior**:
- Same origin: Send full URL
- Cross-origin (HTTPS → HTTPS): Send origin only
- Cross-origin (HTTPS → HTTP): Send nothing (downgrade protection)

**Privacy**: Prevents leaking sensitive URL parameters to third parties

---

### 5. X-XSS-Protection

**Header**: `X-XSS-Protection: 1; mode=block`

**Purpose**: Legacy XSS protection for older browsers
- Enables browser's built-in XSS filter
- Block page rendering if attack detected

**Note**: Modern browsers rely on CSP instead, but included for compatibility

---

### 6. Permissions-Policy

**Header**: `Permissions-Policy: camera=(), microphone=(), geolocation=(), ...`

**Purpose**: Disables unnecessary browser features

**Disabled Features**:
- `camera=()` — Block camera access
- `microphone=()` — Block microphone access
- `geolocation=()` — Block location tracking
- `payment=()` — Block Payment Request API
- `usb=()` — Block WebUSB API
- `magnetometer=()` — Block sensor access
- `gyroscope=()` — Block sensor access
- `accelerometer=()` — Block sensor access

**Security**: Reduces attack surface by disabling unused features

---

### 7. Strict-Transport-Security (HSTS)

**Header**: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`

**Purpose**: Enforces HTTPS for all connections

**Configuration**:
- `max-age=31536000` — Enforce for 1 year (365 days)
- `includeSubDomains` — Apply to all subdomains
- `preload` — Eligible for browser preload lists

**Requirements**:
- Only sent in production (HTTPS enabled)
- Valid SSL certificate required
- All subdomains must support HTTPS

**Preload List**: Submit to https://hstspreload.org/ after testing

---

## CSP Levels

### Level 1 (Current Implementation)
- Basic directive-based CSP
- Uses `'unsafe-inline'` for scripts and styles
- Protects against most XSS attacks
- Allows inline event handlers (not recommended but functional)

### Level 2 (Recommended Upgrade)
- Nonce-based CSP for inline scripts
- Hash-based CSP for inline styles
- Remove `'unsafe-inline'` and `'unsafe-eval'`
- Stronger XSS protection

**Example with nonces**:
```javascript
// Generate nonce per request
const nonce = crypto.randomUUID();

// CSP header
script-src 'self' 'nonce-${nonce}'

// HTML
<script nonce="${nonce}">
  // Inline script allowed
</script>
```

### Level 3 (Future)
- `'strict-dynamic'` for script loading
- Automatic trust propagation
- Eliminates whitelist maintenance

---

## Testing CSP

### Browser DevTools

1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for CSP violation errors:
   ```
   Refused to load the script 'https://evil.com/script.js' 
   because it violates the following Content Security Policy directive: 
   "script-src 'self'"
   ```

### CSP Report-Only Mode

Test CSP without blocking (for debugging):

```javascript
// Report violations without enforcing
{
  key: 'Content-Security-Policy-Report-Only',
  value: '...'
}
```

### Online Tools

- **CSP Evaluator**: https://csp-evaluator.withgoogle.com/
  - Analyzes CSP for weaknesses
  - Suggests improvements

- **SecurityHeaders.com**: https://securityheaders.com/
  - Scans website for security headers
  - Grades A-F with recommendations

### Manual Testing

```bash
# Test CSP headers
curl -I https://legallens.com | grep -i "content-security-policy"

# Expected output:
# content-security-policy: default-src 'self'; script-src 'self' 'unsafe-inline'; ...
```

---

## CSP Violations

### Common Violations

**1. Inline Event Handlers**
```html
<!-- ❌ Blocked by CSP -->
<button onclick="handleClick()">Click</button>

<!-- ✅ Allowed: Use addEventListener -->
<button id="myButton">Click</button>
<script>
  document.getElementById('myButton').addEventListener('click', handleClick);
</script>
```

**2. Inline Styles**
```html
<!-- ❌ Blocked without 'unsafe-inline' -->
<div style="color: red;">Text</div>

<!-- ✅ Allowed: Use CSS classes -->
<div class="text-red-500">Text</div>
```

**3. eval() and Function()**
```javascript
// ❌ Blocked without 'unsafe-eval'
eval('console.log("blocked")');

// ✅ Use safe alternatives
JSON.parse('{"key": "value"}');
```

**4. External Resources**
```html
<!-- ❌ Blocked if domain not whitelisted -->
<script src="https://cdn.example.com/lib.js"></script>

<!-- ✅ Self-host or whitelist in CSP -->
<script src="/js/lib.js"></script>
```

### Handling Violations

1. **Monitor**: Check browser console for CSP errors
2. **Report**: Set up CSP reporting endpoint (optional)
3. **Adjust**: Modify CSP to allow legitimate resources
4. **Fix**: Remove unsafe patterns from code

---

## CSP Reporting (Optional)

Send violation reports to monitoring endpoint:

```javascript
{
  key: 'Content-Security-Policy',
  value: [
    "default-src 'self'",
    // ... other directives
    "report-uri /api/csp-report",
    "report-to csp-endpoint"
  ].join('; ')
}
```

**Report format**:
```json
{
  "csp-report": {
    "document-uri": "https://legallens.com/",
    "violated-directive": "script-src 'self'",
    "blocked-uri": "https://evil.com/script.js",
    "line-number": 42,
    "column-number": 15
  }
}
```

---

## Browser Compatibility

| Header | Chrome | Firefox | Safari | Edge |
|---|---|---|---|---|
| Content-Security-Policy | ✅ 25+ | ✅ 23+ | ✅ 7+ | ✅ 12+ |
| X-Content-Type-Options | ✅ 64+ | ✅ 50+ | ✅ 11+ | ✅ 12+ |
| X-Frame-Options | ✅ All | ✅ All | ✅ All | ✅ All |
| Referrer-Policy | ✅ 56+ | ✅ 50+ | ✅ 11.1+ | ✅ 79+ |
| Permissions-Policy | ✅ 88+ | ✅ 74+ | ✅ 15.4+ | ✅ 88+ |
| Strict-Transport-Security | ✅ 4+ | ✅ 4+ | ✅ 7+ | ✅ 12+ |

**Legacy Support**: All modern browsers support CSP Level 2+

---

## Maintenance

### Regular Reviews

- **Quarterly**: Review CSP for unnecessary permissions
- **After updates**: Test CSP when adding new features
- **On violations**: Investigate and fix legitimate errors

### Best Practices

1. **Start strict, relax as needed**: Begin with most restrictive policy
2. **Use report-only first**: Test in non-blocking mode
3. **Monitor violations**: Track CSP errors in production
4. **Document exceptions**: Note why certain directives are needed
5. **Regular audits**: Use CSP Evaluator to check for weaknesses

---

## Trade-offs

### Current Implementation

**Pros**:
✅ Prevents most XSS attacks  
✅ Compatible with React/Next.js  
✅ Works with Tailwind CSS  
✅ Easy to maintain  

**Cons**:
⚠️ `'unsafe-inline'` weakens protection  
⚠️ Not Level 2 compliant (nonces/hashes)  
⚠️ Inline event handlers still possible  

### Recommended Upgrade Path

1. **Phase 9** (Current): Level 1 CSP with `'unsafe-inline'`
2. **Phase 10**: Implement nonce-based CSP for scripts
3. **Phase 11**: Hash-based CSP for styles
4. **Phase 12**: `'strict-dynamic'` for dynamic script loading

---

## Additional Resources

- [MDN: Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [OWASP: CSP Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [CSP Evaluator](https://csp-evaluator.withgoogle.com/)
- [SecurityHeaders.com](https://securityheaders.com/)
- [HSTS Preload](https://hstspreload.org/)

---

**Last Updated**: Phase 9 — January 2025  
**Review Schedule**: Quarterly  
**Owner**: Security Team
