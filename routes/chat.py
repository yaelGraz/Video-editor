"""
AI Editor Chat route — multi-intent styling commands via Groq LLM.
"""
import json
import re

from fastapi import APIRouter, Form, HTTPException
from groq import Groq

from services.audio_service import list_music_library
from utils.config import GROQ_API_KEY, MUSIC_DIR

router = APIRouter()


@router.post("/chat")
async def ai_editor_chat(
    message: str = Form(...),
    history: str = Form("[]"),
    currentContext: str = Form("{}"),
    has_video: str = Form("false"),
):
    """
    AI chat endpoint for video editing styling commands.
    Multi-intent: extracts all commands from a single sentence.
    """
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key not configured")

    try:
        history_list = json.loads(history) if history else []
        context = json.loads(currentContext) if currentContext else {}

        # Regex pre-extraction
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+(?:[?&]\S*)?)'
        extracted_youtube_urls = re.findall(youtube_regex, message)

        hex_color_regex = r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b'
        extracted_colors = re.findall(hex_color_regex, message)

        font_size_regex = r'(?:גודל|size)\s*[=:]?\s*(\d{1,3})'
        extracted_sizes = re.findall(font_size_regex, message, re.IGNORECASE)

        volume_regex = r'(?:ווליום|volume|עוצמ[הת])\s*[=:]?\s*(\d{1,3})\s*%?'
        extracted_volumes = re.findall(volume_regex, message, re.IGNORECASE)

        pre_extracted_hint = ""
        if extracted_youtube_urls:
            pre_extracted_hint += f"\n[המערכת זיהתה לינק יוטיוב: {extracted_youtube_urls[0]}]"
        if extracted_colors:
            pre_extracted_hint += f"\n[המערכת זיהתה צבע: {extracted_colors[0]}]"
        if extracted_sizes:
            pre_extracted_hint += f"\n[המערכת זיהתה גודל: {extracted_sizes[0]}]"
        if extracted_volumes:
            pre_extracted_hint += f"\n[המערכת זיהתה ווליום: {extracted_volumes[0]}%]"

        music_files = list_music_library(str(MUSIC_DIR))
        music_list_str = ", ".join([f['name'] for f in music_files[:10]]) if music_files else "אין קבצי מוזיקה"

        current_font = context.get("font", "Assistant")
        current_color = context.get("fontColor", "#FFFFFF")
        current_size = context.get("fontSize", 48)
        current_music_vol = context.get("musicVolume", 0.3)
        music_vol_percent = int(current_music_vol * 100) if current_music_vol <= 1 else int(current_music_vol)
        current_ducking = context.get("ducking", True)
        current_subtitles = context.get("subtitlesEnabled", context.get("subtitles", True))
        has_video_bool = has_video.lower() == "true"

        system_prompt = f"""אתה עוזר AI מקצועי לעריכת וידאו בעברית. תפקידך לסייע למשתמש לעצב ולערוך את הסרטון שלו בצורה מדויקת.

=== מצב נוכחי של הפרויקט (Context) ===
- וידאו הועלה: {"כן ✓" if has_video_bool else "לא - המשתמש צריך להעלות וידאו קודם"}
- כתוביות מופעלות: {"כן ✓" if current_subtitles else "לא"}
- פונט נוכחי: {current_font} | צבע: {current_color} | גודל: {current_size}px
- עוצמת מוזיקה: {music_vol_percent}%
- דאקינג (הנמכת מוזיקה בזמן דיבור): {"מופעל ✓" if current_ducking else "כבוי"}

=== ספריית מוזיקה זמינה (קבצים אמיתיים בלבד!) ===
{music_list_str}

=== פרוטוקול ניהול שיחה על מוזיקה (חובה!) ===
1. אם המשתמש מבקש "מוזיקה" או מציין סגנון: אל תבחר קובץ עדיין. שאל אם רוצה לינק יוטיוב, העלאת קובץ, או בחירה מהספרייה.
2. רק אחרי אישור: בחר קובץ מדויק מהרשימה, או החזר youtubeUrl.

=== הגבלות (קריטי!) ===
- איסור המצאה: השתמש רק בשמות קבצים מהרשימה לעיל.
- איסור עריכה אוטומטית: אל תחזיר action: process_video אלא אם המשתמש ביקש במפורש.
{pre_extracted_hint}

=== פורמט תשובה (JSON בלבד) ===
{{
  "answer": "התשובה שלך בעברית",
  "commands": [
    {{
      "font": "string או null",
      "fontColor": "#RRGGBB או null",
      "fontSize": "number או null",
      "musicVolume": "number (0-100) או null",
      "musicFile": "filename.mp3 או null",
      "youtubeUrl": "URL מלא או null",
      "subtitlesEnabled": "true/false או null",
      "ducking": "true/false או null",
      "action": "process_video (רק באישור מפורש!) או null"
    }}
  ]
}}

החזר רק JSON תקין, ללא טקסט נוסף.
"""

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history_list[-8:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": message})

        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=messages, temperature=0.7, max_tokens=500,
        )

        ai_response = response.choices[0].message.content.strip()

        try:
            cleaned_response = ai_response
            if cleaned_response.startswith("```"):
                parts = cleaned_response.split("```")
                if len(parts) >= 2:
                    cleaned_response = parts[1]
                    if cleaned_response.startswith("json"):
                        cleaned_response = cleaned_response[4:]
                    cleaned_response = cleaned_response.strip()

            result = json.loads(cleaned_response)
            answer = result.get("answer", result.get("message", ai_response))

            commands_raw = result.get("commands", None)
            if commands_raw is None:
                single_cmd = result.get("command", result.get("style_updates", {}))
                commands_raw = [single_cmd] if single_cmd else [{}]

            if not isinstance(commands_raw, list):
                commands_raw = [commands_raw]

            # Normalize commands
            commands = []
            for cmd in commands_raw:
                if not isinstance(cmd, dict):
                    continue
                cmd = {k: v for k, v in cmd.items() if v is not None and v != "null" and v != ""}
                if "musicVolume" in cmd:
                    vol = cmd["musicVolume"]
                    if isinstance(vol, (int, float)) and vol > 1:
                        cmd["musicVolume"] = vol / 100.0
                if cmd:
                    commands.append(cmd)

            # Post-processing: merge regex-extracted data LLM missed
            has_yt = any(c.get("youtubeUrl") for c in commands)
            if extracted_youtube_urls and not has_yt:
                if commands:
                    commands[0]["youtubeUrl"] = extracted_youtube_urls[0]
                else:
                    commands.append({"youtubeUrl": extracted_youtube_urls[0]})

            has_color = any(c.get("fontColor") for c in commands)
            if extracted_colors and not has_color:
                target = commands[0] if commands else {}
                target["fontColor"] = extracted_colors[0]
                if not commands:
                    commands.append(target)

            has_size = any(c.get("fontSize") for c in commands)
            if extracted_sizes and not has_size:
                target = commands[0] if commands else {}
                target["fontSize"] = int(extracted_sizes[0])
                if not commands:
                    commands.append(target)

            has_vol = any(c.get("musicVolume") is not None for c in commands)
            if extracted_volumes and not has_vol:
                target = commands[0] if commands else {}
                vol_val = int(extracted_volumes[0])
                target["musicVolume"] = vol_val / 100.0 if vol_val > 1 else vol_val
                if not commands:
                    commands.append(target)

            return {"answer": answer, "commands": commands}

        except json.JSONDecodeError:
            # Fallback: build commands from regex extractions
            fallback_cmd = {}
            if extracted_youtube_urls:
                fallback_cmd["youtubeUrl"] = extracted_youtube_urls[0]
            if extracted_colors:
                fallback_cmd["fontColor"] = extracted_colors[0]
            if extracted_sizes:
                fallback_cmd["fontSize"] = int(extracted_sizes[0])
            if extracted_volumes:
                vol_val = int(extracted_volumes[0])
                fallback_cmd["musicVolume"] = vol_val / 100.0 if vol_val > 1 else vol_val

            return {
                "answer": ai_response,
                "commands": [fallback_cmd] if fallback_cmd else [],
            }

    except Exception as e:
        print(f"[ERROR] Chat failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
