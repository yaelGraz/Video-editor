"""
WhatsApp Chat Service — AI chat + conversation state for WhatsApp via Green API.

Mirrors the /chat endpoint logic (Groq LLM, multi-intent, regex pre-processing)
but adapted for a WhatsApp conversation flow with subtitle review.
"""
import asyncio
import json
import re
import time
import uuid
import random
from pathlib import Path

from utils.config import (
    GROQ_API_KEY,
    INPUTS_DIR,
    OUTPUTS_DIR,
    MUSIC_DIR,
    MUSIC_TEMP_DIR,
    SERVER_BASE_URL,
)
from services.greenapi_service import send_text_message, send_file_by_url, download_media
from services.audio_service import (
    transcribe_with_groq,
    get_random_music,
    list_music_library,
    download_audio_from_url,
)
from services.video_service import (
    get_video_duration,
    get_video_resolution,
    check_video_has_audio,
    merge_final_video,
)
from services.text_service import (
    convert_srt_to_ass,
    fix_subtitles_with_ai,
    parse_srt_file,
    write_srt_from_entries,
    extract_text_from_file,
)
from services.font_service import ensure_font_available
from services.marketing_service import generate_marketing_kit

# ============================================================================
# Conversation State (in-memory, keyed by phone number)
# ============================================================================

conversations: dict = {}

DEFAULT_SETTINGS = {
    "font": "Arial",
    "fontColor": "#FFFFFF",
    "fontSize": 24,
    "musicVolume": 0.15,
    "ducking": True,
    "subtitlesEnabled": True,
    "musicFile": None,
    "youtubeUrl": None,
}


def _get_convo(phone: str) -> dict:
    """Get or create conversation state for a phone number."""
    if phone not in conversations:
        conversations[phone] = {
            "history": [],
            "settings": dict(DEFAULT_SETTINGS),
            "state": "idle",
            "file_id": None,
            "video_path": None,
            "srt_path": None,
            "last_activity": time.time(),
        }
    conversations[phone]["last_activity"] = time.time()
    return conversations[phone]


def _add_history(convo: dict, role: str, content: str):
    """Add a message to conversation history, keeping last 10."""
    convo["history"].append({"role": role, "content": content})
    if len(convo["history"]) > 10:
        convo["history"] = convo["history"][-10:]


# ============================================================================
# System Prompt — adapted from /chat for WhatsApp
# ============================================================================

def _build_system_prompt(convo: dict) -> str:
    s = convo["settings"]
    music_vol_percent = int(s["musicVolume"] * 100) if s["musicVolume"] <= 1 else int(s["musicVolume"])
    has_video = convo["video_path"] is not None

    music_files = list_music_library(str(MUSIC_DIR))
    music_list_str = ", ".join([f["name"] for f in music_files[:10]]) if music_files else "אין קבצי מוזיקה"

    return f"""אתה עוזר AI מקצועי לעריכת וידאו בעברית. אתה מתקשר עם המשתמש דרך וואטסאפ.

=== מצב נוכחי ===
- וידאו הועלה: {"כן ✓" if has_video else "לא - המשתמש צריך לשלוח סרטון"}
- כתוביות מופעלות: {"כן ✓" if s["subtitlesEnabled"] else "לא"}
- פונט נוכחי: {s["font"]} | צבע: {s["fontColor"]} | גודל: {s["fontSize"]}px
- עוצמת מוזיקה: {music_vol_percent}%
- דאקינג: {"מופעל ✓" if s["ducking"] else "כבוי"}

=== ספריית מוזיקה זמינה ===
{music_list_str}

=== פרוטוקול מוזיקה ===
1. אם המשתמש מבקש מוזיקה בסגנון כלשהו: שאל אם רוצה לינק מיוטיוב או שתבחר מהספרייה. אל תבחר עדיין.
2. אם אומר "תבחר אתה" / "מהספרייה": בחר קובץ מהרשימה. השתמש בשם מדויק כולל .mp3.
3. אם שולח לינק יוטיוב: החזר אותו בשדה "youtubeUrl".
- אסור להמציא שמות קבצים.

=== Multi-Intent ===
המשתמש יכול לשלוח מספר בקשות במשפט אחד. זהה את כולן.
סדר: שינויי סגנון (פונט, צבע, גודל, מוזיקה) לפני פעולות (process_video).

=== חוקי עריכה ===
- החזר "action": "process_video" רק כאשר המשתמש כותב במפורש: "תערוך", "תייצא", "עבד", "Export".
- כשהמשתמש מבקש לערוך, הסרטון יעובד וישלח אליו בוואטסאפ כשיהיה מוכן.
- אם אין וידאו, בקש מהמשתמש לשלוח סרטון קודם.

=== כתוביות ===
- אם המשתמש אומר "כתוביות כבויות" או "בלי כתוביות": הגדר subtitlesEnabled = false
- אם אומר "הפעל כתוביות": הגדר subtitlesEnabled = true

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
      "youtubeUrl": "URL או null",
      "subtitlesEnabled": "true/false או null",
      "ducking": "true/false או null",
      "action": "process_video או null"
    }}
  ]
}}

=== דוגמאות ===
משתמש: "שנה צבע לצהוב וגודל 32"
{{"answer": "שיניתי צבע לצהוב וגודל ל-32!", "commands": [{{"fontColor": "#FFD700", "fontSize": 32}}]}}

משתמש: "תערוך"
{{"answer": "מתחיל לעבד את הסרטון! אשלח אותו כשיהיה מוכן.", "commands": [{{"action": "process_video"}}]}}

משתמש: "שנה פונט לדויד, צבע אדום ותערוך"
{{"answer": "שיניתי פונט לדויד, צבע לאדום, ומתחיל עיבוד!", "commands": [{{"font": "David", "fontColor": "#FF0000"}}, {{"action": "process_video"}}]}}

החזר רק JSON תקין, ללא טקסט נוסף."""


