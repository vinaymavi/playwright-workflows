# Security Guide

## Overview

This guide covers security best practices for the Playwright Workflows framework, including credential management, session security, input validation, and safe workflow authoring.

## Credential Storage and Management

### Encryption Strategy

All credentials are encrypted using AES-256-GCM at rest:

```
Plain Credential → AES-256-GCM → Encrypted Storage
                   (256-bit key)   (data/credentials/)
```

### Secure Storage

```python
from playwright_workflows.security import CredentialManager

# Initialize credential manager
cred_manager = CredentialManager(
    key_file='data/secrets.key',  # 256-bit encryption key
    storage_path='data/credentials/'
)

# Store credential
cred_manager.store('github_token', 'ghp_xxxxxxxxxxxxx')

# Retrieve credential (automatically decrypted)
token = cred_manager.retrieve('github_token')

# Use in workflow
class GitHubWorkflow(Workflow):
    def __init__(self):
        self.token = cred_manager.retrieve('github_token')
```

### Key Management

**Generate encryption key**:
```bash
python -m playwright_workflows security generate-key

# Output: data/secrets.key (256-bit, base64-encoded)
# Protect this file: chmod 600 data/secrets.key
```

**Protect the key file**:
```bash
# Restrict access to owner only
chmod 600 data/secrets.key

# Back up securely
gpg --symmetric data/secrets.key
# Store backup in secure location
```

**Rotate keys** (re-encrypt all credentials):
```python
cred_manager.rotate_key(new_key_file='data/secrets.key.new')
# All credentials re-encrypted with new key
```

### Environment Variable Credentials

For deployment environments, use environment variables:

```python
import os
from playwright_workflows.security import CredentialManager

# Load from environment
token = os.getenv('GITHUB_TOKEN')
if not token:
    token = cred_manager.retrieve('github_token')

# Recommended: Use credential manager for local, env vars for production
cred_manager = CredentialManager(
    fallback_env_vars={
        'github_token': 'GITHUB_TOKEN',
        'api_key': 'API_KEY',
        'password': 'SERVICE_PASSWORD'
    }
)

# Automatically uses env var if available, falls back to encrypted storage
token = cred_manager.retrieve('github_token')
```

### Credential Masking in Logs

Credentials are automatically masked in logs:

```python
# Sensitive fields: passwords, tokens, keys, api_keys
# These are never logged in plaintext

# Before:
log: f"Login with token: {token}"

# After (in logs):
log: f"Login with token: ****MASKED****"
```

**Configure masking patterns**:
```python
cred_manager.add_mask_pattern(r'Bearer\s+[\w-]+')
cred_manager.add_mask_pattern(r'password=["\']?[\w]+["\']?')
```

## Session and Cookie Security

### Secure Session Storage

```python
from playwright_workflows.security import SessionManager

session_manager = SessionManager(
    storage_path='data/sessions/',
    encryption_enabled=True,
    session_timeout=3600  # 1 hour
)

# Save authenticated session
session_manager.save_session(execution_id, {
    'cookies': cookies,
    'storage': storage_state,
    'user_agent': user_agent,
    'timestamp': datetime.now()
})

# Retrieve session (encrypted)
session_data = session_manager.get_session(execution_id)
if session_data and not session_data.is_expired():
    # Restore authenticated session
    await context.add_cookies(session_data['cookies'])
```

### Session Timeout and Expiration

```python
class AuthenticatedWorkflow(Workflow):
    def __init__(self):
        self.session_manager = SessionManager()
        self.session_timeout = 3600  # 1 hour
    
    async def run(self):
        session = self.session_manager.get_session(self.execution_id)
        
        if session.is_expired():
            # Session expired - require re-authentication
            await self.take_checkpoint({
                'reason': 'session_expired',
                'message': 'Please re-authenticate'
            })
            # Wait for human/AI to provide new credentials
```

### Secure Cookie Handling

```python
# Remove sensitive cookies before saving
async def cleanup_session(self, cookies):
    # Don't store certain cookies
    sensitive_patterns = [
        'admin_session',
        'debug_token',
        'internal_csrf'
    ]
    
    filtered = [
        c for c in cookies
        if not any(p in c['name'] for p in sensitive_patterns)
    ]
    
    return filtered
```

## Input Validation and Sanitization

### Workflow Parameter Validation

```python
from playwright_workflows.validation import validate, Schema
from typing import Optional

class LoginWorkflow(Workflow):
    def __init__(self, username: str, password: str, mfa_code: Optional[str] = None):
        # Validate input parameters
        validate(username, Schema.email_address())
        validate(password, Schema.string().min_length(8).max_length(256))
        validate(mfa_code, Schema.optional(Schema.string().pattern(r'^\d{6}$')))
        
        self.username = username
        self.password = password
        self.mfa_code = mfa_code
```

