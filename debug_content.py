#!/usr/bin/env python3
"""
Debug script to test the exact JSON parsing that happens in gemini_structured_plan
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def debug_content_parsing():
    """
    Test the exact parsing logic from gemini_structured_plan function
    """
    
    # Get API key
    KIE_KEY = os.getenv("KIEAI_API_KEY")
    if not KIE_KEY:
        print("❌ KIEAI_API_KEY not found in .env")
        return
    
    # Headers and URL
    JAUTH = {"Authorization": f"Bearer {KIE_KEY}", "Content-Type": "application/json"}
    GEMINI_CHAT_URL = "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions"
    
    # Schema
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
    
    user_msg = "Theme:\nCreate a mystical fantasy adventure"
    
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
    
    print("🔍 Making API call with actual prompt...")
    
    try:
        response = requests.post(GEMINI_CHAT_URL, headers=JAUTH, json=payload, timeout=240)
        print(f"✅ HTTP Status: {response.status_code}")
        
        # Parse response (same as original code)
        data = response.json()
        print(f"📊 Response keys: {list(data.keys())}")
        
        if "choices" not in data:
            print(f"❌ No 'choices' in response: {json.dumps(data, indent=2)}")
            return
            
        content = data["choices"][0]["message"]["content"]
        print(f"📄 Raw content from API:")
        print(f"Type: {type(content)}")
        print(f"Length: {len(content)} characters")
        print(f"Content: {repr(content)}")
        print()
        
        # This is where the original code fails - trying to parse content as JSON
        print("🔍 ATTEMPTING TO PARSE CONTENT AS JSON:")
        print("=" * 50)
        
        # Same logic as original code
        txt = content.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.lower().startswith("json"):
                txt = txt[4:].strip()
        
        print(f"Text to parse (after processing): {repr(txt)}")
        print()
        
        try:
            plan = json.loads(txt)
            print("✅ Content parsed as JSON successfully!")
            print(f"Plan keys: {list(plan.keys()) if isinstance(plan, dict) else 'Not a dict'}")
            
            # Check if it's valid structure
            if "scenes" not in plan or len(plan.get("scenes", [])) != 6:
                print("❌ Plan structure is invalid - missing scenes or wrong count")
            else:
                print("✅ Plan structure is valid!")
                
        except json.JSONDecodeError as e:
            print(f"❌ FOUND THE ISSUE! JSON parsing of content failed:")
            print(f"Error: {e}")
            print(f"Error position: line {e.lineno}, column {e.colno}")
            
            # Show the problematic part
            if e.pos < len(txt):
                problem_char = txt[e.pos]
                print(f"Problem character: '{problem_char}' (ord={ord(problem_char)})")
                
                start = max(0, e.pos - 20)
                end = min(len(txt), e.pos + 20)
                context = txt[start:end]
                print(f"Context: {repr(context)}")
                
            print()
            print("🔍 DIAGNOSIS:")
            print("The API is returning valid JSON in OpenAI format, but the 'content' field")
            print("contains plain text instead of the requested structured JSON schema.")
            print("This means the model is not following the json_schema format requirement.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_content_parsing()