#!/usr/bin/env python3
"""
COMPREHENSIVE SOLUTION: Multiple Approaches to Get Structured JSON from Gemini API

Based on official OpenAI Structured Outputs documentation and testing with KIE API.
"""

import os
import json
import requests
import re
from dotenv import load_dotenv

load_dotenv()

def create_proper_json_schema():
    """Create a proper JSON schema following OpenAI structured output requirements"""
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the video series"
            },
            "avatar_identity": {
                "type": "string", 
                "description": "Consistent identity description for the avatar across all scenes"
            },
            "scenes": {
                "type": "array",
                "minItems": 6,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Scene identifier"
                        },
                        "element": {
                            "type": "string",
                            "enum": ["AIR", "WATER", "EARTH", "FIRE", "SCIENCE", "COSMOS"]
                        },
                        "avatar_prompt": {
                            "type": "string",
                            "description": "Image generation prompt for avatar"
                        },
                        "dialogue": {
                            "type": "string",
                            "description": "Spoken dialogue for the scene"
                        },
                        "video_prompt": {
                            "type": "string",
                            "description": "Video generation prompt"
                        }
                    },
                    "required": ["id", "element", "avatar_prompt", "dialogue", "video_prompt"],
                    "additionalProperties": false
                }
            }
        },
        "required": ["title", "avatar_identity", "scenes"],
        "additionalProperties": false
    }

def approach_1_strict_json_schema(user_prompt: str):
    """
    APPROACH 1: Use proper OpenAI-style structured output with strict schema
    """
    print("🧪 APPROACH 1: Strict JSON Schema with OpenAI Format")
    print("=" * 60)
    
    KIE_KEY = os.getenv("KIEAI_API_KEY")
    if not KIE_KEY:
        print("❌ KIEAI_API_KEY not found")
        return None
        
    headers = {
        "Authorization": f"Bearer {KIE_KEY}",
        "Content-Type": "application/json"
    }
    
    schema = create_proper_json_schema()
    
    # Strict system message based on OpenAI best practices
    system_msg = (
        "You are a JSON generator. You MUST return ONLY valid JSON that strictly follows the provided schema.\n"
        "Generate exactly 6 scenes in this order: AIR, WATER, EARTH, FIRE, SCIENCE, COSMOS.\n"
        "Each scene must have the same avatar identity but different prompts and dialogue.\n"
        "Avatar prompts: photorealistic, cinematic lighting, 9:16 portrait format.\n"
        "Video prompts must request natural spoken dialogue and subtle background music.\n\n"
        "CRITICAL: Return ONLY the JSON object. No explanation, no markdown, no code blocks."
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_msg}]},
            {"role": "user", "content": [{"type": "text", "text": f"Theme: {user_prompt}"}]}
        ],
        "include_thoughts": False,
        "reasoning_effort": "low",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "video_plan_schema",
                "strict": true,
                "schema": schema
            }
        }
    }
    
    try:
        response = requests.post(
            "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=240
        )
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print("Raw content:", repr(content[:200]) + "...")
            
            try:
                result = json.loads(content)
                print("✅ SUCCESS: Valid JSON returned!")
                return result
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing failed: {e}")
                return None
                
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def approach_2_json_mode_with_parsing(user_prompt: str):
    """
    APPROACH 2: Use JSON mode and robust parsing
    """
    print("\n🧪 APPROACH 2: JSON Mode with Robust Parsing")
    print("=" * 60)
    
    KIE_KEY = os.getenv("KIEAI_API_KEY")
    if not KIE_KEY:
        print("❌ KIEAI_API_KEY not found")
        return None
        
    headers = {
        "Authorization": f"Bearer {KIE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Explicit JSON-only system message
    system_msg = (
        "You are a JSON generator that creates video planning data.\n"
        "You MUST respond with ONLY a valid JSON object in this exact format:\n\n"
        '{"title": "string", "avatar_identity": "string", "scenes": [array of 6 scene objects]}\n\n'
        "Each scene object must have: id, element, avatar_prompt, dialogue, video_prompt\n"
        "Elements must be exactly: AIR, WATER, EARTH, FIRE, SCIENCE, COSMOS\n"
        "Start your response with { and end with }\n"
        "DO NOT include any text before or after the JSON."
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_msg}]},
            {"role": "user", "content": [{"type": "text", "text": f"Create a 6-scene video plan for theme: {user_prompt}"}]}
        ],
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(
            "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=240
        )
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print("Raw content:", repr(content[:200]) + "...")
            
            # Try to extract JSON from the content
            result = extract_json_from_text(content)
            if result:
                print("✅ SUCCESS: JSON extracted successfully!")
                return result
            else:
                print("❌ Failed to extract valid JSON")
                return None
                
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def approach_3_gemini_pro_with_examples(user_prompt: str):
    """
    APPROACH 3: Try Gemini Pro with explicit examples
    """
    print("\n🧪 APPROACH 3: Gemini Pro with Examples")
    print("=" * 60)
    
    KIE_KEY = os.getenv("KIEAI_API_KEY")
    if not KIE_KEY:
        print("❌ KIEAI_API_KEY not found")
        return None
        
    headers = {
        "Authorization": f"Bearer {KIE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Include a complete example in the prompt
    system_msg = '''You must return ONLY a JSON object following this EXACT structure:

{
  "title": "Sample Video Series",
  "avatar_identity": "A wise mystical sage with flowing robes and glowing eyes",
  "scenes": [
    {
      "id": "scene_1_air",
      "element": "AIR", 
      "avatar_prompt": "A wise mystical sage with flowing robes and glowing eyes, standing in clouds, photorealistic, cinematic lighting, 9:16 portrait",
      "dialogue": "Welcome to the realm of air, where thoughts take flight",
      "video_prompt": "Mystical clouds swirling, natural spoken dialogue, subtle cinematic background music"
    }
  ]
}

Generate exactly 6 scenes for elements: AIR, WATER, EARTH, FIRE, SCIENCE, COSMOS.
Return ONLY the JSON. No other text.'''
    
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_msg}]},
            {"role": "user", "content": [{"type": "text", "text": f"Theme: {user_prompt}"}]}
        ]
    }
    
    try:
        response = requests.post(
            "https://api.kie.ai/gemini-2.5-pro/v1/chat/completions",  # Try Pro instead of Flash
            headers=headers,
            json=payload,
            timeout=240
        )
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print("Raw content:", repr(content[:200]) + "...")
            
            result = extract_json_from_text(content)
            if result:
                print("✅ SUCCESS: JSON extracted successfully!")
                return result
            else:
                print("❌ Failed to extract valid JSON")
                return None
                
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def extract_json_from_text(text: str):
    """Extract JSON object from text that might contain other content"""
    
    # Try direct JSON parsing first
    try:
        return json.loads(text.strip())
    except:
        pass
    
    # Remove code fences if present
    if "```" in text:
        # Find content between code fences
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
    
    # Try to find JSON object in the text
    json_patterns = [
        r'\{[^{}]*\{[^{}]*\{[^{}]*\}[^{}]*\}[^{}]*\}',  # Nested objects
        r'\{.*?\}',  # Simple object
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match)
                if isinstance(result, dict) and "scenes" in result:
                    return result
            except:
                continue
    
    return None