### Form Input Sanitization

```python
import html
from urllib.parse import quote

class FormWorkflow(Workflow):
    async def fill_form(self, field_name, value):
        # Sanitize text inputs
        if isinstance(value, str):
            # Remove potentially dangerous characters
            value = html.escape(value)
            # Prevent injection
            value = value[:1000]  # Limit length
        
        await self.page.fill(field_name, value)
```

### Selector Validation

```python
from playwright_workflows.validation import validate_selector

class BrowsingWorkflow(Workflow):
    async def click_element(self, selector):
        # Validate selector format (prevent injection)
        validate_selector(selector)
        
        # Safe to use
        await self.page.click(selector)
```

### URL Validation

```python
from urllib.parse import urlparse
from playwright_workflows.validation import validate_url

class NavigationWorkflow(Workflow):
    async def navigate(self, url):
        # Validate URL
        validate_url(url)
        
        # Prevent common attacks
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Invalid scheme: {parsed.scheme}")
        
        await self.page.goto(url)
```

## XSS and Injection Prevention

### Executing Scripts Safely

```python
# ❌ UNSAFE: User input in script
user_input = get_user_input()
result = await page.evaluate(f"() => {{ return '{user_input}'; }}")

# ✅ SAFE: Pass data via function parameter
user_input = get_user_input()
result = await page.evaluate(
    "(userInput) => { return userInput.toUpperCase(); }",
    user_input
)
```

### Content Security Policy

```python
# Check for CSP headers
async def check_csp(page):
    headers = await page.evaluate(
        "() => Object.fromEntries(new Headers(Array.from(fetch('').headers)))"
    )
    csp = headers.get('content-security-policy')
    if csp:
        print(f"CSP enabled: {csp}")
```

### Safe DOM Manipulation

```python
# ❌ UNSAFE: innerHTML with untrusted content
element.innerHTML = user_data

# ✅ SAFE: textContent for text
element.textContent = user_data

# ✅ SAFE: setAttribute with sanitized values
element.setAttribute('data-value', sanitize(user_data))
```

## Network Security

### HTTPS Enforcement

```python
class SecureNavigationWorkflow(Workflow):
    async def navigate_secure(self, url):
        # Ensure HTTPS
        if not url.startswith('https://'):
            raise ValueError("Only HTTPS URLs are allowed")
        
        await self.page.goto(url)
    
    async def verify_certificate(self):
        # Verify SSL certificate
        response = await self.page.goto(self.page.url)
        if not response.ok:
            raise ConnectionError("Invalid SSL certificate or HTTPS issue")
```

### Certificate Pinning (for critical connections)

```python
from playwright_workflows.security import CertificatePin

cert_pin = CertificatePin()
cert_pin.add_pin('api.example.com', 'sha256/AAAA...')
cert_pin.add_pin('auth.example.com', 'sha256/BBBB...')

class SecureAPIWorkflow(Workflow):
    async def call_api(self, url):
        if not cert_pin.verify(url):
            raise SecurityError("Certificate pin verification failed")
        
        # Safe to call
        response = await self.page.goto(url)
```

### Proxy Usage and Monitoring

```python
# ✅ Use trusted proxy
context = await browser.new_context(
    proxy={
        'server': 'http://proxy.internal:8080',
        'username': 'proxyuser',
        'password': 'proxypass'
    }
)

# ❌ AVOID: Untrusted public proxies
# They can intercept traffic and credentials
```

## Execution Isolation

### Execution Sandboxing

Each execution runs in isolation:

```
Browser Context (private)
    ↓
Isolated Cookies/Storage
    ↓
Separate Process (when needed)
    ↓
No Cross-Execution State Sharing
```

```python
# Each execution gets fresh context
context1 = await browser.new_context()  # User A
context2 = await browser.new_context()  # User B

# Completely isolated - no data leakage
# context1 cookies ≠ context2 cookies
```

### File System Isolation

```
data/
├── executions/
│   ├── exec-user-a-001/
│   │   ├── state.json (User A data only)
│   │   └── artifacts/
│   └── exec-user-b-001/
│       ├── state.json (User B data only)
│       └── artifacts/
```

Each execution has isolated directory:
```python
execution_dir = Path(f"data/executions/{execution_id}/")
# Only this execution can read/write here
# File permissions: 700 (user read/write/execute only)
```

## Workflow Authoring Security Best Practices

### 1. Secrets Management

