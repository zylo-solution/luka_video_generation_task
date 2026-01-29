"""
Core pipeline logic for AI documentary video generation.

This module defines the ``VideoGenerator`` class which orchestrates the
multi‑stage workflow necessary to transform a user prompt into a finished
30‑second video. The pipeline consists of:

1. **Script generation** – uses the Google Gemini API to produce a
   structured five‑scene narrative. Each scene contains a visual description
   and exactly eighteen words of dialogue to approximate a 6‑second
   duration when spoken at normal speed. The method gracefully handles JSON
   parsing errors and falls back to a simple deterministic script when
   Gemini fails to respond or returns malformed output.
2. **Avatar & voice selection** – queries the HeyGen API for available
   avatars and voices. It picks an English voice and a default avatar if
   possible, otherwise it uses hard‑coded fallback IDs. Caching prevents
   repeated API lookups on subsequent requests.
3. **Video generation** – submits the structured scenes to HeyGen’s
   ``/v2/video/generate`` endpoint. Each scene is represented as a
   ``video_inputs`` object with avatar, dialogue and speaking speed
   automatically calculated from the word count. The method polls the
   ``/v1/video_status.get`` endpoint until completion and returns the
   resulting video URL and duration.
4. **Caption burn‑in** – invokes Submagic to transcribe the video and apply
   stylistic captions. It creates a project, triggers export, and polls
   until a download URL becomes available.

Job state and progress are persisted in the shared ``job_registry`` dict
passed to the constructor. The ``process_prompt`` coroutine ties all the
stages together, updating job status as it proceeds. Exceptions are
captured so that the job record reflects any error condition.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import httpx


class JobState(str, Enum):
    """Enumeration of possible job states."""

    pending = "pending"
    generating_script = "generating_script"
    generating_video = "generating_video"
    adding_captions = "adding_captions"
    complete = "complete"
    error = "error"


@dataclass
class JobInfo:
    """Represents the state of a video generation job."""

    id: str
    status: JobState
    progress: float
    created_at: datetime
    video_url: Optional[str]
    error: Optional[str]


class VideoGenerator:
    """Encapsulates all logic for generating a captioned documentary video."""

    def __init__(self, job_storage) -> None:
        self.job_storage = job_storage
        # API keys are loaded from environment variables. See `.env.example` for
        # required variables. Providing defaults makes it easier to test when
        # environment variables are missing but will result in failures if not
        # overridden by the user.
        self.heygen_api_key: str | None = os.getenv("HEYGEN_API_KEY")
        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
        self.submagic_api_key: str | None = os.getenv("SUBMAGIC_API_KEY")
        # Caches to avoid repeated calls to list voices/avatars
        self._avatar_cache: Optional[str] = None
        self._voice_cache: Optional[str] = None

    async def process_prompt(self, job_id: str, prompt: str) -> None:
        """Asynchronously process a prompt through the entire pipeline.

        This method updates job status and progress as it advances through
        script generation, video generation and caption application. If any
        step raises an exception, the job is marked as errored and the
        exception message is stored.
        """
        job = self.job_storage.get(job_id)
        try:
            # Step 1: Script generation
            await self._update_job(job_id, JobState.generating_script, 0.05)
            scenes = await self.generate_script(prompt)

            # Step 2: Avatar/voice selection
            avatar_id, voice_id = await self.choose_avatar_voice()

            # Step 3: Video assembly via HeyGen
            await self._update_job(job_id, JobState.generating_video, 0.2)
            video_url, duration = await self.generate_video(scenes, avatar_id, voice_id, job_id)

            # Step 4: Caption burn‑in via Submagic
            await self._update_job(job_id, JobState.adding_captions, 0.75)
            captioned_url = await self.add_captions(video_url, job_id)

            # Finalise job
            job.video_url = captioned_url or video_url
            self.job_storage.set(job_id, job)  # Persist video URL
            await self._update_job(job_id, JobState.complete, 1.0)
        except Exception as exc:
            # Capture any exception and mark the job as errored
            job.error = str(exc)
            self.job_storage.set(job_id, job)  # Persist error
            await self._update_job(job_id, JobState.error, job.progress)

    async def generate_script(self, prompt: str) -> List[Dict[str, str]]:
        """Generate a five‑scene script using the Gemini API.

        The resulting list contains dictionaries with ``scene_number``,
        ``visual_description`` and ``dialogue`` keys. The dialogue fields are
        constrained to exactly 18 words to approximate six seconds of speech
        when spoken at normal pace (3 words per second). If the API
        response is malformed or the request fails, a deterministic fallback
        script is returned instead.
        """
        print(f"[SCRIPT GENERATION] Starting for prompt: {prompt[:100]}...")
        # Build the instruction for Gemini. The model is asked to return
        # strictly formatted JSON. Using present tense and cinematic language
        # makes the scenes more engaging.
        system_prompt = (
            "You are an expert documentary scriptwriter creating professional 30-second video narrations. "
            "Your task is to write a compelling narrative that sounds like a real person speaking naturally.\n\n"
            "CRITICAL RULES:\n"
            "1. Return ONLY valid JSON - no markdown, no code fences, no extra text\n"
            "2. All 5 scenes MUST be directly connected and relate to the user's specific topic\n"
            "3. Each scene builds upon the previous one, telling ONE cohesive story about the topic\n"
            "2. STRICT NO WORD REPETITION RULE: Each word can only appear ONCE in the entire script\n"
            "3. Even common words like 'AI', 'the', 'and', 'is', 'are' should not repeat if possible\n"
            "4. Use synonyms religiously - 'artificial intelligence' → 'machine learning' → 'computational systems' → 'automated technology' → 'digital intelligence'\n"
            "5. Rephrase to avoid repetition - 'bookings increased' → 'reservations doubled' → 'appointments surged' → 'scheduling expanded' → 'orders multiplied'\n"
            "6. Use rich, varied vocabulary - treat every word as precious and unique\n"
            "7. NEVER start sentences with 'This is', 'This was', 'Here we see', or similar phrases\n"
            "8. Write as if you're a professional narrator speaking to an audience\n"
            "9. Each scene dialogue must be EXACTLY 18 words - count carefully\n"
            "10. Make dialogue flow naturally from one scene to the next with unique vocabulary\n"
            "11. Use contractions (we're, it's, they've) when needed but don't repeat them\n"
            "12. Vary sentence structure and word choice dramatically between scenes\n"
            "13. Stay focused on the user's topic - every scene must advance the story about that specific subject\n\n"
            "CONNECTIVITY REQUIREMENTS:\n"
            "- All 5 scenes tell a complete, connected story about the EXACT topic provided\n"
            "- Each scene transitions smoothly to the next while staying on topic\n"
            "- The narrative arc must be coherent and focused on the user's subject\n"
            "- Don't drift to generic statements - keep it specific to the topic\n\n"
            "VOCABULARY STRATEGY:\n"
            "- Scene 1: Use certain vocabulary about the topic\n"
            "- Scene 2: Switch to completely different words and synonyms, still about the topic\n"
            "- Scene 3: Introduce new terms about the topic, avoid previous vocabulary\n"
            "- Scene 4: Fresh perspective on the topic with unique word choices\n"
            "- Scene 5: Conclude the topic story with entirely new language, no repeats\n\n"
            "JSON Format Required:\n"
            "{\n"
            "  \"scenes\": [\n"
            "    {\n"
            "      \"scene_number\": 1,\n"
            "      \"visual_description\": \"descriptive text in present tense\",\n"
            "      \"dialogue\": \"exactly 18 words of natural narration\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        user_prompt = (
            f"Write a professional 30-second documentary narration about: {prompt}\n\n"
            "ALL 5 SCENES must be directly about this specific topic and tell ONE connected story.\n\n"
            "Create exactly 5 scenes with this narrative structure:\n"
            f"Scene 1 (HOOK): Grab attention about '{prompt}' with an intriguing fact. Use unique, powerful vocabulary.\n"
            f"Scene 2 (CONTEXT): Provide essential background ABOUT '{prompt}'. Use DIFFERENT words - synonyms only.\n"
            f"Scene 3 (CORE CONTENT): Deliver the main insight ABOUT '{prompt}'. AVOID previous words, use fresh vocabulary.\n"
            f"Scene 4 (IMPACT): Show the significance OF '{prompt}'. NEW words only - no repetition from any scene.\n"
            f"Scene 5 (CONCLUSION): End with a memorable takeaway ABOUT '{prompt}'. UNIQUE vocabulary not used anywhere else.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            f"- Every scene must clearly relate to the specific topic: {prompt}\n"
            f"- The 5 scenes together tell ONE complete, connected story about: {prompt}\n"
            "- Check that NO single word appears twice across all 5 scenes\n"
            "- Use synonyms extensively to maintain variety while staying on topic\n\n"
            "EXAMPLE - Notice connection to topic AND no word repeats:\n"
            "Topic: 'AI in healthcare'\n"
            "Scene 1: 'Imagine doctors spotting cancer months earlier than ever before using artificial intelligence now.'\n"
            "Scene 2: 'Revolutionary technology analyzes medical scans, helping physicians identify problems faster with unprecedented accuracy today.'\n"
            "Scene 3: 'Machine learning algorithms process patient data, revealing patterns human experts might overlook during diagnosis procedures.'\n"
            "Scene 4: 'Lives saved, treatments optimized - computational systems transform modern medicine, benefiting millions worldwide through better outcomes.'\n"
            "Scene 5: 'Healthcare's future merges human expertise with digital innovation, creating possibilities we're only beginning to realize.'\n"
            "(Notice: ALL scenes about AI in healthcare, each advances the story, ZERO repeated words)\n\n"
            f"Now create your narration about: {prompt}\n\n"
            "STORYTELLING REQUIREMENTS:\n"
            "- Tell it like a story with a beginning, middle, and end\n"
            "- Use emotional language that conveys excitement, concern, hope, or impact\n"
            "- Build tension and release it in your narrative arc\n"
            "- Make the audience FEEL something about the topic\n\n"
            "Write naturally. Sound human. Show emotion. Engage the audience. Stay on topic. ZERO word repetition. Maximum variety."
        )

        if not self.gemini_api_key:
            # Without an API key we cannot call Gemini; generate a fallback script
            return self._fallback_script(prompt)

        # Use the correct Gemini model name (gemini-pro is deprecated)
        url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"
        params = {"key": self.gemini_api_key}
        # Combine system and user prompts into a single message
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        payload = {
            "contents": [{
                "parts": [{"text": combined_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, params=params, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            print(f"[ERROR] Gemini API failed: {e}")
            print(f"[FALLBACK] Using generic script for: {prompt[:50]}...")
            return self._fallback_script(prompt)

        # Extract the text portion of the response
        try:
            candidates = data.get("candidates") or []
            # Gemini responses include candidates; take the first
            if not candidates:
                raise ValueError("No candidates returned")
            text = candidates[0]["content"]["parts"][0]["text"]
            print(f"[GEMINI RESPONSE] Received {len(text)} characters")
        except Exception as e:
            print(f"[ERROR] Failed to extract Gemini response: {e}")
            return self._fallback_script(prompt)

        # Clean up extraneous code fences or markup
        # Gemini sometimes wraps JSON in triple backticks; strip them
        text = text.strip()
        text = re.sub(r"^```json\s*|```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
        text = re.sub(r"^```\s*|```$", "", text, flags=re.MULTILINE).strip()
        
        # Attempt to parse JSON
        try:
            obj = json.loads(text)
            scenes = obj.get("scenes")
            if not isinstance(scenes, list) or len(scenes) != 5:
                print(f"[ERROR] Invalid scenes structure: expected 5 scenes, got {len(scenes) if isinstance(scenes, list) else 'non-list'}")
                raise ValueError("Invalid scenes structure")
            print(f"[SUCCESS] Gemini generated {len(scenes)} scenes successfully")
            # Validate each scene and enforce 18 words in dialogue
            validated = []
            for idx, sc in enumerate(scenes, start=1):
                scene_num = sc.get("scene_number", idx)
                vis = sc.get("visual_description", f"Scene {idx}")
                dialog = sc.get("dialogue", "").strip()
                # Normalise whitespace
                words = dialog.split()
                if len(words) < 18:
                    # Pad with filler words if too short
                    words += ["..."] * (18 - len(words))
                elif len(words) > 18:
                    words = words[:18]
                validated.append(
                    {
                        "scene_number": scene_num,
                        "visual_description": vis,
                        "dialogue": " ".join(words),
                    }
                )
            
            # Log the generated dialogues for verification
            print(f"[VALIDATED SCENES] Generated dialogues:")
            for i, sc in enumerate(validated, 1):
                print(f"  Scene {i}: {sc['dialogue'][:60]}...")
            
            return validated
        except Exception as e:
            print(f"[ERROR] JSON parsing failed: {e}")
            print(f"[ERROR] Response text: {text[:200]}...")
            return self._fallback_script(prompt)

    async def choose_avatar_voice(self) -> Tuple[str, str]:
        """Retrieve or return default avatar and voice identifiers.

        HeyGen exposes ``/v2/avatars`` and ``/v2/voices`` endpoints for
        listing available assets. We attempt to pick a voice with English
        support and the first available avatar. If retrieval fails, we fall
        back to documented example IDs.
        """
        # Return cached values if available
        if self._avatar_cache and self._voice_cache:
            return self._avatar_cache, self._voice_cache
        
        avatar_id = "Angela-inTshirt-20220820"  # fallback value from docs
        # ALWAYS use ElevenLabs "Connie - Professional" - most human-like voice
        voice_id = "d774d69075f24d1fb52a0dad145ba809"  # Connie Professional (ElevenLabs) - FIXED
        
        print(f"[VOICE] Using ElevenLabs Connie Professional: {voice_id}")
        
        if not self.heygen_api_key:
            self._avatar_cache, self._voice_cache = avatar_id, voice_id
            return avatar_id, voice_id

        async with httpx.AsyncClient(timeout=30) as client:
            headers = {"X-Api-Key": self.heygen_api_key, "Accept": "application/json"}
            try:
                # Fetch avatars only (voice is fixed to ElevenLabs)
                res_avatars = await client.get("https://api.heygen.com/v2/avatars", headers=headers)
                res_avatars.raise_for_status()
                avatars_data = res_avatars.json().get("data", {}).get("avatars", [])
                if avatars_data:
                    # Pick a random avatar to introduce variety
                    avatar_id = random.choice(avatars_data).get("avatar_id", avatar_id)
                    print(f"[AVATAR SELECTED] {avatar_id}")
            except Exception as e:
                # On any failure, use fallback IDs
                print(f"[WARNING] Avatar fetch failed: {e}, using fallback")
                pass
        
        # Cache the selections - voice is ALWAYS ElevenLabs Connie
        self._avatar_cache, self._voice_cache = avatar_id, voice_id
        return avatar_id, voice_id

    async def generate_video(self, scenes: List[Dict[str, str]], avatar_id: str, voice_id: str, job_id: str) -> Tuple[str, float]:
        """Submit a video generation request to HeyGen and wait for completion.

        Builds a ``video_inputs`` array from the provided scenes. Speaking
        speed is calculated dynamically based on word count to approximate a
        fixed 6‑second duration per scene (18 words / 3 words per second).
        Polls the status endpoint until the video is ready. Returns the
        video URL and duration in seconds.
        """
        if not self.heygen_api_key:
            raise RuntimeError("HEYGEN_API_KEY is missing")
        
        print(f"[VIDEO GENERATION] Starting with {len(scenes)} scenes")
        for i, sc in enumerate(scenes, 1):
            print(f"[SCENE {i}] Dialogue: {sc['dialogue'][:50]}...")
        
        # Build payload for video generation
        video_inputs = []
        for sc in scenes:
            dialog = sc["dialogue"].strip()
            words = dialog.split()
            # Compute expected duration at 3 wps
            expected_duration = max(len(words), 1) / 3.0
            # Desired duration per scene is 6 seconds
            desired = 6.0
            speed = expected_duration / desired
            # Cap speed within reasonable bounds
            speed = max(0.6, min(speed, 1.5))
            # Determine emotion based on scene position for natural storytelling
            emotions = ["Excited", "Friendly", "Serious", "Friendly", "Friendly"]
            emotion = emotions[min(len(video_inputs), 4)]  # Map to scene number
            
            video_inputs.append(
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": dialog,
                        "voice_id": voice_id,
                        "speed": round(speed, 2),
                        "emotion": emotion,  # Dynamic emotion per scene
                    },
                    "background": {
                        "type": "color",
                        # Use a dark background for cinematic effect
                        "value": "#000000",
                    },
                }
            )

        payload = {
            "video_inputs": video_inputs,
            # Use 720p resolution - most compatible across all paid plans
            # Pro plan supports up to 1080p, but some API keys may have restrictions
            "dimension": {"width": 1280, "height": 720},
        }
        
        print(f"[VIDEO GENERATION] Payload contains {len(payload['video_inputs'])} video inputs")
        print(f"[VIDEO GENERATION] Full payload structure:")
        for i, vi in enumerate(payload['video_inputs'], 1):
            print(f"  Scene {i}: '{vi['voice']['input_text']}'")
        
        headers = {
            "X-Api-Key": self.heygen_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Use a much longer timeout for the HTTP client to avoid connection timeouts
        # The polling logic will handle the overall timeout
        # Add retry logic for network issues
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=60.0)) as client:
            # Submit generation request
            try:
                res = await client.post(
                    "https://api.heygen.com/v2/video/generate", headers=headers, json=payload
                )
                res.raise_for_status()
                resp_data = res.json().get("data", {})
                video_id = resp_data.get("video_id")
                if not video_id:
                    raise RuntimeError("Failed to obtain video_id from HeyGen response")
            except Exception as e:
                raise RuntimeError(f"HeyGen video generation request failed: {e}")

            # Poll status until completed or failed
            status_url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
            total_checks = 240  # allow up to 20 minutes (240 * 5s)
            for i in range(total_checks):
                try:
                    status_res = await client.get(status_url, headers=headers)
                    status_res.raise_for_status()
                    status_data = status_res.json().get("data", {})
                    status = status_data.get("status")
                    # Update progress proportional to polling loop (30–70% range)
                    progress_fraction = 0.2 + (i / total_checks) * 0.5
                    await self._update_job(job_id, JobState.generating_video, progress_fraction)
                    
                    if status == "completed":
                        video_url = status_data.get("video_url")
                        duration = status_data.get("duration") or 30.0
                        if not video_url:
                            raise RuntimeError("Video completed but no URL returned")
                        return video_url, float(duration)
                    elif status == "failed":
                        error_info = status_data.get("error", {}).get("message", "Unknown error")
                        raise RuntimeError(f"HeyGen video generation failed: {error_info}")
                    # Continue polling for: pending, waiting, processing statuses
                    elif status in ["pending", "waiting", "processing"]:
                        await asyncio.sleep(5)
                    else:
                        # Unknown status - log it but continue
                        print(f"Unknown status from HeyGen: {status}, continuing to poll...")
                        await asyncio.sleep(5)
                except httpx.HTTPStatusError as http_err:
                    # HTTP error - might be rate limiting or temporary issue
                    print(f"HTTP error polling status (attempt {i+1}/{total_checks}): {http_err}")
                    await asyncio.sleep(10)  # Wait longer on HTTP errors
                except (httpx.ConnectError, httpx.TimeoutException) as net_err:
                    # Network error - retry with longer wait
                    print(f"Network error (attempt {i+1}/{total_checks}): {net_err}")
                    await asyncio.sleep(15)  # Wait even longer for network issues
                except Exception as poll_exc:
                    # On other polling errors, log and retry
                    print(f"Error polling status (attempt {i+1}/{total_checks}): {poll_exc}")
                    await asyncio.sleep(5)
            # If we exit loop, video not ready
            raise RuntimeError(f"HeyGen video generation timed out after {total_checks * 5 / 60} minutes")

    async def add_captions(self, video_url: str, job_id: str) -> Optional[str]:
        """Use Submagic to transcribe and burn captions into the video.

        Creates a project, triggers an export, and polls for completion. If
        Submagic is unavailable or fails, the original video URL is
        returned and the job still completes. Returning ``None`` signals
        that no captioned URL is available.
        """
        if not self.submagic_api_key:
            # If no key is provided, skip captioning
            return None
        headers = {
            "x-api-key": self.submagic_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            # Create project
            create_payload = {
                "title": f"Video job {job_id}",
                "language": "en",
                "videoUrl": video_url,
                # Use a simple caption template; Sara is the default template in docs
                "templateName": "Sara",
            }
            try:
                create_res = await client.post(
                    "https://api.submagic.co/v1/projects", headers=headers, json=create_payload
                )
                create_res.raise_for_status()
                project_id = create_res.json().get("id") or create_res.json().get("projectId")
                if not project_id:
                    raise RuntimeError("No project id returned from Submagic")
            except Exception as e:
                # If creation fails, return None but don't raise to avoid
                # aborting the entire pipeline
                return None

            # Trigger export
            try:
                export_res = await client.post(
                    f"https://api.submagic.co/v1/projects/{project_id}/export", headers=headers
                )
                export_res.raise_for_status()
            except Exception:
                # If export fails, return None
                return None

            # Poll for completion
            total_checks = 60  # up to 5 minutes
            for i in range(total_checks):
                try:
                    proj_res = await client.get(
                        f"https://api.submagic.co/v1/projects/{project_id}", headers=headers
                    )
                    proj_res.raise_for_status()
                    proj_data = proj_res.json()
                    status = proj_data.get("status")
                    download_url = proj_data.get("downloadUrl") or proj_data.get("directUrl")
                    # update progress between 75% and 95%
                    progress_fraction = 0.75 + (i / total_checks) * 0.2
                    await self._update_job(job_id, JobState.adding_captions, progress_fraction)
                    if status == "completed" and download_url:
                        return download_url
                    elif status == "failed":
                        return None
                    await asyncio.sleep(5)
                except Exception:
                    await asyncio.sleep(5)
        return None

    async def _update_job(self, job_id: str, state: JobState, progress: float) -> None:
        """Helper to update the job storage.

        Progress is clamped to the [0.0, 1.0] range. The job record is
        modified in place and persisted to storage.
        """
        job = self.job_storage.get(job_id)
        if not job:
            return
        job.status = state
        job.progress = max(0.0, min(progress, 1.0))
        # Persist back into storage (Redis or memory)
        self.job_storage.set(job_id, job)

    def _fallback_script(self, prompt: str) -> List[Dict[str, str]]:
        """Return a better emergency fallback script when Gemini fails.

        Creates varied, natural-sounding dialogue that avoids repetitive phrases.
        Each scene has completely different content focused on the prompt topic.
        """
        print(f"[WARNING] Using fallback script for: {prompt}")
        scenes: List[Dict[str, str]] = []
        
        # Create more natural, varied dialogue templates
        templates = [
            f"Let's explore {prompt} and discover what makes it truly fascinating for millions around the world today.",
            f"Understanding {prompt} requires looking at how it's evolved and where it's headed in the coming years ahead.",
            f"What makes {prompt} so remarkable isn't just what it is but how it's changing lives everywhere right now.",
            f"From its origins to its current impact {prompt} continues to shape our world in unexpected and powerful ways.",
            f"The future of {prompt} holds incredible possibilities that we're only beginning to understand and experience fully today."
        ]
        
        visuals = [
            "Dynamic opening shot with engaging visuals and movement",
            "Contextual imagery showing historical or foundational elements",
            "Core content visualization with detailed close-ups and information",
            "Impact shots showing real-world effects and transformations",
            "Closing scene with forward-looking perspective and hope"
        ]
        
        for idx, (template, visual) in enumerate(zip(templates, visuals), start=1):
            words = template.split()
            # Ensure exactly 18 words
            if len(words) < 18:
                words += ["and more"] * ((18 - len(words)) // 2)
            words = words[:18]
            
            scenes.append({
                "scene_number": idx,
                "visual_description": visual,
                "dialogue": " ".join(words),
            })
        
        return scenes