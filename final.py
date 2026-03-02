import os
import json
import time
import uuid
import random
import shutil
import threading
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIG
# =============================================================================
KIE_KEY = os.getenv("KIEAI_API_KEY")
if not KIE_KEY:
    raise RuntimeError("KIEAI_API_KEY not found in .env")

AUTH = {"Authorization": f"Bearer {KIE_KEY}"}
JAUTH = {"Authorization": f"Bearer {KIE_KEY}", "Content-Type": "application/json"}

# Gemini 2.5 Pro on KIE (OpenAI-compatible chat completions shape)
# Docs show: https://api.kie.ai/gemini-2.5-pro/v1/chat/completions  :contentReference[oaicite:6]{index=6}
# GEMINI_CHAT_URL = "https://api.kie.ai/gemini-2.5-pro/v1/chat/completions"
GEMINI_CHAT_URL = "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions"

# Flux Kontext endpoints (generate + poll)  :contentReference[oaicite:7]{index=7}
FLUX_GEN_URL = "https://api.kie.ai/api/v1/flux/kontext/generate"
FLUX_POLL_URL = "https://api.kie.ai/api/v1/flux/kontext/record-info"

# KIE file upload endpoint (used by your existing pipeline)
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-stream-upload"

# Veo3.1 endpoints (generate + poll), and model "veo3" for Quality  :contentReference[oaicite:8]{index=8}
VEO_GEN_URL = "https://api.kie.ai/api/v1/veo/generate"
VEO_POLL_URL = "https://api.kie.ai/api/v1/veo/record-info"
VEO_MODEL = "veo3"            # Veo 3.1 Quality
ASPECT_RATIO = "9:16"
GENERATION_TYPE = "FIRST_AND_LAST_FRAMES_2_VIDEO"

# Job storage
BASE_DIR = Path("jobs")
BASE_DIR.mkdir(exist_ok=True)

# =============================================================================
# FASTAPI
# =============================================================================
app = FastAPI(title="Gemini→Flux→Veo Job Service")

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CreateJobRequest(BaseModel):
    prompt: str

# In-memory job registry (simple + effective for a single machine)
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