# ============================================================================
# AI Chat — call Groq LLM (same as /chat but async-safe)
# ============================================================================

def _call_groq(messages: list) -> str:
    """Synchronous call to Groq (runs in executor)."""
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.7,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


def _parse_ai_response(raw: str, extracted_data: dict) -> tuple[str, list]:
    """
    Parse Groq JSON response into (answer, commands).
    Falls back to regex extraction if JSON parse fails.
    """
    cleaned = raw
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        answer = result.get("answer", raw)
        commands_raw = result.get("commands", [result.get("command", {})])
        if not isinstance(commands_raw, list):
            commands_raw = [commands_raw]

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

        # Post-processing: inject regex-extracted data LLM missed
        has_yt = any(c.get("youtubeUrl") for c in commands)
        if extracted_data.get("youtube") and not has_yt:
            if commands:
                commands[0]["youtubeUrl"] = extracted_data["youtube"]
            else:
                commands.append({"youtubeUrl": extracted_data["youtube"]})

        has_color = any(c.get("fontColor") for c in commands)
        if extracted_data.get("color") and not has_color:
            target = commands[0] if commands else {}
            target["fontColor"] = extracted_data["color"]
            if not commands:
                commands.append(target)

        has_size = any(c.get("fontSize") for c in commands)
        if extracted_data.get("size") and not has_size:
            target = commands[0] if commands else {}
            target["fontSize"] = int(extracted_data["size"])
            if not commands:
                commands.append(target)

        return answer, commands

    except json.JSONDecodeError:
        print(f"[WA-Chat] JSON parse failed, using raw answer")
        fallback_cmd = {}
        if extracted_data.get("youtube"):
            fallback_cmd["youtubeUrl"] = extracted_data["youtube"]
        if extracted_data.get("color"):
            fallback_cmd["fontColor"] = extracted_data["color"]
        if extracted_data.get("size"):
            fallback_cmd["fontSize"] = int(extracted_data["size"])
        return raw, [fallback_cmd] if fallback_cmd else []


# ============================================================================
# Video Processing — Phase 1 (transcribe) and Phase 2 (finalize)
# ============================================================================

