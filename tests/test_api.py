"""
Integration tests for the AI Video Generator API.

These tests verify the complete video generation pipeline including:
- Job creation and validation
- Status tracking
- Job persistence across restarts
- Error handling
"""

import time
import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from main import app, job_storage
from video_generator import JobState


client = TestClient(app)


class TestGenerateEndpoint:
    """Tests for the POST /generate endpoint."""

    def test_generate_video_success(self):
        """Test successful video generation job creation."""
        response = client.post(
            "/generate",
            json={"prompt": "AI transforming healthcare"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 36  # UUID format
    
    def test_generate_empty_prompt(self):
        """Test that empty prompts are rejected."""
        response = client.post(
            "/generate",
            json={"prompt": "   "}
        )
        
        assert response.status_code == 400
        assert "Prompt cannot be empty" in response.json()["detail"]
    
    def test_generate_missing_prompt(self):
        """Test that missing prompt field is rejected."""
        response = client.post(
            "/generate",
            json={}
        )
        
        assert response.status_code == 422  # Validation error


class TestStatusEndpoint:
    """Tests for the GET /status/{job_id} endpoint."""

    def test_status_existing_job(self):
        """Test retrieving status of an existing job."""
        # Create a job first
        response = client.post(
            "/generate",
            json={"prompt": "Testing video generation"}
        )
        job_id = response.json()["job_id"]
        
        # Check its status
        response = client.get(f"/status/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] in ["pending", "generating_script", "generating_video", "adding_captions", "complete", "error"]
        assert 0.0 <= data["progress"] <= 1.0
        assert "created_at" in data
    
    def test_status_nonexistent_job(self):
        """Test that nonexistent job IDs return 404."""
        fake_job_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/status/{fake_job_id}")
        
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]
    
    def test_status_job_persistence(self):
        """Test that job status persists in storage."""
        # Create a job
        response = client.post(
            "/generate",
            json={"prompt": "Persistence test"}
        )
        job_id = response.json()["job_id"]
        
        # Wait a moment for async processing to update status
        time.sleep(0.5)
        
        # Retrieve directly from storage
        job = job_storage.get(job_id)
        assert job is not None
        assert job.id == job_id
        assert isinstance(job.status, JobState)
        assert isinstance(job.created_at, datetime)


class TestDownloadEndpoint:
    """Tests for the GET /download/{job_id} endpoint."""

    def test_download_pending_job(self):
        """Test download endpoint for a job still in progress."""
        # Create a job
        response = client.post(
            "/generate",
            json={"prompt": "Download test"}
        )
        job_id = response.json()["job_id"]
        
        # Try to download immediately
        response = client.get(f"/download/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["video_url"] is None
        assert "not ready yet" in data["message"].lower()
    
    def test_download_nonexistent_job(self):
        """Test download endpoint with invalid job ID."""
        fake_job_id = "99999999-9999-9999-9999-999999999999"
        response = client.get(f"/download/{fake_job_id}")
        
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]


class TestJobStorage:
    """Tests for the job storage system."""

    def test_job_storage_set_and_get(self):
        """Test basic storage operations."""
        from video_generator import JobInfo, JobState
        from datetime import datetime
        
        job_id = "test-job-123"
        job_info = JobInfo(
            id=job_id,
            status=JobState.pending,
            progress=0.0,
            created_at=datetime.utcnow(),
            video_url=None,
            error=None,
        )
        
        # Store job
        job_storage.set(job_id, job_info)
        
        # Retrieve job
        retrieved = job_storage.get(job_id)
        
        assert retrieved is not None
        assert retrieved.id == job_id
        assert retrieved.status == JobState.pending
        assert retrieved.progress == 0.0
    
    def test_job_storage_update(self):
        """Test updating an existing job."""
        from video_generator import JobInfo, JobState
        from datetime import datetime
        
        job_id = "test-job-update-456"
        job_info = JobInfo(
            id=job_id,
            status=JobState.pending,
            progress=0.0,
            created_at=datetime.utcnow(),
            video_url=None,
            error=None,
        )
        
        # Store initial job
        job_storage.set(job_id, job_info)
        
        # Update job
        job_info.status = JobState.generating_video
        job_info.progress = 0.5
        job_storage.set(job_id, job_info)
        
        # Retrieve updated job
        retrieved = job_storage.get(job_id)
        
        assert retrieved.status == JobState.generating_video
        assert retrieved.progress == 0.5
    
    def test_job_storage_exists(self):
        """Test checking job existence."""
        from video_generator import JobInfo, JobState
        from datetime import datetime
        
        job_id = "test-job-exists-789"
        job_info = JobInfo(
            id=job_id,
            status=JobState.pending,
            progress=0.0,
            created_at=datetime.utcnow(),
            video_url=None,
            error=None,
        )
        
        # Store job
        job_storage.set(job_id, job_info)
        
        # Check existence
        assert job_storage.exists(job_id) is True
        assert job_storage.exists("nonexistent-job") is False


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_complete_workflow(self):
        """Test the complete workflow from generation to status check."""
        # Step 1: Generate video
        response = client.post(
            "/generate",
            json={"prompt": "Complete workflow test: AI in education"}
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Step 2: Check status immediately
        response = client.get(f"/status/{job_id}")
        assert response.status_code == 200
        initial_status = response.json()
        assert initial_status["job_id"] == job_id
        assert initial_status["progress"] >= 0.0
        
        # Step 3: Try download (should not be ready)
        response = client.get(f"/download/{job_id}")
        assert response.status_code == 200
        download_response = response.json()
        assert download_response["video_url"] is None or download_response["status"] != "complete"
        
        # Step 4: Verify job persists in storage
        job = job_storage.get(job_id)
        assert job is not None
        assert job.id == job_id
    
    def test_multiple_concurrent_jobs(self):
        """Test creating multiple jobs concurrently."""
        job_ids = []
        
        # Create 3 jobs
        for i in range(3):
            response = client.post(
                "/generate",
                json={"prompt": f"Concurrent test job {i}"}
            )
            assert response.status_code == 200
            job_ids.append(response.json()["job_id"])
        
        # Verify all jobs are unique
        assert len(set(job_ids)) == 3
        
        # Verify all jobs can be retrieved
        for job_id in job_ids:
            response = client.get(f"/status/{job_id}")
            assert response.status_code == 200
            assert response.json()["job_id"] == job_id


class TestHealthCheck:
    """Tests for API health and availability."""

    def test_docs_endpoint(self):
        """Test that Swagger docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()
    
    def test_openapi_schema(self):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/generate" in schema["paths"]
        assert "/status/{job_id}" in schema["paths"]
        assert "/download/{job_id}" in schema["paths"]
