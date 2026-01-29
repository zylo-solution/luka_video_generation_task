"""
Persistent job storage using Redis.

This module provides a Redis-backed job storage system to persist job data
across server restarts. Falls back to in-memory storage if Redis is unavailable.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from video_generator import JobInfo, JobState


class JobStorage:
    """Job storage with Redis persistence and in-memory fallback."""

    def __init__(self):
        self.use_redis = False
        self.redis_client = None
        self.memory_storage: Dict[str, JobInfo] = {}
        
        # Try to connect to Redis
        if REDIS_AVAILABLE:
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                print(f"[JobStorage] Connected to Redis at {redis_url}")
            except Exception as e:
                print(f"[JobStorage] Redis unavailable: {e}. Using in-memory storage.")
        else:
            print("[JobStorage] Redis not installed. Using in-memory storage.")

    def set(self, job_id: str, job_info: JobInfo) -> None:
        """Store job information."""
        if self.use_redis:
            try:
                # Serialize JobInfo to JSON
                job_dict = {
                    "id": job_info.id,
                    "status": job_info.status.value,
                    "progress": job_info.progress,
                    "created_at": job_info.created_at.isoformat(),
                    "video_url": job_info.video_url,
                    "error": job_info.error,
                }
                # Store in Redis with 24-hour expiration
                self.redis_client.setex(
                    f"job:{job_id}",
                    86400,  # 24 hours
                    json.dumps(job_dict)
                )
            except Exception as e:
                print(f"[JobStorage] Redis write failed: {e}. Falling back to memory.")
                self.memory_storage[job_id] = job_info
        else:
            self.memory_storage[job_id] = job_info

    def get(self, job_id: str) -> Optional[JobInfo]:
        """Retrieve job information."""
        if self.use_redis:
            try:
                data = self.redis_client.get(f"job:{job_id}")
                if data:
                    job_dict = json.loads(data)
                    return JobInfo(
                        id=job_dict["id"],
                        status=JobState(job_dict["status"]),
                        progress=job_dict["progress"],
                        created_at=datetime.fromisoformat(job_dict["created_at"]),
                        video_url=job_dict.get("video_url"),
                        error=job_dict.get("error"),
                    )
            except Exception as e:
                print(f"[JobStorage] Redis read failed: {e}. Checking memory.")
        
        return self.memory_storage.get(job_id)

    def delete(self, job_id: str) -> None:
        """Delete job information."""
        if self.use_redis:
            try:
                self.redis_client.delete(f"job:{job_id}")
            except Exception:
                pass
        
        if job_id in self.memory_storage:
            del self.memory_storage[job_id]

    def exists(self, job_id: str) -> bool:
        """Check if job exists."""
        if self.use_redis:
            try:
                return bool(self.redis_client.exists(f"job:{job_id}"))
            except Exception:
                pass
        
        return job_id in self.memory_storage
