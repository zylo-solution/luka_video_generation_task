# Testing Guide

This document provides step-by-step instructions for testing the AI Video Generator application.

## Quick Test Commands

### 1. Setup and Start Services

```bash
# Create .env file from example
cp .env.example .env

# Edit .env and add your API keys
# nano .env  # or use your preferred editor

# Build and start all services
docker compose up --build
```

Wait for all services to be healthy (about 10-20 seconds).

### 2. Run Backend Tests (in Docker)

Open a **new terminal** and run:

```bash
# Run all backend tests
docker compose exec video-generator pytest tests/ -v

# Run specific test file
docker compose exec video-generator pytest tests/test_api.py -v

# Run with coverage
docker compose exec video-generator pytest tests/ --cov=. --cov-report=html
```

### 3. Run Frontend Integration Tests (from host)

In your terminal, run:

```bash
# Run all frontend integration tests
pytest tests/test_frontend_integration.py -v

# Run with detailed output
pytest tests/test_frontend_integration.py -v --tb=short
```

### 4. Run Complete Test Suite

```bash
# Terminal 1: Run frontend tests
pytest tests/test_frontend_integration.py -v

# Terminal 2: Run backend tests (in Docker)
docker compose exec video-generator pytest tests/ -v
```

## Expected Results

✅ **Frontend Integration Tests:** 21/21 PASSED  
✅ **Backend API Tests:** 15/15 PASSED  
✅ **Video Generator Tests:** 5/5 PASSED  
✅ **Total:** 41/41 PASSED

## Test Coverage

The test suite validates:
- API endpoints (`/generate`, `/status`, `/download`)
- Job creation and lifecycle management
- Redis persistence
- Error handling and validation
- Request/response schemas
- Multiple concurrent jobs
- OpenAPI documentation
- Frontend HTML serving and UI elements
- Frontend-backend communication via CORS
- Cross-origin request handling
- Job status polling and progress tracking
- Full end-to-end workflow

## Manual Testing via Browser

1. Open **http://localhost:3000** in your browser
2. Enter a prompt (e.g., "A coffee shop owner discovers AI")
3. Click "Generate Video"
4. Watch the progress bar update in real-time
5. Once complete, the video will display and can be downloaded

## Stopping Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v
```
