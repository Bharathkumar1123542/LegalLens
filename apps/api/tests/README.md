# LegalLens API Test Suite

Comprehensive test suite for the LegalLens backend API following SPEC cycle methodology.

## Directory Structure

```
tests/
├── unit/                    # Unit tests (isolated, mocked dependencies)
│   ├── test_config.py
│   ├── test_security.py
│   ├── test_auth_service.py
│   ├── test_ingestion_service.py
│   ├── test_audit_service.py
│   ├── test_text_extraction.py
│   ├── test_ocr.py
│   ├── test_chunking.py
│   ├── test_embedding.py
│   ├── test_llm_orchestration.py
│   ├── test_simplification.py
│   ├── test_clause_extraction.py
│   ├── test_chat.py
│   ├── test_storage.py          # To be created
│   ├── test_comparison.py       # To be created
│   └── test_export.py           # To be created
├── integration/             # Integration tests (real DB, mocked external APIs)
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_auth_endpoints.py
│   ├── test_document_endpoints.py
│   ├── test_ingestion_pipeline.py
│   ├── test_phase3_flow.py
│   ├── test_chat_flow.py
│   ├── test_comparison_flow.py  # To be created
│   ├── test_export_flow.py      # To be created
│   └── test_e2e_journey.py      # To be created
├── eval/                    # LLM evaluation tests
│   ├── golden_dataset/
│   ├── test_llm_quality.py      # To be created
│   └── metrics.py               # To be created
├── performance/             # Performance and load tests
│   ├── test_latency.py          # To be created
│   └── locustfile.py            # To be created
└── README.md               # This file
```

## Running Tests

### Run All Tests
```bash
cd apps/api
pytest -v
```

### Run Specific Test Suite
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_auth_service.py -v

# Specific test
pytest tests/unit/test_auth_service.py::test_register_user_success -v
```

### Run with Coverage
```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# Generate terminal report
pytest --cov=app --cov-report=term-missing

# Generate JSON report for analysis
pytest --cov=app --cov-report=json
```

### Run with Markers
```bash
# Run only fast tests (unit tests)
pytest -m "not slow"

# Run only slow tests (integration/e2e)
pytest -m slow