async def _phase1_transcribe(phone: str, convo: dict):
    """Phase 1: Transcribe video and send subtitles for review."""
    chat_id = phone
    loop = asyncio.get_event_loop()
    video_path = convo["video_path"]
    file_id = convo["file_id"]
    srt_path = str(OUTPUTS_DIR / f"{file_id}.srt")
    convo["srt_path"] = srt_path

    send_text_message(chat_id, "⏳ מתחיל לעבד את הסרטון... מתמלל...")

    try:
        has_audio = check_video_has_audio(video_path)

        if has_audio:
            success, transcript = await loop.run_in_executor(
                None, lambda: transcribe_with_groq(video_path, srt_path, None)
            )
            if not success:
                send_text_message(chat_id, "❌ שגיאה בתמלול. נסה שוב.")
                convo["state"] = "idle"
                return
        else:
            # No audio — use Gemini for visual text extraction
            from services.video_service import extract_text_huggingface
            transcript, entries = await loop.run_in_executor(
                None, lambda: extract_text_huggingface(video_path, None, srt_path)
            )

        # Fix subtitles with AI
        srt_file = Path(srt_path)
        if srt_file.exists() and srt_file.stat().st_size > 0:
            await loop.run_in_executor(
                None, lambda: fix_subtitles_with_ai(srt_path, None)
            )

        # Read subtitles and send to user for review
        entries = parse_srt_file(srt_path)
        if not entries:
            send_text_message(chat_id, "⚠️ לא הצלחתי לחלץ כתוביות מהסרטון. ממשיך בעיבוד בלי כתוביות...")
            convo["settings"]["subtitlesEnabled"] = False
            convo["state"] = "processing"
            await _phase2_finalize(phone, convo)
            return

        # Build subtitles text for user review
        subtitle_lines = []
        for entry in entries:
            text = entry.get("text", "")
            subtitle_lines.append(text)

        subtitles_text = "\n".join(subtitle_lines)

        review_msg = (
            f"📝 הנה הכתוביות שמצאתי:\n\n"
            f"{subtitles_text}\n\n"
            f"שלח *אישור* להמשיך עם הכתוביות האלה,\n"
            f"או שלח את הטקסט המתוקן."
        )
        send_text_message(chat_id, review_msg)
        convo["state"] = "waiting_subtitle_review"
        print(f"[WA-Chat] {phone}: Sent subtitles for review, state=waiting_subtitle_review")

    except Exception as e:
        print(f"[WA-Chat] Phase 1 error: {e}")
        import traceback
        traceback.print_exc()
        send_text_message(chat_id, f"❌ שגיאה בעיבוד: {str(e)[:200]}")
        convo["state"] = "idle"


async def _phase2_finalize(phone: str, convo: dict):
    """Phase 2: Select music, mix, burn subtitles, render final video."""
    chat_id = phone
    loop = asyncio.get_event_loop()
    s = convo["settings"]
    file_id = convo["file_id"]
    video_path = convo["video_path"]
    srt_path = convo["srt_path"]
    out_path = str(OUTPUTS_DIR / f"{file_id}_final.mp4")

    send_text_message(chat_id, "⏳ ממשיך עיבוד... מוסיף מוזיקה וכתוביות...")

    try:
        video_duration = get_video_duration(video_path)
        video_width, video_height = get_video_resolution(video_path)

        # --- Music selection ---
        chosen_music = None

        if s.get("youtubeUrl"):
            # Download from YouTube
            downloaded = download_audio_from_url(s["youtubeUrl"], str(MUSIC_TEMP_DIR))
            if downloaded:
                chosen_music = downloaded
        elif s.get("musicFile"):
            lib_path = MUSIC_DIR / s["musicFile"]
            if lib_path.exists():
                chosen_music = str(lib_path)

        if not chosen_music:
            chosen_music = get_random_music("calm", str(MUSIC_DIR))
            if not chosen_music:
                all_music = list(MUSIC_DIR.glob("*.mp3"))
                if all_music:
                    chosen_music = str(random.choice(all_music))

        # --- ASS subtitles ---
        final_subtitle_path = None
        srt_file = Path(srt_path) if srt_path else None

        if s["subtitlesEnabled"] and srt_file and srt_file.exists() and srt_file.stat().st_size > 0:
            ass_path = str(OUTPUTS_DIR / f"{file_id}.ass")

            font_name = await loop.run_in_executor(None, ensure_font_available, s["font"])

            ok = await loop.run_in_executor(
                None, lambda: convert_srt_to_ass(
                    srt_path, ass_path, video_width, video_height,
                    font_name=font_name,
                    font_color=s["fontColor"],
                    font_size=s["fontSize"],
                )
            )
            if ok and Path(ass_path).exists():
                final_subtitle_path = ass_path
            else:
                final_subtitle_path = srt_path

        # --- Final merge ---
        merge_success = await loop.run_in_executor(
            None,
            lambda: merge_final_video(
                v_input=video_path,
                srt_input=final_subtitle_path,
                v_output=out_path,
                music_path=str(chosen_music) if chosen_music else None,
                voice_path=None,
            ),
        )

        out_file = Path(out_path)
        if not merge_success or not out_file.exists():
            send_text_message(chat_id, "❌ שגיאה ביצירת הסרטון הסופי.")
            convo["state"] = "idle"
            return

        # --- Send video back via WhatsApp ---
        video_url = f"{SERVER_BASE_URL}/outputs/{out_file.name}"
        print(f"[WA-Chat] Sending final video: {video_url}")

        send_file_by_url(
            chat_id=chat_id,
            file_url=video_url,
            filename=out_file.name,
            caption="✅ הסרטון מוכן!",
        )

        convo["state"] = "idle"
        print(f"[WA-Chat] {phone}: Video sent, state=idle")

    except Exception as e:
        print(f"[WA-Chat] Phase 2 error: {e}")
        import traceback
        traceback.print_exc()
        send_text_message(chat_id, f"❌ שגיאה בעיבוד: {str(e)[:200]}")
        convo["state"] = "idle"