def validate_plan_structure(plan):
    """Validate that the plan has the correct structure"""
    if not isinstance(plan, dict):
        return False, "Plan is not a dictionary"
    
    required_keys = ["title", "avatar_identity", "scenes"]
    for key in required_keys:
        if key not in plan:
            return False, f"Missing required key: {key}"
    
    scenes = plan.get("scenes", [])
    if len(scenes) != 6:
        return False, f"Expected 6 scenes, got {len(scenes)}"
    
    required_elements = {"AIR", "WATER", "EARTH", "FIRE", "SCIENCE", "COSMOS"}
    found_elements = set()
    
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            return False, f"Scene {i} is not a dictionary"
        
        scene_keys = ["id", "element", "avatar_prompt", "dialogue", "video_prompt"]
        for key in scene_keys:
            if key not in scene:
                return False, f"Scene {i} missing key: {key}"
        
        element = scene.get("element")
        if element not in required_elements:
            return False, f"Scene {i} has invalid element: {element}"
        
        found_elements.add(element)
    
    if found_elements != required_elements:
        missing = required_elements - found_elements
        return False, f"Missing elements: {missing}"
    
    return True, "Plan structure is valid"

def approach_4_aggressive_json_forcing(user_prompt: str):
    """
    APPROACH 4: Aggressive JSON forcing with minimal conversation
    """
    print("\n🧪 APPROACH 4: Aggressive JSON Forcing")
    print("=" * 60)
    
    KIE_KEY = os.getenv("KIEAI_API_KEY")
    if not KIE_KEY:
        print("❌ KIEAI_API_KEY not found")
        return None
        
    headers = {
        "Authorization": f"Bearer {KIE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Ultra-strict prompt that should force JSON
    system_msg = '''RESPOND ONLY WITH VALID JSON. NO OTHER TEXT ALLOWED.

OUTPUT STRUCTURE:
{
  "title": "string",
  "avatar_identity": "string describing avatar appearance",
  "scenes": [
    {"id": "scene_1_air", "element": "AIR", "avatar_prompt": "avatar description + photorealistic, cinematic lighting, 9:16 portrait", "dialogue": "spoken quote", "video_prompt": "video scene description with spoken dialogue and background music"},
    {"id": "scene_2_water", "element": "WATER", "avatar_prompt": "same avatar + water environment + photorealistic, cinematic lighting, 9:16 portrait", "dialogue": "spoken quote", "video_prompt": "video scene description with spoken dialogue and background music"},
    {"id": "scene_3_earth", "element": "EARTH", "avatar_prompt": "same avatar + earth environment + photorealistic, cinematic lighting, 9:16 portrait", "dialogue": "spoken quote", "video_prompt": "video scene description with spoken dialogue and background music"},
    {"id": "scene_4_fire", "element": "FIRE", "avatar_prompt": "same avatar + fire environment + photorealistic, cinematic lighting, 9:16 portrait", "dialogue": "spoken quote", "video_prompt": "video scene description with spoken dialogue and background music"},
    {"id": "scene_5_science", "element": "SCIENCE", "avatar_prompt": "same avatar + science environment + photorealistic, cinematic lighting, 9:16 portrait", "dialogue": "spoken quote", "video_prompt": "video scene description with spoken dialogue and background music"},
    {"id": "scene_6_cosmos", "element": "COSMOS", "avatar_prompt": "same avatar + cosmic environment + photorealistic, cinematic lighting, 9:16 portrait", "dialogue": "spoken quote", "video_prompt": "video scene description with spoken dialogue and background music"}
  ]
}

RULES:
- Start response with {
- End response with }
- No markdown formatting
- No explanations
- Same avatar identity in all scenes
- Different environment per element'''
    
    user_msg = f"THEME: {user_prompt}\n\nOUTPUT JSON NOW:"
    
    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system_msg}]},
            {"role": "user", "content": [{"type": "text", "text": user_msg}]}
        ],
        "max_tokens": 2000,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(
            "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=240
        )
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print("Raw content:", repr(content[:300]) + "...")
            
            result = extract_json_from_text(content)
            if result:
                print("✅ SUCCESS: JSON extracted successfully!")
                return result
            else:
                print("❌ Failed to extract valid JSON")
                print("Full content:", content)
                return None
                
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def approach_5_template_filling(user_prompt: str):
    """
    APPROACH 5: Template filling approach - ask model to fill a JSON template
    """
    print("\n🧪 APPROACH 5: JSON Template Filling")
    print("=" * 60)
    
    KIE_KEY = os.getenv("KIEAI_API_KEY")
    if not KIE_KEY:
        print("❌ KIEAI_API_KEY not found")
        return None
        
    headers = {
        "Authorization": f"Bearer {KIE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Give the model a JSON template to fill
    template = '''{
  "title": "[INSERT TITLE HERE]",
  "avatar_identity": "[INSERT AVATAR DESCRIPTION HERE]",
  "scenes": [
    {
      "id": "scene_1_air",
      "element": "AIR",
      "avatar_prompt": "[INSERT AVATAR + AIR ENVIRONMENT + photorealistic, cinematic lighting, 9:16 portrait]",
      "dialogue": "[INSERT AIR-THEMED DIALOGUE]",
      "video_prompt": "[INSERT AIR VIDEO DESCRIPTION with spoken dialogue and background music]"
    },
    {
      "id": "scene_2_water", 
      "element": "WATER",
      "avatar_prompt": "[INSERT SAME AVATAR + WATER ENVIRONMENT + photorealistic, cinematic lighting, 9:16 portrait]",
      "dialogue": "[INSERT WATER-THEMED DIALOGUE]",
      "video_prompt": "[INSERT WATER VIDEO DESCRIPTION with spoken dialogue and background music]"
    },
    {
      "id": "scene_3_earth",
      "element": "EARTH", 
      "avatar_prompt": "[INSERT SAME AVATAR + EARTH ENVIRONMENT + photorealistic, cinematic lighting, 9:16 portrait]",
      "dialogue": "[INSERT EARTH-THEMED DIALOGUE]",
      "video_prompt": "[INSERT EARTH VIDEO DESCRIPTION with spoken dialogue and background music]"
    },
    {
      "id": "scene_4_fire",
      "element": "FIRE",
      "avatar_prompt": "[INSERT SAME AVATAR + FIRE ENVIRONMENT + photorealistic, cinematic lighting, 9:16 portrait]", 
      "dialogue": "[INSERT FIRE-THEMED DIALOGUE]",
      "video_prompt": "[INSERT FIRE VIDEO DESCRIPTION with spoken dialogue and background music]"
    },
    {
      "id": "scene_5_science",
      "element": "SCIENCE",
      "avatar_prompt": "[INSERT SAME AVATAR + SCIENCE ENVIRONMENT + photorealistic, cinematic lighting, 9:16 portrait]",
      "dialogue": "[INSERT SCIENCE-THEMED DIALOGUE]", 
      "video_prompt": "[INSERT SCIENCE VIDEO DESCRIPTION with spoken dialogue and background music]"
    },
    {
      "id": "scene_6_cosmos",
      "element": "COSMOS",
      "avatar_prompt": "[INSERT SAME AVATAR + COSMIC ENVIRONMENT + photorealistic, cinematic lighting, 9:16 portrait]",
      "dialogue": "[INSERT COSMOS-THEMED DIALOGUE]",
      "video_prompt": "[INSERT COSMOS VIDEO DESCRIPTION with spoken dialogue and background music]"
    }
  ]
}'''

    system_msg = f'''Replace all [INSERT ...] placeholders in this JSON template with appropriate content.
Keep the JSON structure exactly as shown. Only replace the placeholder text.
Theme: {user_prompt}

Return the completed JSON template with all placeholders filled:

{template}'''
    
    payload = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": system_msg}]}
        ],
        "max_tokens": 2000,
        "temperature": 0.3
    }
    
    try:
        response = requests.post(
            "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=240
        )
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print("Raw content:", repr(content[:300]) + "...")
            
            result = extract_json_from_text(content)
            if result:
                print("✅ SUCCESS: JSON extracted successfully!")
                return result
            else:
                print("❌ Failed to extract valid JSON")
                return None
                
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None
def test_all_approaches():
    """Test all approaches with a sample prompt"""
    
    test_prompt = "A mystical journey through the elements of existence"
    print(f"Testing all approaches with prompt: '{test_prompt}'")
    print("=" * 80)
    
    approaches = [
        approach_1_strict_json_schema,
        approach_2_json_mode_with_parsing, 
        approach_3_gemini_pro_with_examples,
        approach_4_aggressive_json_forcing,
        approach_5_template_filling
    ]
    
    for i, approach in enumerate(approaches, 1):
        try:
            result = approach(test_prompt)
            
            if result:
                is_valid, message = validate_plan_structure(result)
                if is_valid:
                    print(f"🎉 APPROACH {i} SUCCEEDED!")
                    print("Sample output:")
                    print(json.dumps(result, indent=2)[:500] + "...")
                    return result
                else:
                    print(f"❌ APPROACH {i} returned invalid structure: {message}")
            else:
                print(f"❌ APPROACH {i} failed to return valid JSON")
                
        except Exception as e:
            print(f"❌ APPROACH {i} crashed: {e}")
        
        print("\n" + "-" * 40 + "\n")
    
    print("❌ ALL APPROACHES FAILED")
    return None

if __name__ == "__main__":
    # Test all approaches and find the working one
    successful_result = test_all_approaches()
    
    print("\n" + "=" * 80)
    print("SUMMARY & RECOMMENDATIONS:")
    print("=" * 80)
    
    if successful_result:
        print("✅ Found a working approach! Use the successful method in your final.py")
        print("\n📋 Code to implement in final.py:")
        print("""
# Replace the gemini_structured_plan function with the working approach
# Add the extract_json_from_text helper function  
# Use proper error handling and validation
        """)
    else:
        print("❌ No approach worked. Possible solutions:")
        print("1. Check API key validity")
        print("2. Try different Gemini endpoints") 
        print("3. Use a different LLM service")
        print("4. Implement manual JSON template filling")
    
    print("\n💡 Based on OpenAI documentation, the issue is likely that")
    print("   KIE's Gemini endpoints don't fully support OpenAI-style structured outputs.")