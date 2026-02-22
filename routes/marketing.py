"""
Marketing routes — AI-generated text, thumbnails, and shorts.
"""
import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException

from core import marketing_cache
from services.audio_service import transcribe_with_groq
from services.video_service import (
    get_video_duration,
    check_video_has_audio,
    generate_thumbnail,
    generate_ai_thumbnail_image,
    cut_viral_shorts,
    extract_text_huggingface,
)
from services.marketing_service import generate_marketing_kit
from utils.config import INPUTS_DIR, OUTPUTS_DIR, SERVER_BASE_URL

router = APIRouter()


@router.post("/generate-marketing-text")
async def generate_marketing_text(video_id: str = Form(...)):
    """Generate marketing text content: titles, description, tags, viral moments."""
    v_path = INPUTS_DIR / video_id
    file_id = video_id.split('.')[0]
    thumb_out = OUTPUTS_DIR / f"{file_id}_thumb.jpg"

    if not v_path.exists():
        return {"status": "error", "error": "הקובץ לא נמצא בשרת."}

    try:
        video_duration = get_video_duration(str(v_path))
        has_audio = check_video_has_audio(str(v_path))
        loop = asyncio.get_event_loop()
        transcript_text = ""

        if has_audio:
            srt_path = OUTPUTS_DIR / f"{file_id}_marketing.srt"
            success, transcript_text = await loop.run_in_executor(
                None, lambda: transcribe_with_groq(str(v_path), str(srt_path), None)
            )
        else:
            transcript_text, _ = await loop.run_in_executor(
                None, lambda: extract_text_huggingface(str(v_path), None, None)
            )

        if not transcript_text:
            transcript_text = "סרטון ללא מלל מזוהה"

        marketing_data = await loop.run_in_executor(
            None, lambda: generate_marketing_kit(transcript_text, video_duration, None)
        )

        if not marketing_data:
            return {"status": "error", "error": "נכשל ביצירת תוכן שיווקי"}

        # Generate basic thumbnail
        thumbnail_url = None
        title = marketing_data.get("titles", [""])[0] if marketing_data.get("titles") else "סרטון חדש"
        punchline = marketing_data.get("punchline", "")

        ok = await loop.run_in_executor(
            None, lambda: generate_thumbnail(str(v_path), title, str(thumb_out), None, punchline)
        )
        if ok and thumb_out.exists():
            thumbnail_url = f"{SERVER_BASE_URL}/outputs/{thumb_out.name}"

        # Cache for other endpoints
        marketing_cache[file_id] = {
            "marketing_data": marketing_data,
            "transcript_text": transcript_text,
            "video_duration": video_duration,
            "title": title,
            "punchline": punchline,
            "srt_path": str(OUTPUTS_DIR / f"{file_id}_marketing.srt") if has_audio else None
        }

        marketing_kit = {
            "title": title,
            "description": marketing_data.get("facebook_post", ""),
            "tags": " ".join(marketing_data.get("hashtags", [])),
            "punchline": punchline,
            "image_prompt": marketing_data.get("image_prompt", ""),
            "viral_moments": marketing_data.get("viral_moments", []),
        }

        return {"status": "success", "marketing_kit": marketing_kit, "thumbnail_url": thumbnail_url}

    except Exception as e:
        print(f"[MARKETING-TEXT ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@router.post("/generate-marketing-ai-image")
async def generate_marketing_ai_image(
    video_id: str = Form(...),
    custom_prompt: str = Form(None),
    provider: str = Form("leonardo"),
    netfree_mode: str = Form("false"),
):
    """Generate AI image using Leonardo or Gemini (Nano Banana)."""
    is_netfree = netfree_mode.lower() == "true"
    file_id = video_id.split('.')[0]
    v_path = INPUTS_DIR / video_id

    if not v_path.exists():
        return {"status": "error", "error": "הקובץ לא נמצא בשרת."}

    try:
        cached = marketing_cache.get(file_id, {})
        marketing_data = cached.get("marketing_data", {})
        title = cached.get("title", "סרטון חדש")
        punchline = cached.get("punchline", "")

        if custom_prompt and custom_prompt.strip():
            image_prompt = custom_prompt.strip()
        else:
            image_prompt = marketing_data.get("image_prompt", "")
            if not image_prompt:
                return {"status": "error", "error": "אין prompt לתמונה. יש ליצור תוכן שיווקי קודם."}

        ai_out = OUTPUTS_DIR / f"{file_id}_ai_thumb_{uuid.uuid4().hex[:4]}.jpg"
        loop = asyncio.get_event_loop()

        success, result_data = await loop.run_in_executor(
            None, lambda: generate_ai_thumbnail_image(
                image_prompt, title, str(ai_out), None, punchline, provider, is_netfree
            )
        )

        if success:
            if is_netfree and result_data == "file" and ai_out.exists():
                return {
                    "status": "netfree_preview",
                    "preview_url": f"{SERVER_BASE_URL}/outputs/{ai_out.name}",
                    "prompt_used": image_prompt
                }
            elif result_data and isinstance(result_data, str) and result_data.startswith("data:"):
                return {"status": "success", "ai_thumbnail_url": result_data, "prompt_used": image_prompt}
            elif ai_out.exists():
                return {
                    "status": "success",
                    "ai_thumbnail_url": f"{SERVER_BASE_URL}/outputs/{ai_out.name}",
                    "prompt_used": image_prompt
                }
        return {"status": "error", "error": "נכשל ביצירת תמונת AI"}

    except Exception as e:
        print(f"[MARKETING-AI-IMAGE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@router.post("/generate-marketing-shorts")
async def generate_marketing_shorts(
    video_id: str = Form(...),
    with_subtitles: bool = Form(False),
    subtitle_color: str = Form(None),
):
    """Generate vertical Shorts (9:16) from viral moments."""
    file_id = video_id.split('.')[0]
    v_path = INPUTS_DIR / video_id

    if not v_path.exists():
        return {"status": "error", "error": "הקובץ לא נמצא בשרת."}

    try:
        cached = marketing_cache.get(file_id, {})
        marketing_data = cached.get("marketing_data", {})
        viral_moments = marketing_data.get("viral_moments", [])
        srt_path = cached.get("srt_path")

        if not viral_moments:
            return {"status": "error", "error": "אין viral_moments. יש ליצור תוכן שיווקי קודם."}

        subtitle_path = None
        if with_subtitles and srt_path and Path(srt_path).exists():
            subtitle_path = srt_path

        loop = asyncio.get_event_loop()
        shorts_paths = await loop.run_in_executor(
            None, lambda: cut_viral_shorts(
                video_path=str(v_path), viral_moments=viral_moments,
                output_dir=str(OUTPUTS_DIR), subtitle_path=subtitle_path,
                use_ass=False, progress_callback=None, vertical=True,
                subtitle_color=subtitle_color, with_subtitles=with_subtitles
            )
        )

        if shorts_paths:
            shorts_urls = [f"{SERVER_BASE_URL}/outputs/shorts/{Path(p).name}" for p in shorts_paths]
            return {"status": "success", "shorts_urls": shorts_urls, "with_subtitles": with_subtitles, "subtitle_color": subtitle_color}
        return {"status": "error", "error": "לא נוצרו קליפים"}

    except Exception as e:
        print(f"[MARKETING-SHORTS ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
