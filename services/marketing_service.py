"""
Marketing Service - Handles marketing kit generation using AI.
"""
import json
import re
from typing import Dict, Optional

from utils.config import GROQ_API_KEY


def clean_json_from_ai_response(text: str) -> str:
    """
    Clean AI response that may contain JSON with extra characters.
    Uses Regex to extract clean JSON from markdown or mixed text.
    """
    if not text:
        return text

    # Remove markdown code blocks
    if "```json" in text:
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1).strip()

    if "```" in text:
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1).strip()

    # Try to find JSON object { ... }
    # Use greedy matching from first { to last }
    json_match = re.search(r'(\{[\s\S]*\})', text)
    if json_match:
        return json_match.group(1).strip()

    return text.strip()


def safe_parse_marketing_json(text: str) -> Optional[Dict]:
    """
    Safely parse JSON from AI response with multiple fallback strategies.
    """
    if not text:
        return None

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Clean and parse
    cleaned = clean_json_from_ai_response(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find JSON boundaries manually
    try:
        if '{' in text:
            start = text.index('{')
            # Find matching closing brace
            depth = 0
            end = start
            for i, char in enumerate(text[start:], start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end > start:
                json_str = text[start:end]
                return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 4: Remove common problematic characters
    try:
        # Remove BOM, null bytes, and other control characters
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        cleaned = clean_json_from_ai_response(cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[WARNING] All JSON parse strategies failed: {e}")
        return None


def generate_marketing_kit(
    transcript_text: str,
    video_duration: float,
    progress_callback=None
) -> Optional[Dict]:
    """
    Use Groq LLM to generate marketing content.
    Returns: titles, post, keywords, hashtags, viral_moments, image_prompt, music_style
    """
    if not transcript_text:
        print("[WARNING] No transcript for marketing kit")
        return None

    if not GROQ_API_KEY:
        print("[ERROR] Groq API key not configured")
        return None

    try:
        from groq import Groq

        if progress_callback:
            progress_callback(22, "יוצר ערכת שיווק...")

        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""אתה מומחה שיווק דיגיטלי. נתח את התמליל הבא של סרטון וצור חומרי שיווק.

תמליל הסרטון:
{transcript_text[:4000]}

אורך הסרטון: {int(video_duration)} שניות

החזר JSON בפורמט הבא בלבד (ללא טקסט נוסף, ללא סימני ```, רק JSON טהור):
{{
    "titles": ["כותרת 1", "כותרת 2", "כותרת 3"],
    "punchline": "המשפט הכי חזק, מסקרן או מרגש מהסרטון - משפט אחד קצר שימשוך צפיות",
    "facebook_post": "פוסט מושך לפייסבוק עם אימוג'ים",
    "keywords": ["מילת מפתח 1", "מילת מפתח 2", "מילת מפתח 3"],
    "hashtags": ["#האשטאג1", "#האשטאג2", "#האשטאג3", "#האשטאג4", "#האשטאג5"],
    "viral_moments": [
        {{"start": 10, "end": 40, "reason": "ציטוט חזק"}},
        {{"start": 60, "end": 90, "reason": "רגע מרגש"}},
        {{"start": 120, "end": 150, "reason": "תובנה חשובה"}}
    ],
    "image_prompt": "English prompt for AI image generation",
    "music_style": "calm"
}}

הנחיות חשובות:
- הכותרות צריכות להיות קליטות ומושכות
- ה-punchline צריך להיות המשפט הכי חזק/מסקרן/מרגש - מקסימום 10 מילים
- הפוסט צריך לעורר עניין ולהזמין לצפייה
- מילות המפתח צריכות להתאים ל-SEO
- viral_moments צריכים להיות רגעים מעניינים בסרטון
- שים לב: אורך הסרטון הוא {int(video_duration)} שניות - אל תבחר רגעים מעבר לאורך הזה!
- music_style יכול להיות: calm, uplifting, dramatic, spiritual
- image_prompt צריך להיות באנגלית ולתאר תמונה מושכת
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )

        if progress_callback:
            progress_callback(30, "מעבד תוצאות...")

        content = response.choices[0].message.content.strip()
        print(f"[DEBUG] Raw AI response length: {len(content)} chars")

        # Use robust JSON parsing
        marketing_data = safe_parse_marketing_json(content)

        if not marketing_data:
            print(f"[ERROR] Failed to parse marketing JSON")
            print(f"[DEBUG] Response content: {content[:500]}")
            return None

        # Validate and fix viral moments
        if 'viral_moments' in marketing_data:
            valid_moments = []
            for moment in marketing_data['viral_moments']:
                start = moment.get('start', 0)
                end = moment.get('end', start + 30)

                # Ensure moments are within video duration
                if start < video_duration:
                    # Clamp end to video duration
                    end = min(end, video_duration)
                    # Ensure minimum duration of 10 seconds
                    if end - start >= 10:
                        valid_moments.append({
                            'start': start,
                            'end': end,
                            'reason': moment.get('reason', 'רגע מעניין')
                        })

            marketing_data['viral_moments'] = valid_moments[:3]  # Max 3 shorts
            print(f"[INFO] Valid viral moments: {len(valid_moments)}")

        print(f"[SUCCESS] Marketing kit generated successfully")
        return marketing_data

    except Exception as e:
        print(f"[ERROR] Marketing kit generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None
