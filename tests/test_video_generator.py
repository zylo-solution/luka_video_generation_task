"""
Unit tests for the VideoGenerator class.

Tests individual components of the video generation pipeline.
"""

import pytest
from datetime import datetime

from video_generator import VideoGenerator, JobInfo, JobState
from job_storage import JobStorage


@pytest.fixture
def job_storage():
    """Provide a fresh job storage instance for each test."""
    return JobStorage()


@pytest.fixture
def video_generator(job_storage):
    """Provide a VideoGenerator instance with test job storage."""
    return VideoGenerator(job_storage=job_storage)


class TestVideoGenerator:
    """Tests for VideoGenerator class initialization."""

    def test_initialization(self, video_generator):
        """Test VideoGenerator initializes correctly."""
        assert video_generator is not None
        assert video_generator.job_storage is not None
    
    def test_fallback_script(self, video_generator):
        """Test fallback script generation."""
        prompt = "Test prompt for fallback"
        scenes = video_generator._fallback_script(prompt)
        
        assert len(scenes) == 5
        for scene in scenes:
            assert "visual_description" in scene or "visual" in scene
            assert "dialogue" in scene
            # Word count should be reasonable (not strict 18 for fallback)


class TestJobLifecycle:
    """Tests for job state management."""

    @pytest.mark.asyncio
    async def test_update_job(self, video_generator, job_storage):
        """Test job update functionality."""
        # Create a test job
        job_id = "test-job-lifecycle"
        job_info = JobInfo(
            id=job_id,
            status=JobState.pending,
            progress=0.0,
            created_at=datetime.utcnow(),
            video_url=None,
            error=None,
        )
        job_storage.set(job_id, job_info)
        
        # Update job status
        await video_generator._update_job(job_id, JobState.generating_script, 0.25)
        
        # Verify update
        updated_job = job_storage.get(job_id)
        assert updated_job.status == JobState.generating_script
        assert updated_job.progress == 0.25
    
    @pytest.mark.asyncio
    async def test_progress_clamping(self, video_generator, job_storage):
        """Test that progress is clamped to [0.0, 1.0]."""
        job_id = "test-job-clamp"
        job_info = JobInfo(
            id=job_id,
            status=JobState.pending,
            progress=0.0,
            created_at=datetime.utcnow(),
            video_url=None,
            error=None,
        )
        job_storage.set(job_id, job_info)
        
        # Try to set progress > 1.0
        await video_generator._update_job(job_id, JobState.complete, 1.5)
        job = job_storage.get(job_id)
        assert job.progress == 1.0
        
        # Try to set progress < 0.0
        await video_generator._update_job(job_id, JobState.pending, -0.5)
        job = job_storage.get(job_id)
        assert job.progress == 0.0


class TestJobStates:
    """Tests for job state transitions."""

    def test_all_states_valid(self):
        """Test that all JobState values are valid."""
        valid_states = [
            JobState.pending,
            JobState.generating_script,
            JobState.generating_video,
            JobState.adding_captions,
            JobState.complete,
            JobState.error,
        ]
        
        for state in valid_states:
            assert isinstance(state, JobState)
            assert state.value in [
                "pending",
                "generating_script",
                "generating_video",
                "adding_captions",
                "complete",
                "error",
            ]
