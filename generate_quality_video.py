#!/usr/bin/env python3
"""
ELEMENTS OF EXISTENCE — VEO 3.1 QUALITY ONLY PIPELINE
======================================================
• Model: veo3 (Quality)
• Native audio generation (dialogue + cinematic background music)
• No Suno
• No Wan
• No external tools except ffmpeg merge
"""

import os, sys, time, json, subprocess, random, requests
from pathlib import Path
from dotenv import load_dotenv

# ── Load API key ─────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("KIEAI_API_KEY")
if not API_KEY:
    print("ERROR: KIEAI_API_KEY not found in .env")
    sys.exit(1)

AUTH  = {"Authorization": f"Bearer {API_KEY}"}
JAUTH = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ── Endpoints ────────────────────────────────────────
UPLOAD_URL = "https://kieai.redpandaai.co/api/file-stream-upload"
VEO_CREATE = "https://api.kie.ai/api/v1/veo/generate"
VEO_POLL   = "https://api.kie.ai/api/v1/veo/record-info"

VIDEO_DIR   = Path("video_outputs"); VIDEO_DIR.mkdir(exist_ok=True)
AVATAR_DIR  = Path("avatar_outputs")
FINAL_VIDEO = Path("final_video.mp4")

MODEL = "veo3"        # Veo 3.1 Quality
ASPECT = "9:16"

# ── SCENES ───────────────────────────────────────────

SCENES = [
    ("scene_1_air.png", "Every breath you take is the universe breathing through you."),
    ("scene_2_water.png", "Flow like water — adapt, persist, and carve your own path."),
    ("scene_3_earth.png", "You are rooted in something ancient — trust your ground."),
    ("scene_4_fire.png", "Ignite your purpose — fire doesn't apologize for its light."),
    ("scene_5_science.png", "Question everything. The answer is always the next question."),
    ("scene_6_cosmos.png", "We are stardust — remembering what we always were.")
]

# ── Upload Image ─────────────────────────────────────

def upload_image(path):
    with open(path, "rb") as f:
        r = requests.post(
            UPLOAD_URL,
            headers=AUTH,
            files={"file": (path.name, f, "image/png")},
            data={"uploadPath": "veo-elements", "fileName": path.name},
            timeout=60,
        )
    data = r.json()
    if data.get("code") == 200:
        return data["data"]["downloadUrl"]
    print("Upload failed:", data)
    return None

# ── Generate Video (VEO ONLY) ───────────────────────

def generate_video(prompt, image_url, index):
    seed = random.randint(10000, 99999)

    payload = {
        "prompt": prompt,
        "imageUrls": [image_url],
        "model": MODEL,
        "aspect_ratio": ASPECT,
        "generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO",
        "enableTranslation": True,
        "seeds": seed
    }

    r = requests.post(VEO_CREATE, headers=JAUTH, json=payload, timeout=60)
    data = r.json()

    if data.get("code") != 200:
        print("Video submit failed:", data)
        return None

    task_id = data["data"]["taskId"]
    print("  → Task:", task_id)

    # Poll
    while True:
        time.sleep(12)
        r = requests.get(VEO_POLL, headers=AUTH, params={"taskId": task_id})
        d = r.json()

        if d.get("code") != 200:
            continue

        info = d.get("data", {})
        flag = info.get("successFlag")

        if flag == 1:
            url = info["response"]["resultUrls"][0]
            break
        if flag in (2, 3):
            print("Generation failed.")
            return None

    # Download
    output_path = VIDEO_DIR / f"clip_{index}.mp4"
    vid = requests.get(url, timeout=180)
    with open(output_path, "wb") as f:
        f.write(vid.content)

    print("  → Saved:", output_path)
    return output_path

# ── Merge Videos ─────────────────────────────────────

def merge_clips(clips):
    list_file = VIDEO_DIR / "concat.txt"
    with open(list_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip.resolve()}'\n")

    subprocess.run([
        "ffmpeg","-y",
        "-f","concat","-safe","0",
        "-i",str(list_file),
        "-c","copy",
        str(FINAL_VIDEO)
    ])

    print("\nFINAL VIDEO:", FINAL_VIDEO)

# ── MAIN ─────────────────────────────────────────────

def main():
    print("\n=== VEO 3.1 QUALITY VIDEO GENERATION ===\n")

    clips = []

    for i, (img_name, text) in enumerate(SCENES, 1):
        img_path = AVATAR_DIR / img_name
        if not img_path.exists():
            print("Missing:", img_path)
            sys.exit(1)

        print(f"\nScene {i}: {img_name}")

        image_url = upload_image(img_path)
        if not image_url:
            continue

        cinematic_prompt = f"""
Ultra-realistic cinematic portrait video.
Keep the exact same face and identity from the reference image.
The head and face remain structurally consistent.

The character speaks clearly and naturally:
"{text}"

Include subtle cinematic background music,
soft atmospheric scoring under the dialogue,
professionally mixed audio.

Natural lip sync, expressive eyes, shallow depth of field,
beautiful lighting, dramatic cinematic camera movement,
high production quality film look, 4K realism.
"""

        clip = generate_video(cinematic_prompt, image_url, i)
        if clip:
            clips.append(clip)

    if clips:
        merge_clips(clips)

if __name__ == "__main__":
    main()