def log(job_id: str, msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with JOBS_LOCK:
        JOBS[job_id]["logs"].append(line)
        # keep logs bounded
        if len(JOBS[job_id]["logs"]) > 5000:
            JOBS[job_id]["logs"] = JOBS[job_id]["logs"][-3000:]
    print(f"{job_id} {line}", flush=True)

def set_status(job_id: str, status: str, step: str = "", progress: int = 0) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["status"] = status
        if step:
            JOBS[job_id]["step"] = step
        if progress is not None:
            JOBS[job_id]["progress"] = progress

def safe_get_job(job_id: str) -> Dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job

# =============================================================================
# KIE HELPERS
# =============================================================================
def gemini_structured_plan(job_id: str, user_prompt: str) -> Dict[str, Any]:
    """
    WORKING VERSION: Template-based approach that works with KIE's Gemini API
    KIE Gemini doesn't support OpenAI-style structured outputs, so we use text parsing
    """
    log(job_id, "GEMINI: Using template-based approach (FIXED VERSION)")
    
    # Use a simple template format that Gemini can understand
    system_msg = '''I need you to create a video plan with exactly 6 scenes for the elements: AIR, WATER, EARTH, FIRE, SCIENCE, COSMOS.

Please format your response EXACTLY like this example:

TITLE: [Your title here]
AVATAR: [Avatar description here]

SCENE_1_AIR:
- ID: scene_1_air
- DIALOGUE: [Air dialogue here]
- AVATAR_PROMPT: [Avatar description] in an air environment, photorealistic, cinematic lighting, 9:16 portrait
- VIDEO_PROMPT: [Air scene description] with natural spoken dialogue and subtle cinematic background music

SCENE_2_WATER:
- ID: scene_2_water  
- DIALOGUE: [Water dialogue here]
- AVATAR_PROMPT: [Same avatar description] in a water environment, photorealistic, cinematic lighting, 9:16 portrait
- VIDEO_PROMPT: [Water scene description] with natural spoken dialogue and subtle cinematic background music

SCENE_3_EARTH:
- ID: scene_3_earth
- DIALOGUE: [Earth dialogue here]  
- AVATAR_PROMPT: [Same avatar description] in an earth environment, photorealistic, cinematic lighting, 9:16 portrait
- VIDEO_PROMPT: [Earth scene description] with natural spoken dialogue and subtle cinematic background music

SCENE_4_FIRE:
- ID: scene_4_fire
- DIALOGUE: [Fire dialogue here]
- AVATAR_PROMPT: [Same avatar description] in a fire environment, photorealistic, cinematic lighting, 9:16 portrait  
- VIDEO_PROMPT: [Fire scene description] with natural spoken dialogue and subtle cinematic background music

SCENE_5_SCIENCE:
- ID: scene_5_science
- DIALOGUE: [Science dialogue here]
- AVATAR_PROMPT: [Same avatar description] in a science environment, photorealistic, cinematic lighting, 9:16 portrait
- VIDEO_PROMPT: [Science scene description] with natural spoken dialogue and subtle cinematic background music

SCENE_6_COSMOS:
- ID: scene_6_cosmos
- DIALOGUE: [Cosmos dialogue here] 
- AVATAR_PROMPT: [Same avatar description] in a cosmic environment, photorealistic, cinematic lighting, 9:16 portrait
- VIDEO_PROMPT: [Cosmos scene description] with natural spoken dialogue and subtle cinematic background music

Use the same avatar character in all scenes but change the environment. Make the dialogue meaningful and thematic.'''
    
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_msg}]},
            {"role": "user", "content": [{"type": "text", "text": f"Create a video plan for theme: {user_prompt}"}]}
        ],
        "max_tokens": 3000,
        "temperature": 0.7
        # NOTE: Removed response_format - KIE Gemini doesn't support structured outputs
    }
    
    max_tries = 3
    for attempt in range(1, max_tries + 1):
        log(job_id, f"GEMINI: template approach attempt {attempt}/{max_tries}")
        
        try:
            r = requests.post(GEMINI_CHAT_URL, headers=JAUTH, json=payload, timeout=240)
            log(job_id, f"GEMINI: HTTP {r.status_code}")
            
            # Handle gateway errors
            if r.status_code in (524, 520, 522, 523, 504, 502, 503, 500):
                snippet = (r.text or "")[:120].replace("\n", " ")
                log(job_id, f"GEMINI: transient gateway error {r.status_code} ({snippet}) -> retry")
                time.sleep(8 * attempt)
                continue
            
            if r.status_code != 200:
                log(job_id, f"GEMINI: HTTP error {r.status_code}, retrying...")
                time.sleep(5 * attempt)
                continue
            
            data = r.json()
            
            # Handle KIE-style wrapped errors
            if data.get("code") not in (None, 200):
                msg = (data.get("msg") or "").lower()
                if data.get("code") in (500, 502, 503, 504) and ("maintain" in msg or "maintenance" in msg or "try again" in msg):
                    log(job_id, f"GEMINI: retryable API error: {json.dumps(data)[:200]} -> retry")
                    time.sleep(8 * attempt)
                    continue
                raise RuntimeError(f"Gemini API error: {json.dumps(data)[:800]}")
            
            if "choices" not in data:
                log(job_id, f"GEMINI: Invalid response format, retrying...")
                time.sleep(3 * attempt)
                continue
                
            content = data["choices"][0]["message"]["content"]
            if not content:
                log(job_id, f"GEMINI: Empty content, retrying...")
                time.sleep(3 * attempt)
                continue
            
            log(job_id, f"GEMINI: Got response, parsing...")
            
            # Parse the structured text response into JSON
            result = parse_gemini_response(content)
            
            if result and len(result.get("scenes", [])) == 6:
                log(job_id, "GEMINI: Template parsing successful ✅")
                return result
            else:
                log(job_id, f"GEMINI: Parsing failed, retrying...")
                time.sleep(3 * attempt)
                
        except Exception as e:
            log(job_id, f"GEMINI: Error {type(e).__name__}: {str(e)[:100]}, retrying...")
            time.sleep(5 * attempt)
    
    # If all else fails, create a reliable fallback
    log(job_id, "GEMINI: Using fallback template")
    return create_fallback_plan(user_prompt)

