"""
WhatsApp integration routes — n8n command endpoint and Green API webhook.
"""
import asyncio
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from starlette.requests import Request as StarletteRequest

from services.audio_service import transcribe_with_groq, download_audio_from_url
from services.video_service import (
    get_video_duration, check_video_has_audio,
    extract_text_huggingface, video_planner_chat,
)
from services.marketing_service import generate_marketing_kit
from services.greenapi_service import is_configured as greenapi_is_configured, check_connection as greenapi_check
from services.whatsapp_chat_service import handle_whatsapp_message
from utils.config import GROQ_API_KEY, INPUTS_DIR, OUTPUTS_DIR, SERVER_BASE_URL
from routes.video import process_video_task

router = APIRouter()


class WhatsAppCommandRequest(BaseModel):
    message: str
    media_url: Optional[str] = None


@router.post("/api/whatsapp-command")
async def whatsapp_command(req: WhatsAppCommandRequest):
    """Unified AI command endpoint for n8n / WhatsApp integration."""
    import json as _json
    from groq import Groq

    message = req.message.strip()
    media_url = req.media_url

    if not message:
        return {"type": "error", "message": "לא התקבלה הודעה"}

    if not GROQ_API_KEY:
        return {"type": "error", "message": "Groq API key not configured"}

    classify_prompt = """אתה מנתח בקשות לעריכת וידאו. סווג את הבקשה:
1. "editing" — עריכת וידאו, כתוביות, shorts, מוזיקה, ייצוא
2. "script" — תסריט, סקריפט, תכנון תוכן
3. "marketing" — כותרות, תיאורים, תגיות, פוסט, hashtags
4. "chat" — שאלה כללית, שיחה

החזר JSON: {"intent": "editing|script|marketing|chat", "summary": "תיאור קצר"}"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        loop = asyncio.get_event_loop()

        classify_response = await loop.run_in_executor(
            None, lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": classify_prompt}, {"role": "user", "content": message}],
                temperature=0.1, max_tokens=150,
            ),
        )

        raw_intent = classify_response.choices[0].message.content.strip()
        cleaned = raw_intent
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) >= 2:
                cleaned = parts[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

        intent_data = _json.loads(cleaned)
        intent = intent_data.get("intent", "chat")

    except Exception:
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["תסריט", "סקריפט", "script", "רעיון", "תכנון"]):
            intent = "script"
        elif any(w in msg_lower for w in ["שיווק", "marketing", "כותרת", "תיאור", "hashtag", "פוסט"]):
            intent = "marketing"
        elif any(w in msg_lower for w in ["עריכה", "edit", "כתוביות", "subtitle", "shorts", "מוזיקה"]):
            intent = "editing"
        else:
            intent = "chat"

    # Route to handler
    if intent == "script":
        try:
            result = await loop.run_in_executor(
                None, lambda: video_planner_chat(message, [], "", ""),
            )
            if result.get("success"):
                return {"type": "text", "content": result.get("script", ""), "message": result.get("ai_message", "התסריט נוצר")}
            return {"type": "error", "message": result.get("error", "שגיאה ביצירת תסריט")}
        except Exception as e:
            return {"type": "error", "message": f"שגיאה ביצירת תסריט: {str(e)}"}

    if intent == "marketing":
        video_path, file_id = _resolve_media(media_url)
        if not video_path:
            return {"type": "error", "message": "לא נמצא סרטון. שלח קישור או העלה קובץ."}

        try:
            video_duration = get_video_duration(str(video_path))
            has_audio = check_video_has_audio(str(video_path))
            transcript_text = ""

            if has_audio:
                srt_path = OUTPUTS_DIR / f"{file_id}_wa_marketing.srt"
                _, transcript_text = await loop.run_in_executor(
                    None, lambda: transcribe_with_groq(str(video_path), str(srt_path), None)
                )
            else:
                transcript_text, _ = await loop.run_in_executor(
                    None, lambda: extract_text_huggingface(str(video_path), None, None)
                )

            marketing_data = await loop.run_in_executor(
                None, lambda: generate_marketing_kit(transcript_text or "סרטון ללא מלל", video_duration, None)
            )
            if not marketing_data:
                return {"type": "error", "message": "נכשל ביצירת תוכן שיווקי"}

            return {"type": "marketing", "data": marketing_data, "message": "חומרי שיווק נוצרו!"}
        except Exception as e:
            return {"type": "error", "message": f"שגיאה ביצירת שיווק: {str(e)}"}

    if intent == "editing":
        video_path, file_id = _resolve_media(media_url)
        if not video_path:
            return {"type": "error", "message": "לעריכה נדרש סרטון. שלח קישור או העלה קובץ."}

        try:
            srt_path = OUTPUTS_DIR / f"{file_id}.srt"
            out_path = OUTPUTS_DIR / f"{file_id}_edited.mp4"

            await process_video_task(
                file_id=file_id, v_path=video_path, srt_path=srt_path, out_path=out_path,
                do_music=True, do_subtitles=True, do_marketing=False, do_shorts=False,
                do_thumbnail=False, do_styled_subtitles=True, do_voiceover=False,
                music_style="calm", font_name="Arial", font_color="#FFFFFF", font_size=24,
            )

            if out_path.exists():
                return {"type": "video", "url": f"{SERVER_BASE_URL}/outputs/{out_path.name}", "message": "הסרטון עובד בהצלחה!"}
            return {"type": "error", "message": "העיבוד הסתיים אך הפלט לא נמצא"}
        except Exception as e:
            return {"type": "error", "message": f"שגיאה בעריכה: {str(e)}"}

    # General chat
    try:
        chat_response = await loop.run_in_executor(
            None, lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "אתה עוזר AI מקצועי לעריכת וידאו בעברית. ענה בצורה ידידותית וקצרה."},
                    {"role": "user", "content": message},
                ],
                temperature=0.7, max_tokens=500,
            ),
        )
        return {"type": "text", "content": chat_response.choices[0].message.content.strip(), "message": "תשובה מה-AI"}
    except Exception as e:
        return {"type": "error", "message": f"שגיאה: {str(e)}"}


def _resolve_media(media_url: Optional[str]):
    """Resolve video path and file_id from media_url or most recent upload."""
    if media_url:
        file_id = uuid.uuid4().hex[:8]
        video_path = INPUTS_DIR / f"{file_id}.mp4"
        try:
            download_audio_from_url(media_url, str(video_path))
            if video_path.exists():
                return video_path, file_id
        except Exception:
            pass
        return None, None

    input_files = sorted(INPUTS_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    if input_files:
        return input_files[0], input_files[0].stem
    return None, None


# =============================================================================
# Green API Webhook
# =============================================================================

@router.post("/api/greenapi/webhook")
async def greenapi_webhook(request: StarletteRequest, background_tasks: BackgroundTasks):
    """Webhook receiver for Green API WhatsApp messages."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    if body.get("typeWebhook") != "incomingMessageReceived":
        return {"status": "ok"}

    sender_data = body.get("senderData", {})
    message_data = body.get("messageData", {})
    chat_id = sender_data.get("chatId", "")

    if not chat_id or "@g.us" in chat_id:
        return {"status": "ok"}

    text = ""
    media_url = None
    type_message = message_data.get("typeMessage", "")

    if type_message == "textMessage":
        text = message_data.get("textMessageData", {}).get("textMessage", "")
    elif type_message in ("videoMessage", "documentMessage", "audioMessage"):
        file_data = message_data.get("fileMessageData", {})
        media_url = file_data.get("downloadUrl", "")
        text = file_data.get("caption", "")
    elif type_message == "extendedTextMessage":
        text = message_data.get("extendedTextMessageData", {}).get("text", "")

    if not text and not media_url:
        return {"status": "ok"}

    background_tasks.add_task(handle_whatsapp_message, chat_id, text, media_url)
    return {"status": "ok"}


@router.get("/api/greenapi/status")
async def greenapi_status():
    """Check Green API connection status."""
    if not greenapi_is_configured():
        return {"configured": False, "message": "Green API credentials not set."}

    result = greenapi_check()
    return {"configured": True, "connected": result.get("ok", False), "data": result.get("data"), "error": result.get("error")}
