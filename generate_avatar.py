#!/usr/bin/env python3
"""
ELEMENTS OF EXISTENCE - Avatar Image Generator
KIE.ai Flux Kontext API

Polling endpoint (confirmed from official docs):
  GET https://api.kie.ai/api/v1/flux/kontext/record-info?taskId=xxx
  Response: data.response.resultImageUrl
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# ── Load API key ───────────────────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("KIEAI_API_KEY")

if not API_KEY:
    print("ERROR: KIEAI_API_KEY not found in .env file.")
    sys.exit(1)

# ── API Endpoints ──────────────────────────────────────────────────────────────
#
#  GENERATE:  POST /api/v1/flux/kontext/generate
#  POLL:      GET  /api/v1/flux/kontext/record-info?taskId=xxx
#
#  Source: https://docs.kie.ai/flux-kontext-api/get-image-details
#  The poll response shape is:
#    { code: 200, data: { successFlag: 1, response: { resultImageUrl: "..." } } }
#
API_BASE     = "https://api.kie.ai/api"
GENERATE_URL = f"{API_BASE}/v1/flux/kontext/generate"
POLL_URL     = f"{API_BASE}/v1/flux/kontext/record-info"   # taskId as ?taskId= query param

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

OUTPUT_DIR = Path("avatar_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Avatar Identity (locked across all 6 scenes) ───────────────────────────────
AVATAR_BASE = (
    "Portrait photo of a 30-year-old South Asian man with sharp defined features, "
    "strong jawline, medium-length dark wavy hair, light stubble beard, "
    "deep brown expressive eyes, warm tan skin tone. "
    "He is wearing a timeless dark charcoal high-collar jacket. "
    "Ultra-realistic photographic quality, 8K, cinematic lighting, "
    "same exact face and identity in all images. "
)

NEG = "Avoid cartoon, anime, illustration, distorted face, extra limbs, blur, watermark."

# ── 6 Scene Prompts ────────────────────────────────────────────────────────────
SCENES = [
    {
        "id":      "scene_1_air",
        "element": "AIR",
        "prompt":  AVATAR_BASE + (
            "Scene: Mountaintop at golden hour, vast open sky, wind-swept clouds behind him. "
            "Chin tilted slightly upward toward the sky, eyes open wide with a calm knowing smile, "
            "hair gently blown by the breeze. Warm golden-hour side lighting. Medium close-up, slight low angle. "
            "Mood: serene, transcendent, free. " + NEG
        ),
    },
    {
        "id":      "scene_2_water",
        "element": "WATER",
        "prompt":  AVATAR_BASE + (
            "Scene: Ocean shoreline at sunrise, waves gently in background, golden-blue reflections on water. "
            "Head tilted slightly downward looking at water, eyes raising to horizon with quiet determined expression. "
            "Cool blue-gold ambient light. Mid-shot, eye level, water visible in foreground. "
            "Mood: contemplative, resilient, fluid. " + NEG
        ),
    },
    {
        "id":      "scene_3_earth",
        "element": "EARTH",
        "prompt":  AVATAR_BASE + (
            "Scene: Ancient dense forest, beside a massive ancient tree, one hand resting on bark, "
            "eyes closed with deep reverence, dappled golden sunlight filtering through leaves above him. "
            "Warm earth tones, green bokeh background. Close-up on face and hand. "
            "Mood: rooted, wise, ancient. " + NEG
        ),
    },
    {
        "id":      "scene_4_fire",
        "element": "FIRE",
        "prompt":  AVATAR_BASE + (
            "Scene: Volcanic rocky landscape at dusk, fire and ember glow reflecting warm orange-red on his face. "
            "Intense passionate gaze directly into camera, slight forward lean, jaw set with fierce controlled energy. "
            "Sparks rising in background, dramatic dark sky. Tight medium close-up, fire as key light from below. "
            "Mood: passionate, purposeful, commanding. " + NEG
        ),
    },
    {
        "id":      "scene_5_science",
        "element": "SCIENCE",
        "prompt":  AVATAR_BASE + (
            "Scene: Futuristic laboratory, surrounded by holographic data streams and glowing equations. "
            "One eyebrow raised, thoughtful head tilt, finger briefly at temple, then a sharp insightful smile. "
            "Cool blue-white ambient light, neon digital glow. Medium close-up, holographic elements in background. "
            "Mood: intelligent, curious, wonder-filled. " + NEG
        ),
    },
    {
        "id":      "scene_6_cosmos",
        "element": "COSMOS",
        "prompt":  AVATAR_BASE + (
            "Scene: Open desert at night under the Milky Way, infinite starfield, head tilted back, "
            "arms slightly open at sides, eyes wide open with pure awe and peace, gentle emotional softness, "
            "a full open smile. Starlight and faint nebula glow as only light source. Medium close-up against stars. "
            "Mood: cosmic, awe-struck, infinite, complete. " + NEG
        ),
    },
]


# ── submit_task ────────────────────────────────────────────────────────────────
def submit_task(scene):
    payload = {
        "prompt":            scene["prompt"],
        "aspectRatio":       "9:16",
        "outputFormat":      "png",
        "model":             "flux-kontext-max",
        "promptUpsampling":  True,
        "enableTranslation": False,
        "safetyTolerance":   2,
    }

    print(f"\n  [SUBMIT] {scene['element']}")
    print(f"           POST {GENERATE_URL}")

    try:
        resp = requests.post(GENERATE_URL, headers=HEADERS, json=payload, timeout=30)
        print(f"           HTTP {resp.status_code}")

        try:
            data = resp.json()
        except Exception as e:
            print(f"  [ERROR]  Could not parse JSON: {e}")
            print(f"           Raw: {resp.text[:300]}")
            return None

        print(f"           API code={data.get('code')}  msg={data.get('msg')}")

        if data.get("code") == 200:
            task_id = (data.get("data") or {}).get("taskId")
            if task_id:
                print(f"  [OK]     taskId: {task_id}")
                return task_id
            else:
                print(f"  [ERROR]  200 but no taskId. Full response:")
                print(f"           {json.dumps(data, indent=10)}")
                return None
        else:
            print(f"  [ERROR]  Full response: {json.dumps(data, indent=10)[:400]}")
            return None

    except requests.exceptions.Timeout:
        print(f"  [ERROR]  Submission timed out after 30s")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR]  {type(e).__name__}: {e}")
        return None


# ── poll_task ──────────────────────────────────────────────────────────────────
def poll_task(task_id, element, timeout=300):
    """
    Official endpoint: GET /api/v1/flux/kontext/record-info?taskId=xxx
    Source: https://docs.kie.ai/flux-kontext-api/get-image-details

    Success response shape:
      { code: 200, data: {
          successFlag: 1,
          response: { resultImageUrl: "https://..." }
      }}
    successFlag: 0=processing, 1=success, 2=failed
    """
    start    = time.time()
    interval = 8
    attempt  = 0

    print(f"\n  [POLL]   {element}  taskId={task_id}")
    print(f"           URL: {POLL_URL}?taskId={task_id}")
    print(f"           Polling every {interval}s, timeout={timeout}s")

    while time.time() - start < timeout:
        attempt += 1
        elapsed = int(time.time() - start)
        print(f"\n           Attempt #{attempt}  elapsed={elapsed}s")
        print(f"           GET {POLL_URL}?taskId={task_id}")

        try:
            resp = requests.get(
                POLL_URL,
                headers=HEADERS,
                params={"taskId": task_id},
                timeout=15,
            )
            print(f"           HTTP {resp.status_code}")

            try:
                data = resp.json()
            except Exception as e:
                print(f"  [ERROR]  JSON parse failed: {e}")
                print(f"           Raw: {resp.text[:300]}")
                time.sleep(interval)
                continue

            api_code = data.get("code")
            api_msg  = data.get("msg", "<none>")
            print(f"           API code={api_code}  msg={api_msg}")

            if api_code != 200:
                print(f"  [WARN]   Non-200 response body:")
                print(f"           {json.dumps(data, indent=11)[:500]}")
                print(f"           Retrying in {interval}s...")
                time.sleep(interval)
                continue

            task_data    = data.get("data") or {}
            success_flag = task_data.get("successFlag")
            progress     = task_data.get("progress", "?")
            label        = {0: "processing", 1: "success", 2: "failed"}.get(success_flag, f"unknown({success_flag})")
            print(f"           successFlag={success_flag} ({label})  progress={progress}%")

            if success_flag == 1:
                # Official response shape: data.response.resultImageUrl
                response_block = task_data.get("response") or {}
                image_url = (
                    response_block.get("resultImageUrl") or
                    response_block.get("originImageUrl") or
                    task_data.get("resultImageUrl") or
                    task_data.get("imageUrl") or
                    task_data.get("resultUrl")
                )
                if image_url:
                    print(f"  [DONE]   Image URL: {image_url}")
                    return image_url
                else:
                    print(f"  [ERROR]  successFlag=1 but no image URL found!")
                    print(f"           Full data block:")
                    print(f"           {json.dumps(task_data, indent=11)}")
                    return None

            elif success_flag == 2:
                err = task_data.get("errorMessage") or task_data.get("error") or "unknown"
                print(f"  [FAIL]   Server reported generation failure: {err}")
                print(f"           Full data: {json.dumps(task_data, indent=11)}")
                return None

            else:
                print(f"           Still processing... waiting {interval}s")
                time.sleep(interval)

        except requests.exceptions.Timeout:
            print(f"  [WARN]   Poll request timed out (15s). Retrying...")
            time.sleep(interval)
        except requests.exceptions.RequestException as e:
            print(f"  [WARN]   {type(e).__name__}: {e}. Retrying in {interval}s...")
            time.sleep(interval)

    print(f"\n  [TIMEOUT] {element} — gave up after {timeout}s ({attempt} attempts)")
    return None


# ── download_image ─────────────────────────────────────────────────────────────
def download_image(url, filepath):
    print(f"  [DL]     Downloading → {filepath}")
    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        kb = filepath.stat().st_size // 1024
        print(f"  [SAVED]  {filepath} ({kb} KB)")
        return True
    except Exception as e:
        print(f"  [ERROR]  Download failed: {e}")
        return False


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 65)
    print("  ELEMENTS OF EXISTENCE - Avatar Generator")
    print("  KIE.ai | Flux Kontext Max | 6 Scenes")
    print("=" * 65)
    print(f"  Output: ./{OUTPUT_DIR}/")
    print(f"  Scenes: {len(SCENES)}")
    print(f"  Poll endpoint: {POLL_URL}?taskId=xxx")
    print("-" * 65)

    results  = []
    task_map = {}

    # Phase 1 — Submit all
    print("\n[PHASE 1] Submitting all tasks...\n")
    for scene in SCENES:
        task_id = submit_task(scene)
        if task_id:
            task_map[scene["id"]] = task_id
        else:
            results.append({"element": scene["element"], "status": "submit_failed", "file": None, "url": None})
        time.sleep(1.5)

    # Phase 2 — Poll and download
    print("\n\n[PHASE 2] Polling and downloading...\n")
    for scene in SCENES:
        task_id = task_map.get(scene["id"])
        if not task_id:
            continue

        image_url = poll_task(task_id, scene["element"])
        if image_url:
            fp      = OUTPUT_DIR / f"{scene['id']}.png"
            success = download_image(image_url, fp)
            results.append({
                "element": scene["element"],
                "status":  "success" if success else "download_failed",
                "file":    str(fp) if success else None,
                "url":     image_url,
                "task_id": task_id,
            })
        else:
            results.append({"element": scene["element"], "status": "gen_failed", "file": None, "url": None, "task_id": task_id})

    # Save manifest
    manifest = OUTPUT_DIR / "manifest.json"
    with open(manifest, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Manifest saved: {manifest}")

    # Summary
    print("\n" + "=" * 65)
    print("  SUMMARY")
    print("-" * 65)
    ok = 0
    for r in results:
        icon = "[OK]" if r["status"] == "success" else "[XX]"
        info = r["file"] or r["status"]
        print(f"  {icon}  {r['element']:<12} {info}")
        if r["status"] == "success":
            ok += 1
    print("-" * 65)
    print(f"  Generated: {ok}/{len(SCENES)}")
    print("=" * 65)

    if ok > 0:
        print("""
  NEXT STEPS:
  1. Check ./avatar_outputs/ for your 6 images
  2. Pick the best face as your reference image
  3. Use it in Runway / Kling / HeyGen to lock the
     avatar identity across all 6 video scenes
        """)


if __name__ == "__main__":
    try:
        import dotenv  # noqa
    except ImportError:
        os.system(f"{sys.executable} -m pip install python-dotenv requests --quiet")
    main()
