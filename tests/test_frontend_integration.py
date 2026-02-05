"""
Integration tests for frontend-backend communication and full-stack functionality.

Tests the entire application stack including:
- Backend API endpoints
- Frontend HTML serving
- CORS configuration
- End-to-end workflow simulation
"""

import pytest
import requests
import time
from typing import Dict


BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3434"


class TestFrontendIntegration:
    """Test suite for frontend-backend integration."""

    def test_frontend_accessible(self):
        """Test that frontend HTML is served correctly."""
        response = requests.get(FRONTEND_URL)
        assert response.status_code == 200
        assert "AI Documentary Video Generator" in response.text
        assert "Generate Video" in response.text
        assert "API_BASE_URL" in response.text

    def test_frontend_has_required_elements(self):
        """Test that frontend contains all required UI elements."""
        response = requests.get(FRONTEND_URL)
        content = response.text
        
        # Check for critical HTML elements
        assert 'id="prompt"' in content
        assert 'id="generateBtn"' in content
        assert 'id="statusSection"' in content
        assert 'id="videoPlayer"' in content
        assert 'id="downloadBtn"' in content
        
        # Check for JavaScript functionality
        assert "generateVideo" in content
        assert "checkStatus" in content
        assert "loadVideo" in content
        assert "fetch" in content

    def test_backend_api_accessible(self):
        """Test that backend API is accessible."""
        response = requests.get(f"{BASE_URL}/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_cors_headers_present(self):
        """Test that CORS headers are properly configured."""
        headers = {
            "Origin": FRONTEND_URL,
            "Access-Control-Request-Method": "POST",
        }
        response = requests.options(f"{BASE_URL}/generate", headers=headers)
        
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "POST" in response.headers.get("access-control-allow-methods", "")

    def test_generate_endpoint_returns_job_id(self):
        """Test that /generate endpoint creates a job and returns job_id."""
        payload = {"prompt": "Integration test video"}
        response = requests.post(
            f"{BASE_URL}/generate",
            json=payload,
            headers={"Origin": FRONTEND_URL}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0

    def test_status_endpoint_returns_job_info(self):
        """Test that /status endpoint returns job information."""
        # First create a job
        payload = {"prompt": "Status test video"}
        gen_response = requests.post(f"{BASE_URL}/generate", json=payload)
        job_id = gen_response.json()["job_id"]
        
        # Check status
        status_response = requests.get(f"{BASE_URL}/status/{job_id}")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data["job_id"] == job_id
        assert "status" in data
        assert "progress" in data
        assert "created_at" in data
        assert isinstance(data["progress"], (int, float))
        assert 0.0 <= data["progress"] <= 1.0

    def test_download_endpoint_accessible(self):
        """Test that /download endpoint is accessible."""
        # Create a job first
        payload = {"prompt": "Download test video"}
        gen_response = requests.post(f"{BASE_URL}/generate", json=payload)
        job_id = gen_response.json()["job_id"]
        
        # Try to download (will not be complete but should return valid response)
        download_response = requests.get(f"{BASE_URL}/download/{job_id}")
        assert download_response.status_code == 200
        
        data = download_response.json()
        assert "job_id" in data
        assert "status" in data

    def test_empty_prompt_rejected(self):
        """Test that empty prompts are rejected."""
        payload = {"prompt": ""}
        response = requests.post(f"{BASE_URL}/generate", json=payload)
        assert response.status_code == 400

    def test_invalid_job_id_returns_404(self):
        """Test that invalid job IDs return 404."""
        response = requests.get(f"{BASE_URL}/status/invalid-job-id-12345")
        assert response.status_code == 404

    def test_multiple_jobs_can_be_created(self):
        """Test that multiple jobs can be created and tracked."""
        job_ids = []
        
        for i in range(3):
            payload = {"prompt": f"Concurrent test video {i}"}
            response = requests.post(f"{BASE_URL}/generate", json=payload)
            assert response.status_code == 200
            job_ids.append(response.json()["job_id"])
        
        # Verify all jobs are unique
        assert len(set(job_ids)) == 3
        
        # Verify all jobs can be queried
        for job_id in job_ids:
            status_response = requests.get(f"{BASE_URL}/status/{job_id}")
            assert status_response.status_code == 200

    def test_job_progress_updates(self):
        """Test that job progress can be tracked over time."""
        payload = {"prompt": "Progress tracking test"}
        gen_response = requests.post(f"{BASE_URL}/generate", json=payload)
        job_id = gen_response.json()["job_id"]
        
        # Check status immediately
        initial_response = requests.get(f"{BASE_URL}/status/{job_id}")
        initial_data = initial_response.json()
        
        # Job should be in one of the valid states
        valid_states = ["pending", "processing", "generating_script", 
                       "generating_video", "adding_captions", "complete", "error"]
        assert initial_data["status"] in valid_states
        
        # Job should have a timestamp
        assert initial_data["created_at"] is not None

    def test_frontend_javascript_api_calls(self):
        """Test that frontend JavaScript correctly constructs API URLs."""
        response = requests.get(FRONTEND_URL)
        content = response.text
        
        # Check that API base URL is set correctly
        assert "const API_BASE_URL = 'http://localhost:8000'" in content
        
        # Check that API endpoints are correctly referenced
        assert "${API_BASE_URL}/generate" in content
        assert "${API_BASE_URL}/status/" in content
        assert "${API_BASE_URL}/download/" in content

    def test_frontend_handles_errors_gracefully(self):
        """Test that frontend has error handling code."""
        response = requests.get(FRONTEND_URL)
        content = response.text
        
        # Check for error handling
        assert "catch" in content or "error" in content.lower()
        assert "errorMessage" in content
        assert "showError" in content

    def test_cors_allows_json_content_type(self):
        """Test that CORS allows application/json content type."""
        headers = {
            "Origin": FRONTEND_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = requests.options(f"{BASE_URL}/generate", headers=headers)
        
        assert response.status_code == 200
        # Should not have CORS errors

    def test_redis_persistence(self):
        """Test that jobs are persisted in Redis."""
        # Create a job
        payload = {"prompt": "Redis persistence test"}
        gen_response = requests.post(f"{BASE_URL}/generate", json=payload)
        job_id = gen_response.json()["job_id"]
        
        # Wait a moment for Redis write
        time.sleep(0.5)
        
        # Retrieve job status
        status_response = requests.get(f"{BASE_URL}/status/{job_id}")
        assert status_response.status_code == 200
        
        # Job should be retrievable (proves it was stored)
        data = status_response.json()
        assert data["job_id"] == job_id


class TestAPIEndpointValidation:
    """Test API endpoint validation and error handling."""

    def test_generate_requires_prompt_field(self):
        """Test that /generate requires 'prompt' field."""
        response = requests.post(f"{BASE_URL}/generate", json={})
        assert response.status_code == 422  # Validation error

    def test_generate_accepts_only_json(self):
        """Test that /generate only accepts JSON content type."""
        response = requests.post(
            f"{BASE_URL}/generate",
            data="prompt=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        # FastAPI should reject non-JSON payloads
        assert response.status_code in [415, 422]

    def test_status_endpoint_validates_job_id_format(self):
        """Test status endpoint with various job ID formats."""
        # Valid UUID format should work or return 404
        response = requests.get(
            f"{BASE_URL}/status/550e8400-e29b-41d4-a716-446655440000"
        )
        assert response.status_code in [200, 404]

    def test_openapi_schema_accessible(self):
        """Test that OpenAPI schema is accessible."""
        response = requests.get(f"{BASE_URL}/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "/generate" in data["paths"]
        assert "/status/{job_id}" in data["paths"]
        assert "/download/{job_id}" in data["paths"]


class TestServicesHealth:
    """Test that all Docker services are healthy and accessible."""

    def test_all_services_reachable(self):
        """Test that all services respond to health checks."""
        services = [
            ("Backend API", f"{BASE_URL}/docs"),
            ("Frontend", FRONTEND_URL),
        ]
        
        for service_name, url in services:
            try:
                response = requests.get(url, timeout=5)
                assert response.status_code == 200, f"{service_name} not reachable"
            except requests.exceptions.RequestException as e:
                pytest.fail(f"{service_name} failed: {e}")

    def test_backend_healthcheck_endpoint(self):
        """Test that backend responds to docs endpoint (used in healthcheck)."""
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
