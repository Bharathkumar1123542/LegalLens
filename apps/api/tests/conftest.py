"""
pytest root conftest — LegalLens API
Sets up sys.path and loads the test environment variables BEFORE any app module
is imported, so that the fail-fast Pydantic Settings validator sees valid values
and doesn't raise at import time.
"""

import os
import sys

# ── 1. sys.path: allow `from app.xxx import ...` without package installation ─
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── 2. Load .env.test BEFORE any app module is imported ──────────────────────
# This sets os.environ values that pydantic-settings reads when Settings() is
# instantiated. Must run before any `from app.core.config import settings`.
_env_test = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.test")
if os.path.exists(_env_test):
    with open(_env_test) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