def parse_gemini_response(content: str) -> Dict[str, Any]:
    """Parse the structured text response from Gemini into JSON format"""
    
    try:
        # Extract title
        title_match = re.search(r'TITLE:\s*(.+)', content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "Mystical Journey"
        
        # Extract avatar description
        avatar_match = re.search(r'AVATAR:\s*(.+)', content, re.IGNORECASE)
        avatar_identity = avatar_match.group(1).strip() if avatar_match else "A mystical sage with flowing robes"
        
        scenes = []
        elements = ["AIR", "WATER", "EARTH", "FIRE", "SCIENCE", "COSMOS"]
        
        for i, element in enumerate(elements, 1):
            scene_pattern = rf'SCENE_{i}_{element}:\s*(.+?)(?=SCENE_\d+_|$)'
            scene_match = re.search(scene_pattern, content, re.DOTALL | re.IGNORECASE)
            
            if scene_match:
                scene_content = scene_match.group(1)
                
                # Extract scene details
                id_match = re.search(r'ID:\s*(.+)', scene_content, re.IGNORECASE)
                dialogue_match = re.search(r'DIALOGUE:\s*(.+)', scene_content, re.IGNORECASE)
                avatar_prompt_match = re.search(r'AVATAR_PROMPT:\s*(.+)', scene_content, re.IGNORECASE)
                video_prompt_match = re.search(r'VIDEO_PROMPT:\s*(.+)', scene_content, re.IGNORECASE)
                
                scene = {
                    "id": id_match.group(1).strip() if id_match else f"scene_{i}_{element.lower()}",
                    "element": element,
                    "dialogue": dialogue_match.group(1).strip() if dialogue_match else f"Explore the essence of {element.lower()}",
                    "avatar_prompt": avatar_prompt_match.group(1).strip() if avatar_prompt_match else f"{avatar_identity} in {element.lower()} environment, photorealistic, cinematic lighting, 9:16 portrait",
                    "video_prompt": video_prompt_match.group(1).strip() if video_prompt_match else f"{element.lower()} themed scene with natural spoken dialogue and subtle cinematic background music"
                }
                scenes.append(scene)
        
        # Fill missing scenes with defaults
        while len(scenes) < 6:
            idx = len(scenes)
            element = elements[idx]
            scenes.append({
                "id": f"scene_{idx + 1}_{element.lower()}",
                "element": element,
                "dialogue": f"Experience the power of {element.lower()}",
                "avatar_prompt": f"{avatar_identity} in {element.lower()} environment, photorealistic, cinematic lighting, 9:16 portrait",
                "video_prompt": f"{element.lower()} themed scene with natural spoken dialogue and subtle cinematic background music"
            })
        
        return {
            "title": title,
            "avatar_identity": avatar_identity,
            "scenes": scenes[:6]  # Ensure exactly 6 scenes
        }
        
    except Exception as e:
        print(f"Parsing error: {e}")
        return None

def create_fallback_plan(user_prompt: str) -> Dict[str, Any]:
    """Create a reliable fallback plan if all API calls fail"""
    
    avatar = "A mystical sage with flowing ethereal robes and wise glowing eyes"
    
    scenes = [
        {
            "id": "scene_1_air",
            "element": "AIR",
            "dialogue": "In the realm of air, thoughts take flight and dreams soar beyond the clouds",
            "avatar_prompt": f"{avatar} floating among swirling clouds and winds, photorealistic, cinematic lighting, 9:16 portrait",
            "video_prompt": "Mystical figure in flowing air currents with natural spoken dialogue and subtle atmospheric background music"
        },
        {
            "id": "scene_2_water",
            "element": "WATER",
            "dialogue": "From the depths of water flows the essence of life and emotion",
            "avatar_prompt": f"{avatar} standing by cascading waterfalls and flowing streams, photorealistic, cinematic lighting, 9:16 portrait",
            "video_prompt": "Serene water environment with flowing streams, natural spoken dialogue and gentle aquatic background music"
        },
        {
            "id": "scene_3_earth",
            "element": "EARTH",
            "dialogue": "In earth we find foundation, growth, and the strength of ancient wisdom",
            "avatar_prompt": f"{avatar} in a mystical forest with ancient trees and glowing crystals, photorealistic, cinematic lighting, 9:16 portrait",
            "video_prompt": "Mystical forest setting with earth elements, natural spoken dialogue and organic background music"
        },
        {
            "id": "scene_4_fire",
            "element": "FIRE",
            "dialogue": "Fire brings transformation, passion, and the energy of creation",
            "avatar_prompt": f"{avatar} surrounded by magical flames and glowing embers, photorealistic, cinematic lighting, 9:16 portrait",
            "video_prompt": "Mystical fire environment with dancing flames, natural spoken dialogue and warm rhythmic background music"
        },
        {
            "id": "scene_5_science",
            "element": "SCIENCE",
            "dialogue": "Through science we unlock the mysteries of existence and reality",
            "avatar_prompt": f"{avatar} in a mystical laboratory with floating geometric patterns and energy, photorealistic, cinematic lighting, 9:16 portrait",
            "video_prompt": "Scientific mystical environment with energy patterns, natural spoken dialogue and cosmic background music"
        },
        {
            "id": "scene_6_cosmos",
            "element": "COSMOS",
            "dialogue": "In the cosmos we discover our place in the infinite tapestry of existence",
            "avatar_prompt": f"{avatar} floating in space surrounded by stars and galaxies, photorealistic, cinematic lighting, 9:16 portrait",
            "video_prompt": "Cosmic space environment with stars and galaxies, natural spoken dialogue and ethereal cosmic background music"
        }
    ]
    
    return {
        "title": f"Mystical Journey: {user_prompt}",
        "avatar_identity": avatar,
        "scenes": scenes
    }




def flux_generate_one(job_id: str, prompt: str, out_path: Path) -> None:
    """
    Create Flux task -> poll -> download image to out_path
    """
    log(job_id, f"FLUX: submit image task -> {out_path.name}")
    payload = {
        "prompt": prompt,
        "aspectRatio": ASPECT_RATIO,
        "outputFormat": "png",
        "model": "flux-kontext-max",
        "promptUpsampling": True,
        "enableTranslation": True,
        "safetyTolerance": 2,
    }

    r = requests.post(FLUX_GEN_URL, headers=JAUTH, json=payload, timeout=60)
    d = r.json()
    if d.get("code") != 200:
        raise RuntimeError(f"Flux submit failed: {json.dumps(d)[:500]}")
    task_id = d["data"]["taskId"]
    log(job_id, f"FLUX: taskId={task_id}")

    # poll
    while True:
        time.sleep(8)
        pr = requests.get(FLUX_POLL_URL, headers=AUTH, params={"taskId": task_id}, timeout=30)
        pd = pr.json()
        if pd.get("code") != 200:
            continue
        info = pd.get("data") or {}
        flag = info.get("successFlag")
        if flag == 1:
            url = (info.get("response") or {}).get("resultImageUrl")
            if not url:
                raise RuntimeError("Flux success but no resultImageUrl.")
            log(job_id, f"FLUX: done -> downloading {out_path.name}")
            img = requests.get(url, timeout=120)
            img.raise_for_status()
            out_path.write_bytes(img.content)
            log(job_id, f"FLUX: saved {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return
        if flag in (2, 3):
            raise RuntimeError(f"Flux generation failed (successFlag={flag})")

def kie_upload_image(job_id: str, image_path: Path) -> str:
    """
    Upload local image so Veo can access it; returns downloadUrl
    """
    log(job_id, f"UPLOAD: uploading {image_path.name}")
    with open(image_path, "rb") as f:
        r = requests.post(
            UPLOAD_URL,
            headers=AUTH,
            files={"file": (image_path.name, f, "image/png")},
            data={"uploadPath": f"job-{job_id}", "fileName": image_path.name},
            timeout=60,
        )
    d = r.json()
    if d.get("code") != 200:
        raise RuntimeError(f"Upload failed: {json.dumps(d)[:500]}")
    url = (d.get("data") or {}).get("downloadUrl")
    if not url:
        raise RuntimeError("Upload success but no downloadUrl.")
    log(job_id, f"UPLOAD: url ready for {image_path.name}")
    return url

def veo_generate_clip(job_id: str, prompt: str, image_url: str, out_path: Path) -> None:
    """
    Create Veo task -> poll -> download video clip
    Veo docs: model 'veo3' quality; audio track ships by default.  :contentReference[oaicite:9]{index=9}
    """
    seed = random.randint(10000, 99999)
    log(job_id, f"VEO: submit clip -> {out_path.name} (seed={seed})")

    payload = {
        "prompt": prompt,
        "imageUrls": [image_url],
        "model": VEO_MODEL,
        "aspect_ratio": ASPECT_RATIO,
        "seeds": seed,
        "enableFallback": False,
        "enableTranslation": True,
        "generationType": GENERATION_TYPE,
    }

    r = requests.post(VEO_GEN_URL, headers=JAUTH, json=payload, timeout=90)
    d = r.json()
    if d.get("code") != 200:
        raise RuntimeError(f"Veo submit failed: {json.dumps(d)[:700]}")
    task_id = d["data"]["taskId"]
    log(job_id, f"VEO: taskId={task_id}")

    while True:
        time.sleep(12)
        pr = requests.get(VEO_POLL_URL, headers=AUTH, params={"taskId": task_id}, timeout=30)
        pd = pr.json()
        if pd.get("code") != 200:
            continue
        info = pd.get("data") or {}
        flag = info.get("successFlag")
        if flag == 1:
            urls = (info.get("response") or {}).get("resultUrls") or []
            if not urls:
                raise RuntimeError("Veo success but no resultUrls.")
            video_url = urls[0]
            log(job_id, f"VEO: done -> downloading {out_path.name}")
            v = requests.get(video_url, timeout=300)
            v.raise_for_status()
            out_path.write_bytes(v.content)
            log(job_id, f"VEO: saved {out_path.name} ({out_path.stat().st_size // 1024} KB)")
            return
        if flag in (2, 3):
            raise RuntimeError(f"Veo generation failed (successFlag={flag})")

def ffmpeg_concat(job_id: str, clips: List[Path], final_path: Path) -> None:
    """
    Safer concat: normalize to one consistent spec, then concat.
    """
    log(job_id, "FFMPEG: normalizing clips…")
    norm_dir = final_path.parent / "norm"
    if norm_dir.exists():
        shutil.rmtree(norm_dir)
    norm_dir.mkdir(parents=True, exist_ok=True)

    normed = []
    for i, clip in enumerate(clips):
        out = norm_dir / f"norm_{i}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip),
            "-vf", "scale=608:1080:force_original_aspect_ratio=decrease,"
                   "pad=608:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "24",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            str(out),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"ffmpeg normalize failed: {res.stderr[-500:]}")
        normed.append(out)
        log(job_id, f"FFMPEG: normalized {clip.name} -> {out.name}")

    lst = final_path.parent / "concat.txt"
    with open(lst, "w") as f:
        for c in normed:
            f.write(f"file '{c.resolve()}'\n")

    log(job_id, "FFMPEG: concatenating into final.mp4…")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(lst),
        "-c", "copy",
        str(final_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {res.stderr[-500:]}")

    log(job_id, f"FFMPEG: final ready -> {final_path.name} ({final_path.stat().st_size // (1024*1024)} MB)")

# =============================================================================
# JOB RUNNER
# =============================================================================
def run_job(job_id: str, user_prompt: str) -> None:
    job_dir = BASE_DIR / job_id
    avatars_dir = job_dir / "avatars"
    clips_dir = job_dir / "clips"
    job_dir.mkdir(parents=True, exist_ok=True)
    avatars_dir.mkdir(exist_ok=True)
    clips_dir.mkdir(exist_ok=True)
    final_path = job_dir / "final.mp4"

    try:
        set_status(job_id, "running", step="planning", progress=2)
        log(job_id, "JOB: started")

        # 1) Gemini plan
        plan = gemini_structured_plan(job_id, user_prompt)
        (job_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        set_status(job_id, "running", step="avatars", progress=10)

        # 2) Generate 6 avatars via Flux
        scenes = plan["scenes"]
        for idx, s in enumerate(scenes, 1):
            out_path = avatars_dir / f"{s['id']}.png"
            flux_generate_one(job_id, s["avatar_prompt"], out_path)
            set_status(job_id, "running", step="avatars", progress=10 + int(idx * 10 / 6))

        set_status(job_id, "running", step="video", progress=25)
        log(job_id, "JOB: avatars complete")

        # 3) For each avatar: upload -> Veo video
        clips: List[Path] = []
        for idx, s in enumerate(scenes, 1):
            avatar_path = avatars_dir / f"{s['id']}.png"
            image_url = kie_upload_image(job_id, avatar_path)

            # Force explicit audio+music instructions in prompt (even though Veo ships bg audio by default)  :contentReference[oaicite:10]{index=10}
            veo_prompt = (
                f"{s['video_prompt']}\n\n"
                f'DIALOGUE TO SPEAK (natural voice): "{s["dialogue"]}"\n'
                "AUDIO REQUIREMENTS:\n"
                "- Include natural spoken dialogue (clear voice)\n"
                "- Include subtle cinematic background music UNDER the voice\n"
                "- Professional audio mix, no clipping, balanced levels\n"
                "- Keep it cinematic and emotionally fitting\n"
            )

            clip_path = clips_dir / f"clip_{idx:02d}_{s['id']}.mp4"
            veo_generate_clip(job_id, veo_prompt, image_url, clip_path)
            clips.append(clip_path)

            set_status(job_id, "running", step="video", progress=25 + int(idx * 55 / 6))

        # 4) Merge
        set_status(job_id, "running", step="merge", progress=85)
        log(job_id, "JOB: all clips ready, merging…")
        ffmpeg_concat(job_id, clips, final_path)

        set_status(job_id, "done", step="done", progress=100)
        with JOBS_LOCK:
            JOBS[job_id]["output_path"] = str(final_path)
        log(job_id, "JOB: done ✅")

    except Exception as e:
        set_status(job_id, "error", step="error", progress=100)
        log(job_id, f"JOB: error ❌ {type(e).__name__}: {e}")

# =============================================================================
# API ENDPOINTS (3)
# =============================================================================
@app.post("/jobs")
def create_job(req: CreateJobRequest):
    job_id = uuid.uuid4().hex[:12]
    job_dir = BASE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "step": "queued",
            "progress": 0,
            "created_at": time.time(),
            "prompt": req.prompt,
            "logs": [],
            "output_path": None,
        }

    log(job_id, "API: job created (queued)")
    t = threading.Thread(target=run_job, args=(job_id, req.prompt), daemon=True)
    t.start()

    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    try:
        job = safe_get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")

    # return last 200 lines to keep payload small
    logs_tail = job["logs"][-200:]
    return {
        "job_id": job_id,
        "status": job["status"],
        "step": job["step"],
        "progress": job["progress"],
        "output_ready": bool(job["output_path"]) and job["status"] == "done",
        "logs_tail": logs_tail,
    }

@app.get("/jobs/{job_id}/download")
def download(job_id: str):
    try:
        job = safe_get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")

    if job["status"] != "done" or not job["output_path"]:
        raise HTTPException(status_code=409, detail="output not ready")

    path = Path(job["output_path"])
    if not path.exists():
        raise HTTPException(status_code=500, detail="output file missing on disk")

    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )