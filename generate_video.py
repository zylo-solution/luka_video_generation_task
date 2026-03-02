#!/usr/bin/env python3
"""
ELEMENTS OF EXISTENCE — Full Video Pipeline
============================================
Fixes applied vs previous version:
  1. Music 422: Suno requires callBackUrl — now passed as a placeholder
  2. Video 402: kling-2.6 costs too much — switched to wan/2-2-a14b-image-to-video-turbo
               (cheapest Wan turbo model on KIE; falls back to wan/2-6-image-to-video)
  3. Video input field: Wan uses "image_url" (singular), Kling used "image_urls" (plural)
  4. Video poll: GET /api/v1/jobs/recordInfo?taskId=xxx
                 data.state == "success" → JSON.parse(data.resultJson).resultUrls[0]

ENDPOINTS (official docs):
  Upload:     POST https://kieai.redpandaai.co/api/file-stream-upload
  Music:      POST https://api.kie.ai/api/v1/generate
  Music poll: GET  https://api.kie.ai/api/v1/generate/record-info?taskId=xxx
  Video:      POST https://api.kie.ai/api/v1/jobs/createTask
  Video poll: GET  https://api.kie.ai/api/v1/jobs/recordInfo?taskId=xxx
  Merge:      local ffmpeg
"""

import os, sys, time, json, subprocess, requests
from pathlib import Path
from dotenv import load_dotenv

# ── Load key ───────────────────────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("KIEAI_API_KEY")
if not API_KEY:
    print("ERROR: KIEAI_API_KEY not found in .env"); sys.exit(1)

# ── Endpoints ──────────────────────────────────────────────────────────────────
UPLOAD_URL  = "https://kieai.redpandaai.co/api/file-stream-upload"
VIDEO_URL   = "https://api.kie.ai/api/v1/jobs/createTask"
VIDEO_POLL  = "https://api.kie.ai/api/v1/jobs/recordInfo"
MUSIC_URL   = "https://api.kie.ai/api/v1/generate"
MUSIC_POLL  = "https://api.kie.ai/api/v1/generate/record-info"

AUTH  = {"Authorization": f"Bearer {API_KEY}"}
JAUTH = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Official credit-check endpoint (docs.kie.ai/common-api/get-account-credits)
CREDIT_URL = "https://api.kie.ai/api/v1/chat/credit"

# Suno requires callBackUrl — pass a dummy since we poll manually.
DUMMY_CALLBACK = "https://webhook.site/placeholder-callback"

# Cheapest Wan image-to-video model on KIE (docs.kie.ai/market/wan/2-2-a14b-image-to-video-turbo)
VIDEO_MODEL = "wan/2-2-a14b-image-to-video-turbo"
# Fallback (wan/2-6-image-to-video) — costs more credits
VIDEO_MODEL_FALLBACK = "wan/2-6-image-to-video"

# Set to True the moment any 402 is received — stops all further API calls immediately
_credits_exhausted = False

AVATAR_DIR  = Path("avatar_outputs")
VIDEO_DIR   = Path("video_outputs"); VIDEO_DIR.mkdir(exist_ok=True)
MUSIC_DIR   = Path("music_outputs"); MUSIC_DIR.mkdir(exist_ok=True)
FINAL_VIDEO = Path("final_video.mp4")

# ── Scene definitions ──────────────────────────────────────────────────────────
SCENES = [
    {
        "id": "scene_1_air", "element": "AIR",
        "image": AVATAR_DIR / "scene_1_air.png",
        "video_prompt": (
            "Cinematic 9:16 portrait. The man's face and head position stay completely still "
            "and locked — exactly as in the reference image. Only the environment moves: "
            "golden-hour clouds drift slowly behind him, hair gently sways in breeze, "
            "warm light shimmers across skin. Eyes wide open with calm transcendence, "
            "chin tilted slightly upward. Lips move softly as he speaks: "
            "'Every breath you take... is the universe breathing through you.' "
            "Shallow depth of field, slow subtle parallax, cinematic warm color grade. "
            "Ultra-realistic 1080p. No sudden camera movement. No face distortion."
        ),
        "music_prompt": "Cinematic ambient orchestral, soft wind instruments, airy and transcendent, peaceful, instrumental only, 5 seconds",
        "music_style": "Cinematic Ambient",
    },
    {
        "id": "scene_2_water", "element": "WATER",
        "image": AVATAR_DIR / "scene_2_water.png",
        "video_prompt": (
            "Cinematic 9:16 portrait. Face direction locked exactly as reference image — "
            "no face rotation or camera shake. Ocean waves shimmer behind him, "
            "golden-blue reflections ripple on the water surface. "
            "His eyes slowly raise from the water to the far horizon with quiet resolve. "
            "Lips move as he speaks: 'Flow like water — adapt, persist, and carve your own path.' "
            "Cool blue-gold cinematic grade, medium close-up, natural wave motion in background. "
            "Ultra-realistic 1080p. No distortion. No sudden cuts."
        ),
        "music_prompt": "Cinematic ambient, deep resonant strings, ocean undertones, meditative and flowing, instrumental only, 5 seconds",
        "music_style": "Cinematic Ambient",
    },
    {
        "id": "scene_3_earth", "element": "EARTH",
        "image": AVATAR_DIR / "scene_3_earth.png",
        "video_prompt": (
            "Cinematic 9:16 portrait. Face and hand locked in position from reference image. "
            "Ancient forest: golden sunlight shifts gently through canopy, leaves sway subtly, "
            "bokeh background breathes with life. Eyes closed in deep reverence, "
            "slow gentle nod. Lips move softly: "
            "'You are rooted in something ancient — trust your ground.' "
            "Warm earth-tone cinematic grade, static camera with gentle rack focus. "
            "Ultra-realistic 1080p. No face movement beyond expression and lips."
        ),
        "music_prompt": "Cinematic ambient, low cello drones, warm earthy grounding tones, ancient, instrumental only, 5 seconds",
        "music_style": "Cinematic Ambient",
    },
    {
        "id": "scene_4_fire", "element": "FIRE",
        "image": AVATAR_DIR / "scene_4_fire.png",
        "video_prompt": (
            "Cinematic 9:16 portrait. Face locked — preserve direct forward gaze from reference. "
            "Fire dances behind him, orange-red flame light flickers dynamically across face. "
            "Embers and sparks rise upward, smoke curls in dramatic dark sky. "
            "Jaw set with fierce controlled energy, eyes burning with purpose. "
            "Lips move commanding: 'Ignite your purpose — fire doesn't apologize for its light.' "
            "Fire-lit cinematic grade, tight medium close-up, dynamic ember particles. "
            "Ultra-realistic 1080p. No face distortion. Flame only in background."
        ),
        "music_prompt": "Cinematic epic, powerful low brass and percussion, intense driving energy, instrumental only, 5 seconds",
        "music_style": "Cinematic Epic",
    },
    {
        "id": "scene_5_science", "element": "SCIENCE",
        "image": AVATAR_DIR / "scene_5_science.png",
        "video_prompt": (
            "Cinematic 9:16 portrait. Head tilt locked exactly as reference image. "
            "Holographic data streams and glowing equations float and pulse around him in 3D. "
            "Blue-white neon light pulses softly across face. Eyebrow raises slowly, "
            "sharp insightful smile forms. Lips move with precision: "
            "'Question everything. The answer is always the next question.' "
            "Cool neon blue-white cinematic grade, medium close-up, holographic depth layers. "
            "Ultra-realistic 1080p. No distortion. Holograms only in background."
        ),
        "music_prompt": "Electronic cinematic ambient, digital pulses, minimalist synth arpeggios, futuristic, instrumental only, 5 seconds",
        "music_style": "Electronic Cinematic",
    },
    {
        "id": "scene_6_cosmos", "element": "COSMOS",
        "image": AVATAR_DIR / "scene_6_cosmos.png",
        "video_prompt": (
            "Cinematic 9:16 portrait. Face and upward gaze locked — preserve exact angle from reference. "
            "Milky Way rotates slowly in the infinite starfield above. "
            "Nebula colors shift softly — purple, blue, gold. Stars twinkle gently. "
            "Arms slightly open, pure awe and peace on face, a full slow smile of completion. "
            "Lips move with wonder: 'We are stardust — remembering what we always were.' "
            "Starlight cinematic grade, cool cosmic tones, slow gentle push from wide to medium close. "
            "Ultra-realistic 1080p. No distortion. Stars only in background."
        ),
        "music_prompt": "Cinematic cosmic orchestral, swelling strings and soft choir, vast transcendent completion, instrumental only, 5 seconds",
        "music_style": "Cinematic Orchestral",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def check_credits():
    """Check KIE balance before starting. Exits immediately if zero.
    Official endpoint: GET https://api.kie.ai/api/v1/chat/credit
    Response: {"code": 200, "msg": "success", "data": <balance>}
    """
    try:
        r = requests.get(CREDIT_URL, headers=AUTH, timeout=10)
        d = r.json()
        balance = d.get("data", 0) or 0
        print(f"  [CREDITS] Balance: {balance}")
        if balance <= 0:
            print("\n" + "!"*70)
            print("  ERROR: Your KIE.ai balance is 0 — cannot generate anything.")
            print("  Top up at: https://kie.ai/pricing")
            print("  Then re-run this script.")
            print("!"*70 + "\n")
            sys.exit(1)
        return balance
    except Exception as e:
        print(f"  [WARN]  Could not check credits ({e}) — continuing anyway")
        return None


def handle_402():
    """Called whenever a 402 is received. Sets global flag and prints clear message."""
    global _credits_exhausted
    _credits_exhausted = True
    print("\n" + "!"*70)
    print("  ERROR 402: Credits exhausted mid-run.")
    print("  Top up at: https://kie.ai/pricing")
    print("  Re-run after topping up — already-uploaded images are reusable.")
    print("!"*70)


def poll(label, fn, timeout=600, interval=10):
    """Poll until done. One line when starting, one line when finished — no per-attempt spam."""
    start, attempt = time.time(), 0
    print(f"  [WAIT]   {label} — polling (max {timeout}s) ...", flush=True)
    while time.time() - start < timeout:
        attempt += 1
        try:
            done, result = fn()
            if done:
                elapsed = int(time.time() - start)
                print(f"  [OK]     {label} — done in {elapsed}s ({attempt} polls)")
                return result
            time.sleep(interval)
        except Exception as e:
            elapsed = int(time.time() - start)
            print(f"  [ERROR]  {label} — {e}  (after {elapsed}s, {attempt} polls)")
            time.sleep(interval)
    elapsed = int(time.time() - start)
    print(f"  [TIMEOUT] {label} — gave up after {elapsed}s ({attempt} polls)")
    return None

def dl(url, path):
    try:
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        kb = path.stat().st_size // 1024
        print(f"  [SAVED]  {path.name}  ({kb} KB)")
        return True
    except Exception as e:
        print(f"  [ERROR]  Download: {e}"); return False


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — UPLOAD IMAGE
# POST https://kieai.redpandaai.co/api/file-stream-upload
# Response: data.downloadUrl
# ═══════════════════════════════════════════════════════════════════════════════
def upload_image(image_path):
    print(f"  [UPLOAD] {image_path.name}")
    try:
        with open(image_path, "rb") as f:
            r = requests.post(
                UPLOAD_URL, headers=AUTH,
                files={"file": (image_path.name, f, "image/png")},
                data={"uploadPath": "elements-of-existence", "fileName": image_path.name},
                timeout=60,
            )
        print(f"           HTTP {r.status_code}")
        resp = r.json()
        print(f"           code={resp.get('code')}  msg={resp.get('msg')}")
        if resp.get("code") == 200:
            d = resp.get("data") or {}
            url = d.get("downloadUrl") or d.get("fileUrl") or d.get("url")
            if url:
                print(f"           URL: {url}")
                return url
            print(f"  [ERROR]  No URL in data: {json.dumps(d)[:200]}")
        else:
            print(f"  [ERROR]  {json.dumps(resp)[:300]}")
    except Exception as e:
        print(f"  [ERROR]  Upload: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — MUSIC (Suno)
# FIX: callBackUrl is REQUIRED by Suno (422 without it) — pass dummy placeholder
# POST https://api.kie.ai/api/v1/generate
# Poll: GET https://api.kie.ai/api/v1/generate/record-info?taskId=xxx
# Result: data.response[0].audio_url
# ═══════════════════════════════════════════════════════════════════════════════
def generate_music(scene):
    """Generate music via Suno API.
    POST /api/v1/generate  — docs.kie.ai/suno-api/music-generation
    Poll GET /api/v1/generate/record-info?taskId=xxx
    """
    global _credits_exhausted
    if _credits_exhausted:
        return None

    payload = {
        "prompt":       scene["music_prompt"],
        "customMode":   True,
        "style":        scene["music_style"],
        "title":        f"Elements - {scene['element']}",
        "instrumental": True,
        "model":        "V3_5",
        "callBackUrl":  DUMMY_CALLBACK,
    }
    try:
        r = requests.post(MUSIC_URL, headers=JAUTH, json=payload, timeout=30)
        data = r.json()
        print(f"  [MUSIC]  {scene['element']}  HTTP {r.status_code}  code={data.get('code')}")
        if data.get("code") == 402:
            handle_402(); return None
        if data.get("code") != 200:
            print(f"  [ERROR]  Music submit: {json.dumps(data)}")
            return None
        task_id = (data.get("data") or {}).get("taskId")
        print(f"           taskId: {task_id}")
    except Exception as e:
        print(f"  [ERROR]  Music submit exception: {e}"); return None

    def check():
        r = requests.get(MUSIC_POLL, headers=AUTH, params={"taskId": task_id}, timeout=15)
        d = r.json()
        if d.get("code") != 200:
            raise Exception(f"Poll error: code={d.get('code')} msg={d.get('msg')}")
        task = d.get("data") or {}
        flag = task.get("successFlag")
        if flag == 2:
            raise Exception(f"Music generation failed: {task.get('errorMessage','unknown')}")
        if flag == 1:
            tracks = task.get("response") or []
            if isinstance(tracks, list) and tracks:
                url = tracks[0].get("audio_url") or tracks[0].get("audioUrl")
                if url: return True, url
            for k in ("audioUrl", "audio_url", "url"):
                u = task.get(k)
                if u: return True, u
            print(f"  [WARN]  No audio URL found. Response keys: {list(task.keys())}")
            return True, None
        return False, None

    audio_url = poll(f"Music/{scene['element']}", check, timeout=600, interval=10)
    if not audio_url:
        print(f"  [WARN]  Music skipped for {scene['element']} — video will be silent")
        return None
    path = MUSIC_DIR / f"{scene['id']}.mp3"
    return path if dl(audio_url, path) else None

def generate_video(scene, image_url, model=None):
    """Generate video via Wan API.
    POST /api/v1/jobs/createTask  — docs.kie.ai/market/wan/2-2-a14b-image-to-video-turbo
    Poll GET /api/v1/jobs/recordInfo?taskId=xxx
    Key fixes per official docs:
      - wan/2-2-a14b-image-to-video-turbo: resolution="720p", field="image_url" (singular)
      - wan/2-6-image-to-video: resolution="1080p", field="image_urls" (list)
    """
    global _credits_exhausted
    if _credits_exhausted:
        return None

    model = model or VIDEO_MODEL

    # Build the correct input payload based on which model we're using
    if model == VIDEO_MODEL:   # wan/2-2-a14b-image-to-video-turbo
        input_params = {
            "prompt":               scene["video_prompt"],
            "image_url":            image_url,   # singular — required by this model
            "duration":             "5",
            "resolution":           "720p",       # ONLY valid value for this model
            "enable_prompt_expansion": False,
            "acceleration":         "none",
        }
    else:                       # wan/2-6-image-to-video (fallback)
        input_params = {
            "prompt":     scene["video_prompt"],
            "image_urls": [image_url],            # list — required by this model
            "duration":   "5",
            "resolution": "1080p",
        }

    payload = {"model": model, "callBackUrl": DUMMY_CALLBACK, "input": input_params}

    try:
        r = requests.post(VIDEO_URL, headers=JAUTH, json=payload, timeout=30)
        data = r.json()
        print(f"  [VIDEO]  {scene['element']}  model={model}  HTTP {r.status_code}  code={data.get('code')}")

        if data.get("code") == 402:
            # Both models exhausted — kill remaining scenes
            handle_402(); return None

        if data.get("code") != 200:
            print(f"  [ERROR]  Video submit: {json.dumps(data)}")
            return None

        task_id = (data.get("data") or {}).get("taskId")
        print(f"           taskId: {task_id}")
    except Exception as e:
        print(f"  [ERROR]  Video submit exception: {e}"); return None

    def check():
        r = requests.get(VIDEO_POLL, headers=AUTH, params={"taskId": task_id}, timeout=15)
        d = r.json()
        if d.get("code") != 200:
            raise Exception(f"Poll error: code={d.get('code')} msg={d.get('msg')}")
        task  = d.get("data") or {}
        state = task.get("state", "unknown")
        if state == "fail":
            raise Exception(f"Video failed: {task.get('failMsg', 'unknown reason')}")
        if state == "success":
            rj = task.get("resultJson") or "{}"
            try:
                result = json.loads(rj) if isinstance(rj, str) else rj
            except Exception:
                result = {}
            urls = result.get("resultUrls") or result.get("videoUrls") or []
            if isinstance(urls, list) and urls:
                return True, urls[0]
            for k in ("videoUrl", "resultUrl", "url"):
                u = task.get(k)
                if u: return True, u
            print(f"  [WARN]  No URL in resultJson: {rj[:200]}")
            return True, None
        return False, None

    video_url = poll(f"Video/{scene['element']}", check, timeout=600, interval=12)
    if not video_url: return None
    path = VIDEO_DIR / f"{scene['id']}.mp4"
    return path if dl(video_url, path) else None


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — MERGE with ffmpeg
# ═══════════════════════════════════════════════════════════════════════════════
def merge_all(results):
    print("\n\n[MERGE] Building final_video.mp4\n")

    mixed = []
    for r in results:
        vid = r.get("video")
        mus = r.get("music")
        el  = r["element"]
        if not vid or not vid.exists():
            print(f"  [SKIP]  {el} — no video"); continue

        out = VIDEO_DIR / f"{r['id']}_mixed.mp4"
        if mus and mus.exists():
            print(f"  [MIX]   {el}")
            probe = subprocess.run(
                ["ffprobe","-v","error","-select_streams","a",
                 "-show_entries","stream=codec_type","-of","csv=p=0", str(vid)],
                capture_output=True, text=True)
            has_audio = "audio" in probe.stdout

            if has_audio:
                cmd = ["ffmpeg","-y","-i",str(vid),"-i",str(mus),
                       "-filter_complex",
                       "[0:a]volume=1.0[va];[1:a]volume=0.20,atrim=0:5,asetpts=PTS-STARTPTS[ma];"
                       "[va][ma]amix=inputs=2:duration=first[out]",
                       "-map","0:v","-map","[out]",
                       "-c:v","copy","-c:a","aac","-t","5", str(out)]
            else:
                cmd = ["ffmpeg","-y","-i",str(vid),"-i",str(mus),
                       "-filter_complex",
                       "[1:a]volume=0.50,atrim=0:5,asetpts=PTS-STARTPTS[ma]",
                       "-map","0:v","-map","[ma]",
                       "-c:v","copy","-c:a","aac","-t","5", str(out)]

            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"  [WARN]  Mix failed, using raw: {res.stderr[-150:]}")
                out = vid
            else:
                print(f"         → {out.name}")
        else:
            print(f"  [NOTE]  {el} — no music, raw clip")
            out = vid
        mixed.append(out)

    if not mixed:
        print("  [ERROR] No clips to merge!"); return False

    # Normalize all to same spec
    print(f"\n  [NORM]  Re-encoding {len(mixed)} clips...")
    normed = []
    for i, clip in enumerate(mixed):
        out = VIDEO_DIR / f"norm_{i}.mp4"
        cmd = ["ffmpeg","-y","-i",str(clip),
               "-vf","scale=608:1080:force_original_aspect_ratio=decrease,"
                     "pad=608:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
               "-r","24","-c:v","libx264","-preset","fast","-crf","20",
               "-c:a","aac","-ar","44100","-ac","2","-t","5", str(out)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        normed.append(out if res.returncode == 0 else clip)

    # Concat
    lst = VIDEO_DIR / "concat.txt"
    with open(lst,"w") as f:
        [f.write(f"file '{c.resolve()}'\n") for c in normed]

    print(f"  [CONCAT] {len(normed)} clips → {FINAL_VIDEO}")
    res = subprocess.run(
        ["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(FINAL_VIDEO)],
        capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  [ERROR] {res.stderr[-300:]}"); return False

    mb = FINAL_VIDEO.stat().st_size / (1024*1024)
    print(f"  [DONE]   {FINAL_VIDEO}  ({mb:.1f} MB)")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    global _credits_exhausted
    print("\n" + "="*70)
    print("  ELEMENTS OF EXISTENCE — Full Video Pipeline")
    print(f"  Video model: {VIDEO_MODEL}")
    print("="*70)

    # Verify all avatar images exist
    for s in SCENES:
        if not s["image"].exists():
            print(f"  ERROR: Missing {s['image']}"); sys.exit(1)
    print(f"  [OK]  All 6 avatars found in {AVATAR_DIR}/")

    # Check credits BEFORE doing anything expensive
    # Official docs: GET https://api.kie.ai/api/v1/chat/credit
    check_credits()

    results = []
    for i, scene in enumerate(SCENES, 1):
        print(f"\n" + "─"*70)
        print(f"  SCENE {i}/6 — {scene['element']}")
        print("─"*70)

        # If 402 was received in any earlier scene, skip all remaining
        if _credits_exhausted:
            print(f"  [SKIP]  Credits exhausted — skipping {scene['element']}")
            results.append({"id": scene["id"], "element": scene["element"],
                            "video": None, "music": None, "status": "skipped_no_credits"})
            continue

        image_url = upload_image(scene["image"])
        if not image_url:
            results.append({"id": scene["id"], "element": scene["element"],
                            "video": None, "music": None, "status": "upload_failed"})
            continue

        music_path = generate_music(scene)
        video_path = generate_video(scene, image_url)

        results.append({
            "id":      scene["id"],
            "element": scene["element"],
            "video":   video_path,
            "music":   music_path,
            "status":  "success" if video_path else "video_failed",
        })

    ok = merge_all(results) if any(r.get("video") for r in results) else False

    print("\n" + "="*70 + "\n  SUMMARY\n" + "─"*70)
    for r in results:
        v = "OK  " if r.get("video") else "FAIL"
        m = "OK  " if r.get("music") else "none"
        print(f"  {r['element']:<12}  video={v}  music={m}  [{r['status']}]")
    print("─"*70)
    if ok:
        mb = FINAL_VIDEO.stat().st_size/(1024*1024) if FINAL_VIDEO.exists() else 0
        print(f"  FINAL:  {FINAL_VIDEO}  ({mb:.1f} MB)")
    else:
        print(f"  Clips saved to: ./{VIDEO_DIR}/")
    if _credits_exhausted:
        print("\n  ACTION: Top up at https://kie.ai/pricing then re-run.")
    print("="*70)

    with open("pipeline_manifest.json", "w") as f:
        json.dump([{"element": r["element"], "status": r["status"],
                    "video": str(r["video"]) if r.get("video") else None,
                    "music": str(r["music"]) if r.get("music") else None}
                   for r in results], f, indent=2)
    print("  Manifest: pipeline_manifest.json\n")


if __name__ == "__main__":
    main()
