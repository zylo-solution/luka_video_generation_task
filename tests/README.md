# Test Suite Documentation

## Overview

This test suite validates the AI Video Generator API's functionality, including:
- API endpoint behavior
- Job creation and lifecycle management
- Status tracking and persistence
- Error handling
- Storage layer (Redis/in-memory)

## Test Structure

```
tests/
├── __init__.py           # Package initialization
├── test_api.py           # API endpoint integration tests
├── test_video_generator.py  # VideoGenerator unit tests
└── README.md             # This file
```

## Running Tests

### With Docker (Recommended)

```bash
# Run all tests inside Docker container
docker compose exec video-generator pytest tests/ -v

# Run specific test file
docker compose exec video-generator pytest tests/test_api.py -v

# Run with coverage report
docker compose exec video-generator pytest tests/ --cov=. --cov-report=html
```

### Without Docker (Local)

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run specific test class
pytest tests/test_api.py::TestGenerateEndpoint -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

## Test Categories

### 1. API Integration Tests (`test_api.py`)

**TestGenerateEndpoint**
- `test_generate_video_success`: Validates successful job creation
- `test_generate_empty_prompt`: Ensures empty prompts are rejected
- `test_generate_missing_prompt`: Validates request schema

**TestStatusEndpoint**
- `test_status_existing_job`: Retrieves status of valid jobs
- `test_status_nonexistent_job`: Returns 404 for invalid job IDs
- `test_status_job_persistence`: Verifies jobs persist in storage

**TestDownloadEndpoint**
- `test_download_pending_job`: Handles in-progress jobs correctly
- `test_download_nonexistent_job`: Returns 404 for invalid job IDs

**TestJobStorage**
- `test_job_storage_set_and_get`: Basic storage operations
- `test_job_storage_update`: Job updates persist correctly
- `test_job_storage_exists`: Job existence checks work

**TestEndToEnd**
- `test_complete_workflow`: Full generation → status → download flow
- `test_multiple_concurrent_jobs`: Multiple jobs can be created simultaneously

**TestHealthCheck**
- `test_docs_endpoint`: Swagger UI is accessible
- `test_openapi_schema`: OpenAPI schema is valid

### 2. Unit Tests (`test_video_generator.py`)

**TestVideoGenerator**
- `test_initialization`: VideoGenerator initializes with correct config
- `test_fallback_script`: Fallback script generation works

**TestJobLifecycle**
- `test_update_job`: Job updates work correctly
- `test_progress_clamping`: Progress values are clamped to [0.0, 1.0]

**TestJobStates**
- `test_all_states_valid`: All JobState enum values are valid

## Test Coverage

Current test coverage includes:
- ✅ All API endpoints (`/generate`, `/status`, `/download`)
- ✅ Job storage layer (Redis + in-memory fallback)
- ✅ Job state management and transitions
- ✅ Error handling and validation
- ✅ Request/response schemas
- ✅ OpenAPI documentation

## Continuous Integration

To run tests in CI/CD pipelines:

```bash
# GitHub Actions, GitLab CI, etc.
docker compose up -d
docker compose exec -T video-generator pytest tests/ -v --junitxml=test-results.xml
docker compose down
```

## Writing New Tests

Follow these patterns when adding tests:

```python
class TestNewFeature:
    """Tests for new feature."""

    def test_feature_success_case(self):
        """Test successful operation."""
        response = client.post("/endpoint", json={...})
        assert response.status_code == 200
        assert "expected_key" in response.json()
    
    def test_feature_error_case(self):
        """Test error handling."""
        response = client.post("/endpoint", json={...})
        assert response.status_code == 400
        assert "error message" in response.json()["detail"]
```

## Common Issues

### Redis Connection Errors
If tests fail with Redis connection errors:
```bash
# Ensure Redis is running
docker compose ps redis

# Restart Redis if needed
docker compose restart redis
```

### Import Errors
If you see import errors:
```bash
# Ensure you're running from project root
cd /home/umar/Desktop/video_generation_agent

# Install test dependencies
pip install pytest pytest-asyncio
```

### Async Test Warnings
Add `pytest-asyncio` to handle async tests:
```bash
pip install pytest-asyncio
```

## Test Maintenance

- Keep tests isolated (no shared state between tests)
- Use fixtures for common setup
- Mock external API calls in unit tests
- Use descriptive test names
- Add docstrings explaining what each test validates