# ============================================================================
# Subtitle Review Handler
# ============================================================================

async def _handle_subtitle_review(phone: str, convo: dict, text: str):
    """Handle user response during subtitle review state."""
    chat_id = phone
    normalized = text.strip().lower()

    # Check for approval keywords
    approval_words = ["אישור", "אשר", "ok", "אוקיי", "בסדר", "ממשיך", "המשך", "yes", "כן"]
    is_approved = any(word in normalized for word in approval_words)

    if not is_approved:
        # User sent corrected text — update SRT
        srt_path = convo.get("srt_path")
        if srt_path:
            try:
                entries = parse_srt_file(srt_path)
                corrected_lines = text.strip().split("\n")
                corrected_lines = [l.strip() for l in corrected_lines if l.strip()]

                if entries and corrected_lines:
                    # Map corrected lines to existing timing entries
                    for i, entry in enumerate(entries):
                        if i < len(corrected_lines):
                            entry["text"] = corrected_lines[i]
                    write_srt_from_entries(entries, srt_path)
                    send_text_message(chat_id, "✏️ עדכנתי את הכתוביות!")
                else:
                    send_text_message(chat_id, "⚠️ לא הצלחתי לעדכן. ממשיך עם הכתוביות המקוריות.")
            except Exception as e:
                print(f"[WA-Chat] Subtitle update error: {e}")
                send_text_message(chat_id, "⚠️ שגיאה בעדכון הכתוביות, ממשיך עם המקוריות.")
    else:
        send_text_message(chat_id, "👍 מעולה!")

    # Continue to Phase 2
    convo["state"] = "processing"
    await _phase2_finalize(phone, convo)


# ============================================================================
# Main Entry Point
# ============================================================================