```python
# ❌ NEVER hardcode secrets
API_KEY = 'sk_live_xxxxxxxxxxxxx'

# ✅ ALWAYS use credential manager
from playwright_workflows.security import CredentialManager
cred_manager = CredentialManager()
API_KEY = cred_manager.retrieve('api_key')
```

### 2. Input Validation

```python
# ❌ NEVER trust user input
class MyWorkflow(Workflow):
    async def run(self, query):
        await self.page.goto(f"https://api.example.com/search?q={query}")

# ✅ ALWAYS validate
from playwright_workflows.validation import validate, Schema

class MyWorkflow(Workflow):
    async def run(self, query):
        validate(query, Schema.string().max_length(100))
        # Safe to use
```

### 3. Error Handling

```python
# ❌ DON'T expose sensitive data in error messages
except Exception as e:
    raise ValueError(f"Failed with token: {token}: {e}")

# ✅ DO log safely with masked credentials
except Exception as e:
    logger.error(f"API call failed: {e}")  # token auto-masked
    raise ValueError("API authentication failed")
```

### 4. Dependency Security

```python
# Keep dependencies updated
# pip list --outdated
# pip install --upgrade playwright

# Audit for vulnerabilities
# pip-audit

# Pin versions for reproducibility
# requirements.txt or pyproject.toml with specific versions
```

### 5. Code Review

Before deploying workflows:

- **Credential review**: No hardcoded secrets
- **Input validation**: All user inputs validated
- **Error handling**: No sensitive data in errors
- **Dependency audit**: No vulnerable packages
- **Permission check**: File permissions 600/700

## Security Checklist for Workflows

```markdown
## Workflow Security Checklist

- [ ] All credentials loaded from CredentialManager or env vars
- [ ] All user inputs validated with Schema
- [ ] All URLs are HTTPS (if accessing external sites)
- [ ] Error handling doesn't expose sensitive data
- [ ] Secrets not logged (auto-masked or omitted)
- [ ] Files created with secure permissions (600/700)
- [ ] Sessions properly encrypted and timed-out
- [ ] No use of dangerous functions (eval, exec, etc.)
- [ ] Dependencies updated and vulnerability-scanned
- [ ] Code reviewed by another team member
```

## Security Incident Response

### If Credentials are Exposed

1. **Revoke immediately**:
   - Rotate the credential in the service
   - Generate new token/password

2. **Update storage**:
   ```python
   cred_manager.store('api_key', 'new_key_value')
   # All workflows immediately use new key
   ```

3. **Rotate encryption key**:
   ```bash
   python -m playwright_workflows security rotate-key
   ```

4. **Audit logs**:
   ```python
   logs = execution_manager.get_logs(
       after='2024-01-15T10:00:00Z'
   )
   # Check if exposed credential was used
   ```

### If a Workflow is Compromised

1. **Disable immediately**:
   ```python
   workflow_registry.disable('CompromisedWorkflow')
   ```

2. **Review execution history**:
   ```python
   executions = execution_manager.list_executions(
       workflow_class='CompromisedWorkflow'
   )
   # Check state_files for unauthorized data access
   ```

3. **Inspect code changes**:
   ```bash
   git log -p workflows/compromised.py
   # Identify malicious changes
   ```

4. **Restore from backup**:
   ```bash
   git checkout HEAD~1 workflows/compromised.py
   # Restore to known-good version
   ```

## Compliance and Auditing

### Audit Trail

All actions are logged with audit context:

```python
# Audit log entry
{
    "timestamp": "2024-01-15T10:05:00Z",
    "execution_id": "exec-123",
    "user": "alice@company.com",
    "action": "retrieve_credential",
    "resource": "github_token",
    "result": "success"
}
```

### GDPR Compliance

```python
# Right to be forgotten
execution_manager.delete_execution('exec-123')
# All data, logs, artifacts, credentials removed

# Data portability
export_data = execution_manager.export_execution('exec-123')
# Full execution history in standard format
```

### Access Control

```python
from playwright_workflows.security import AccessControl

access_control = AccessControl()
access_control.grant('alice@company.com', 'read', 'LoginWorkflow')
access_control.grant('bob@company.com', 'execute', '*')

# Enforce access
if not access_control.check(user, action, workflow):
    raise PermissionError(f"Access denied: {user} {action} {workflow}")
```

## Summary

Security in Playwright Workflows is built on:

1. **Encryption**: AES-256-GCM for credentials at rest
2. **Isolation**: Separate browser contexts per execution
3. **Validation**: Input validation and sanitization
4. **Masking**: Automatic credential masking in logs
5. **Audit Trail**: Complete execution audit logging
6. **Best Practices**: Guidelines for workflow authors

Follow these practices to build secure, compliant workflow automation systems.
