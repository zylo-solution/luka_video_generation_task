"""
FastAPI application for AI-driven 30‑second documentary video generation.

This service exposes three endpoints:

* **POST /generate** – accepts a user prompt and enqueues a video generation job. It
  returns a unique job identifier which can be polled for status updates.
* **GET /status/{job_id}** – returns the current status and progress of a video
  generation job.
* **GET /download/{job_id}** – once a job is complete, returns a direct link to
  download the finished, captioned video. If the job is still processing, an
  appropriate status message is returned instead.

The implementation delegates all heavy lifting to the ``VideoGenerator`` class
located in ``video_generator.py``. That class encapsulates the entire
pipeline: generating a five‑scene script via the Gemini API, composing an
avatar video with HeyGen, and burning in captions through Submagic. Each step
updates the job state in an in‑memory dictionary so clients can track
progress. Errors are captured and surfaced via the status endpoint.

This file contains only the API layer and minimal orchestration logic. For
details on the integration with external services, consult ``video_generator.py``.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from video_generator import VideoGenerator, JobState, JobInfo
from job_storage import JobStorage

# Load environment variables from .env file
load_dotenv()


app = FastAPI(title="AI Video Generator", version="1.0.0")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent job storage with Redis backend (falls back to in-memory if unavailable)
job_storage = JobStorage()

# Instantiate a single VideoGenerator instance for reuse across requests.
video_generator = VideoGenerator(job_storage=job_storage)


class GenerateRequest(BaseModel):
    """Request payload for ``POST /generate``.

    * ``prompt`` – A natural language description of the desired documentary.
    """

    prompt: str = Field(..., description="The subject or story you want the video to cover.")


class GenerateResponse(BaseModel):
    """Response model containing the ID of the queued job."""

    job_id: str


class StatusResponse(BaseModel):
    """Response model exposing job status and progress."""

    job_id: str
    status: JobState
    progress: float
    created_at: datetime
    error: str | None = None


class DownloadResponse(BaseModel):
    """Response model for the download endpoint."""

    job_id: str
    status: JobState
    video_url: str | None = None
    message: str | None = None


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """Enqueue a new video generation job.

    Accepts a user prompt describing a documentary topic. The actual video
    generation runs asynchronously so that this endpoint returns quickly. The
    returned ``job_id`` can be passed to ``/status/{job_id}`` and
    ``/download/{job_id}`` to monitor progress and retrieve the result.
    """
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    job_id = str(uuid.uuid4())
    # Initialise a job record with pending status. Progress starts at 0.
    job_info = JobInfo(
        id=job_id,
        status=JobState.pending,
        progress=0.0,
        created_at=datetime.utcnow(),
        video_url=None,
        error=None,
    )
    job_storage.set(job_id, job_info)

    # Kick off asynchronous processing. We don't await here so that the request
    # returns immediately; the task will run in the background.
    asyncio.create_task(video_generator.process_prompt(job_id, prompt))

    return GenerateResponse(job_id=job_id)


@app.get("/status/{job_id}", response_model=StatusResponse)
async def status(job_id: str) -> StatusResponse:
    """Return the current status and progress for the specified job."""
    job = job_storage.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return StatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        error=job.error,
    )


@app.get("/download/{job_id}", response_model=DownloadResponse)
async def download(job_id: str) -> DownloadResponse:
    """Return the finished video URL once generation completes.

    If the job is still in progress, this returns a message indicating that the
    download is not yet available. If the job errored, the error message is
    returned instead. Only when the job status is ``complete`` will a valid
    ``video_url`` be included in the response.
    """
    job = job_storage.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobState.complete:
        return DownloadResponse(job_id=job.id, status=job.status, video_url=job.video_url)
    if job.status == JobState.error:
        # Expose the error via the message field
        return DownloadResponse(job_id=job.id, status=job.status, message=job.error)
    # Otherwise job is still running
    return DownloadResponse(
        job_id=job.id,
        status=job.status,
        message="Video not ready yet. Check the status endpoint for progress.",
    )