async def handle_whatsapp_message(phone: str, text: str, media_url: str | None = None):
    """
    Main handler for incoming WhatsApp messages.
    Called from the webhook endpoint. Runs as a background task.
    """
    convo = _get_convo(phone)
    chat_id = phone

    print(f"\n[WA-Chat] ======== INCOMING ========")
    print(f"[WA-Chat] Phone: {phone}")
    print(f"[WA-Chat] State: {convo['state']}")
    print(f"[WA-Chat] Text: {text[:100] if text else '(none)'}")
    print(f"[WA-Chat] Media: {media_url[:80] if media_url else '(none)'}")

    # --- Block concurrent processing ---
    if convo["state"] == "processing":
        send_text_message(chat_id, "⏳ הסרטון שלך עדיין בעיבוד... אנא המתן.")
        return

    # --- State: Waiting for subtitle review ---
    if convo["state"] == "waiting_subtitle_review":
        if text:
            await _handle_subtitle_review(phone, convo, text)
        else:
            send_text_message(chat_id, "שלח *אישור* להמשיך, או שלח טקסט מתוקן.")
        return

    # --- Handle incoming video media ---
    if media_url:
        local_path = download_media(media_url)
        if local_path:
            file_id = Path(local_path).stem
            convo["video_path"] = local_path
            convo["file_id"] = file_id
            convo["srt_path"] = None

            # Check if user also sent a text command with the video
            if text and _is_process_command(text):
                send_text_message(chat_id, "📹 קיבלתי את הסרטון! מתחיל לעבד...")
                _add_history(convo, "user", text)
                convo["state"] = "processing"
                await _phase1_transcribe(phone, convo)
                return
            else:
                send_text_message(chat_id, "📹 קיבלתי את הסרטון שלך! שלח *תערוך* כשתהיה מוכן, או שנה הגדרות קודם (פונט, צבע, מוזיקה וכו').")
                _add_history(convo, "assistant", "קיבלתי את הסרטון")
                return
        else:
            send_text_message(chat_id, "❌ לא הצלחתי להוריד את הקובץ. נסה שוב.")
            return

    # --- Handle text message ---
    if not text:
        return

    _add_history(convo, "user", text)

    # Quick check: is this a process command without video?
    if _is_process_command(text) and not convo.get("video_path"):
        send_text_message(chat_id, "📹 שלח לי סרטון קודם ואז אוכל לעבד אותו.")
        _add_history(convo, "assistant", "צריך סרטון קודם")
        return

    # --- Call AI ---
    if not GROQ_API_KEY:
        send_text_message(chat_id, "❌ שגיאת מערכת: Groq API key לא מוגדר.")
        return

    try:
        # Pre-process: regex extraction
        extracted = _extract_regex(text)

        # Build system prompt
        system_prompt = _build_system_prompt(convo)

        # Add hint for regex findings
        hint = ""
        if extracted.get("youtube"):
            hint += f"\n[המערכת זיהתה לינק יוטיוב: {extracted['youtube']}]"
        if extracted.get("color"):
            hint += f"\n[המערכת זיהתה צבע: {extracted['color']}]"
        if extracted.get("size"):
            hint += f"\n[המערכת זיהתה גודל: {extracted['size']}]"

        messages = [{"role": "system", "content": system_prompt}]
        for msg in convo["history"][-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        if hint:
            messages[-1]["content"] += hint

        # Call Groq in executor (blocking call)
        loop = asyncio.get_event_loop()
        raw_response = await loop.run_in_executor(None, lambda: _call_groq(messages))

        print(f"[WA-Chat] LLM response: {raw_response[:200]}")

        answer, commands = _parse_ai_response(raw_response, extracted)

        # --- Execute commands ---
        has_process_action = False

        for cmd in commands:
            # Style changes → save to state
            for key in ["font", "fontColor", "fontSize", "musicVolume", "musicFile",
                        "youtubeUrl", "subtitlesEnabled", "ducking"]:
                if key in cmd:
                    val = cmd[key]
                    # Convert booleans
                    if key in ("subtitlesEnabled", "ducking"):
                        if isinstance(val, str):
                            val = val.lower() in ("true", "1", "yes")
                    convo["settings"][key] = val
                    print(f"[WA-Chat] Setting {key} = {val}")

            if cmd.get("action") == "process_video":
                has_process_action = True

        # Send AI answer
        send_text_message(chat_id, answer)
        _add_history(convo, "assistant", answer)

        # Start processing if requested
        if has_process_action:
            if convo.get("video_path"):
                convo["state"] = "processing"
                await _phase1_transcribe(phone, convo)
            else:
                send_text_message(chat_id, "📹 שלח לי סרטון קודם ואז אוכל לעבד אותו.")

    except Exception as e:
        print(f"[WA-Chat] Error: {e}")
        import traceback
        traceback.print_exc()
        send_text_message(chat_id, f"❌ שגיאה: {str(e)[:200]}")


# ============================================================================
# Helpers
# ============================================================================

def _is_process_command(text: str) -> bool:
    """Check if text is a video processing command."""
    normalized = text.strip().lower()
    process_words = ["תערוך", "תייצא", "עבד", "export", "עריכה", "process", "render"]
    return any(w in normalized for w in process_words)


def _extract_regex(text: str) -> dict:
    """Extract YouTube URLs, colors, sizes from text using regex."""
    data = {}

    yt_match = re.findall(
        r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+(?:[?&]\S*)?)',
        text
    )
    if yt_match:
        data["youtube"] = yt_match[0]

    color_match = re.findall(r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b', text)
    if color_match:
        data["color"] = color_match[0]

    size_match = re.findall(r'(?:גודל|size)\s*[=:]?\s*(\d{1,3})', text, re.IGNORECASE)
    if size_match:
        data["size"] = size_match[0]

    vol_match = re.findall(r'(?:ווליום|volume|עוצמ[הת])\s*[=:]?\s*(\d{1,3})\s*%?', text, re.IGNORECASE)
    if vol_match:
        data["volume"] = vol_match[0]

    return data


def cleanup_stale_conversations(max_age_hours: int = 24):
    """Remove conversation states older than max_age_hours."""
    cutoff = time.time() - (max_age_hours * 3600)
    stale = [p for p, c in conversations.items() if c["last_activity"] < cutoff]
    for p in stale:
        del conversations[p]
    if stale:
        print(f"[WA-Chat] Cleaned up {len(stale)} stale conversations")