# Run only tests that don't require external APIs
pytest -m "not external"
```

## Test Coverage Goals

**Target**: 80% line coverage

**Current Coverage by Module** (run `python scripts/analyze-coverage-gaps.py`):
- Phase 0 (Config): 100%
- Phase 1 (Auth): 90%+
- Phase 2 (Ingestion): 85%+
- Phase 3 (LLM): 80%+
- Phase 4 (Chat): 80%+
- Phase 5 (Comparison/Export): 60% (needs improvement)
- Phase 6 (Workers): 70% (needs improvement)

## Test Categories

### Unit Tests
- **Purpose**: Test individual functions/methods in isolation
- **Characteristics**:
  - Fast (<0.1s per test)
  - No external dependencies (mocked)
  - No database (or in-memory SQLite)
  - Deterministic results
- **Mock Strategy**:
  - DB queries: `AsyncMock()` with `MagicMock()` result
  - External APIs: `respx` for HTTP, `patch()` for functions
  - S3: Mock boto3 client
  - LLM: Mock responses with known outputs

### Integration Tests
- **Purpose**: Test component interactions
- **Characteristics**:
  - Moderate speed (0.5-2s per test)
  - Real database (SQLite in-memory or containerized Postgres)
  - Mocked external APIs only
  - Test API endpoints end-to-end
- **Setup**:
  - Fresh DB per test (fixtures in `conftest.py`)
  - Test users created automatically
  - Clean state between tests

### E2E Tests
- **Purpose**: Test complete user journeys
- **Characteristics**:
  - Slow (5-30s per test)
  - All real services (DB, Redis, S3/MinIO)
  - Mocked LLM APIs only (cost/determinism)
  - Full request/response cycle
- **Scenarios**:
  - New user registration → document upload → processing → Q&A
  - Multi-document comparison workflow
  - Export generation and download

### Evaluation Tests
- **Purpose**: Validate LLM output quality
- **Characteristics**:
  - Run against golden dataset
  - Metrics: precision, recall, F1, groundedness
  - Not run in CI (requires real LLM calls)
  - Manual review component
- **Metrics**:
  - Clause extraction: precision ≥0.85, recall ≥0.80
  - Q&A groundedness: ≥95% with valid citations
  - Simplification: 0% fabricated content

### Performance Tests
- **Purpose**: Validate latency and throughput
- **Characteristics**:
  - Run separately from unit/integration
  - Uses locust for load testing
  - Measures p50, p95, p99 latencies
  - Identifies bottlenecks
- **Targets** (from architecture.md):
  - Simplification: p95 ≤15s for ≤20 pages
  - Chat response: p95 ≤5s per turn
  - Throughput: 100 concurrent users

## Writing New Tests

### Unit Test Template
```python
"""
Unit tests for MODULE_NAME
Tests: list key behaviors being tested
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.module_name import function_to_test


@pytest.mark.asyncio
class TestFunctionName:
    """Test function_to_test behavior."""

    async def test_success_case(self):
        """Test successful execution."""
        # Arrange
        mock_dependency = AsyncMock()
        mock_dependency.method.return_value = expected_value
        
        # Act
        result = await function_to_test(mock_dependency, input_data)
        
        # Assert
        assert result == expected_result
        mock_dependency.method.assert_called_once_with(input_data)
    
    async def test_error_case(self):
        """Test error handling."""
        # Arrange
        mock_dependency = AsyncMock()
        mock_dependency.method.side_effect = ValueError("Error message")
        
        # Act & Assert
        with pytest.raises(ValueError, match="Error message"):
            await function_to_test(mock_dependency, input_data)
```

### Integration Test Template
```python
"""
Integration tests for MODULE endpoints
Tests: API endpoint behavior with real DB
"""

import pytest
from httpx import AsyncClient

from app.main import app
from tests.integration.conftest import test_user, auth_headers


@pytest.mark.asyncio
async def test_endpoint_success(test_db, test_user, auth_headers):
    """Test successful endpoint call."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Act
        response = await client.post(
            "/api/v1/endpoint",
            json={"key": "value"},
            headers=auth_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "expected_value"
```

## Mock Patterns

### Async DB Mock
```python
# Correct pattern for async SQLAlchemy queries
mock_result = MagicMock()
mock_result.scalars.return_value.all.return_value = [item1, item2]

async def mock_execute(*args, **kwargs):
    return mock_result

db.execute = mock_execute
```

### LLM Response Mock
```python
from app.services.llm_orchestration import GroundedResponse, Citation

mock_response = GroundedResponse(
    task="simplify",
    content="Simplified text with [chunk:uuid] citation.",
    citations=[
        Citation(
            chunk_id=chunk_id,
            page_number=1,
            excerpt="source text"
        )
    ],
    model_used="claude-sonnet-4-20250514",
)

with patch("app.services.module.generate_grounded_response") as mock_gen:
    mock_gen.return_value = mock_response
    # Call function that uses LLM
```

### S3 Mock
```python
with patch("app.services.storage._s3_client") as mock_s3:
    mock_s3.return_value.put_object.return_value = {"ETag": "abc123"}
    mock_s3.return_value.generate_presigned_url.return_value = "https://..."
    # Call function that uses S3
```

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every push to main
- Nightly (full suite including slow tests)

**CI Configuration**: `.github/workflows/ci.yml`

**Coverage Gate**: PRs must maintain ≥80% coverage or improve coverage

## Troubleshooting

### Tests Fail Due to Missing Dependencies
```bash
pip install -r requirements.txt
```

### Database Errors
```bash
# Ensure migrations are up to date
alembic upgrade head

# Reset test database
rm -f test.db
```

### Async Mock Errors
- Use `AsyncMock()` for async functions
- Use `MagicMock()` for sync return values
- Follow the async DB mock pattern above

### Import Errors
- Check `conftest.py` has correct `sys.path` setup
- Ensure `__init__.py` files exist in all package directories

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [respx documentation](https://lundberg.github.io/respx/) (HTTP mocking)
- [Architecture document](.context/architecture.md)
- [Code standards](.context/code-standards.md)

## Questions?

See `.context/progress-tracker.md` for current test status and coverage metrics.
