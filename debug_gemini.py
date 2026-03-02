#!/usr/bin/env python3
"""
Debug script to identify the exact issue with Gemini API response
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def debug_gemini_response():
    """
    Replicate the exact Gemini API call and analyze the response
    """
    
    # Get API key
    KIE_KEY = os.getenv("KIEAI_API_KEY")
    if not KIE_KEY:
        print("❌ KIEAI_API_KEY not found in .env")
        return
    
    # Headers (same as in final.py)
    JAUTH = {"Authorization": f"Bearer {KIE_KEY}", "Content-Type": "application/json"}
    
    # URL (same as in final.py)
    GEMINI_CHAT_URL = "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions"
    
    # Schema (same as in final.py)
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "avatar_identity": {"type": "string"},
            "scenes": {
                "type": "array",
                "minItems": 6,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "element": {"type": "string"},
                        "avatar_prompt": {"type": "string"},
                        "dialogue": {"type": "string"},
                        "video_prompt": {"type": "string"},
                    },
                    "required": ["id", "element", "avatar_prompt", "dialogue", "video_prompt"],
                },
            },
        },
        "required": ["title", "avatar_identity", "scenes"],
    }
    
    system_msg = (
        "Return STRICT JSON that matches the provided json_schema.\n"
        "Generate exactly 6 scenes in this order: AIR, WATER, EARTH, FIRE, SCIENCE, COSMOS.\n"
        "Keep the SAME avatar identity across all 6 avatar prompts.\n"
        "Avatar prompts: photorealistic, cinematic lighting, 9:16 portrait.\n"
        "Video prompts must explicitly request:\n"
        "- natural spoken dialogue (use the dialogue)\n"
        "- subtle cinematic background music UNDER the voice\n"
        "- professional audio mix\n"
        "Output ONLY JSON."
    )
    
    user_msg = "Theme:\nTest prompt for debugging"
    
    # Payload (same as in final.py)
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_msg}]},
            {"role": "user", "content": [{"type": "text", "text": user_msg}]},
        ],
        "include_thoughts": False,
        "reasoning_effort": "low",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "elements_of_existence_plan",
                "schema": schema
            }
        },
    }
    
    print("🔍 Making API call to Gemini...")
    print(f"URL: {GEMINI_CHAT_URL}")
    print(f"Headers: {JAUTH}")
    print(f"Payload size: {len(json.dumps(payload))} bytes")
    print()
    
    try:
        # Make the request (same as in final.py)
        response = requests.post(GEMINI_CHAT_URL, headers=JAUTH, json=payload, timeout=240)
        
        print(f"✅ HTTP Status: {response.status_code}")
        print(f"📊 Response headers: {dict(response.headers)}")
        print(f"📏 Response length: {len(response.content)} bytes")
        print()
        
        # Get raw response content
        raw_content = response.content
        text_content = response.text
        
        print("🔬 RAW RESPONSE ANALYSIS:")
        print("=" * 50)
        
        # Show first 200 bytes as hex
        print(f"First 200 bytes (hex): {raw_content[:200].hex()}")
        print()
        
        # Show first 200 characters as text with special chars visible
        print("First 200 characters (repr):")
        print(repr(text_content[:200]))
        print()
        
        # Character-by-character analysis of first 20 characters
        print("First 20 characters analysis:")
        for i, char in enumerate(text_content[:20]):
            print(f"  Pos {i}: '{char}' (ord={ord(char)}, hex={hex(ord(char))})")
        print()
        
        # Try to parse as JSON and see exactly where it fails
        print("🔍 JSON PARSING TEST:")
        print("=" * 30)
        try:
            parsed = response.json()
            print("✅ JSON parsing successful!")
            print(f"Parsed type: {type(parsed)}")
            print(f"Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'Not a dict'}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed!")
            print(f"Error: {e}")
            print(f"Error position: line {e.lineno}, column {e.colno}")
            print(f"Error at character index: {e.pos}")
            
            if e.pos < len(text_content):
                problem_char = text_content[e.pos]
                print(f"Problem character: '{problem_char}' (ord={ord(problem_char)}, hex={hex(ord(problem_char))})")
                
                # Show context around the problem
                start = max(0, e.pos - 10)
                end = min(len(text_content), e.pos + 10)
                context = text_content[start:end]
                print(f"Context around error: {repr(context)}")
        
        print()
        print("📄 FULL RESPONSE CONTENT:")
        print("=" * 40)
        print(text_content)
        print("=" * 40)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    debug_gemini_response()