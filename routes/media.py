"""
Media routes — YouTube download, voiceover generation, music library.
"""
import asyncio
import uuid
import re
import hashlib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from services.audio_service import (
    generate_voiceover_sync,
    generate_voiceover_elevenlabs_sync,
    list_music_library,
    download_audio_from_url,
)
from services.text_service import extract_text_from_file
from services.video_service import generate_ai_thumbnail_image, download_image_from_url
from core import ai_thumbnail_original_urls
from utils.config import INPUTS_DIR, OUTPUTS_DIR, MUSIC_DIR, MUSIC_TEMP_DIR, ELEVENLABS_EMOTION_SETTINGS, SERVER_BASE_URL

router = APIRouter()


# =============================================================================
# Request Models
# =============================================================================

class AIThumbnailRequest(BaseModel):
    video_id: str
    prompt: str
    title: str


class RetryDownloadRequest(BaseModel):
    video_id: str
    original_url: str
    title: Optional[str] = None


# =============================================================================
# YouTube Audio Download
# =============================================================================

@router.post("/download-youtube-audio")
async def download_yt_audio(url: str = Form(...)):
    """Download audio from YouTube URL."""
    import yt_dlp

    try:
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+(?:&\S*)?)'
        match = re.search(youtube_regex, url)

        if not match:
            return {"status": "error", "message": "לא מצאתי לינק תקין בהודעה"}

        clean_url = match.group(0)
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:8]
        output_filename = f"yt_{url_hash}"
        file_path = MUSIC_DIR / f"{output_filename}.mp3"

        if file_path.exists():
            return {
                "status": "success",
                "audioUrl": f"{SERVER_BASE_URL}/assets/music/{output_filename}.mp3",
                "filename": f"{output_filename}.mp3"
            }

        output_template = str(MUSIC_DIR / output_filename)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'socket_timeout': 30,
        }

        def _do_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([clean_url])

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_download)

        return {
            "status": "success",
            "audioUrl": f"{SERVER_BASE_URL}/assets/music/{output_filename}.mp3",
            "filename": f"{output_filename}.mp3"
        }
    except ConnectionResetError:
        return {"status": "error", "message": "החיבור נותק. נסה שוב."}
    except Exception as e:
        print(f"[ERROR] YouTube download failed: {str(e)}")
        return {"status": "error", "message": str(e)}


# =============================================================================
# YouTube Video Download
# =============================================================================

@router.post("/download-youtube-video")
async def download_youtube_video_endpoint(url: str = Form(...)):
    """Download full MP4 video from YouTube."""
    import yt_dlp

    try:
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+(?:&\S*)?)'
        match = re.search(youtube_regex, url)
        if not match:
            raise HTTPException(status_code=400, detail="הלינק שסיפקת אינו תקין.")

        clean_url = match.group(0)
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:8]
        filename = f"yt_video_{url_hash}.mp4"
        file_path = OUTPUTS_DIR / filename

        if file_path.exists():
            return {
                "status": "success",
                "videoUrl": f"{SERVER_BASE_URL}/outputs/{filename}",
                "filename": filename,
                "message": "הוידאו כבר קיים במערכת"
            }

        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(OUTPUTS_DIR / f"yt_video_{url_hash}") + '.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': True,
            'socket_timeout': 30,
        }

        def _do_video_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=True)
                return info.get('title', 'YouTube Video')

        loop = asyncio.get_event_loop()
        title = await loop.run_in_executor(None, _do_video_download)

        downloaded_file = None
        for ext in ['mp4', 'webm', 'mkv']:
            check_path = OUTPUTS_DIR / f"yt_video_{url_hash}.{ext}"
            if check_path.exists():
                downloaded_file = check_path
                break

        if not downloaded_file:
            raise HTTPException(status_code=500, detail="ההורדה נכשלה - הקובץ לא נוצר")

        return {
            "status": "success",
            "videoUrl": f"{SERVER_BASE_URL}/outputs/{downloaded_file.name}",
            "filename": downloaded_file.name,
            "title": title,
            "message": f"הוידאו '{title}' הורד בהצלחה!"
        }

    except HTTPException:
        raise
    except ConnectionResetError:
        return {"status": "error", "message": "החיבור נותק. נסה שוב."}
    except Exception as e:
        error_msg = str(e)
        detail = "שגיאה בהורדת הוידאו מיוטיוב"
        if "Video unavailable" in error_msg or "Private video" in error_msg:
            detail = "הסרטון אינו זמין (פרטי או הוסר)"
        elif "age" in error_msg.lower():
            detail = "הסרטון מוגבל לפי גיל ולא ניתן להורדה"
        elif "copyright" in error_msg.lower():
            detail = "הסרטון חסום עקב זכויות יוצרים"
        elif "live" in error_msg.lower():
            detail = "לא ניתן להוריד שידורים חיים"
        raise HTTPException(status_code=500, detail=detail)


# =============================================================================
# Voiceover
# =============================================================================

@router.post("/generate-voiceover")
async def generate_voiceover_endpoint(video_id: str = Form(...), text: str = Form(...)):
    """Generate voiceover using Edge-TTS (free)."""
    output_path = OUTPUTS_DIR / f"{video_id}_voiceover.mp3"
    try:
        success = generate_voiceover_sync(text, str(output_path), None)
        if success and output_path.exists():
            return {"status": "success", "voiceover_url": f"{SERVER_BASE_URL}/outputs/{output_path.name}"}
        raise HTTPException(status_code=500, detail="Failed to generate voiceover")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-voiceover-elevenlabs")
async def generate_voiceover_elevenlabs_endpoint(
    text: str = Form(...),
    emotion: str = Form("neutral"),
    voice_id: Optional[str] = Form(None),
):
    """Generate voiceover using ElevenLabs API."""
    try:
        file_id = str(uuid.uuid4())[:8]
        output_path = OUTPUTS_DIR / f"{file_id}_elevenlabs_voiceover.mp3"

        success = generate_voiceover_elevenlabs_sync(
            text=text, output_path=str(output_path), emotion=emotion, voice_id=voice_id
        )

        if success and output_path.exists():
            return {"status": "success", "voiceover_url": f"{SERVER_BASE_URL}/outputs/{output_path.name}"}
        raise HTTPException(status_code=500, detail="Failed to generate voiceover")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Text Extraction & Music Library
# =============================================================================

@router.post("/extract-text")
async def extract_text_endpoint(file: UploadFile = File(...)):
    """Extract text from uploaded Word (.docx) or Text (.txt) file."""
    try:
        import shutil
        file_id = str(uuid.uuid4())[:8]
        suffix = Path(file.filename).suffix.lower()
        temp_path = INPUTS_DIR / f"{file_id}_doc{suffix}"

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        text = extract_text_from_file(str(temp_path))

        try:
            temp_path.unlink()
        except Exception:
            pass

        return {"status": "success", "text": text}
    except Exception as e:
        return {"status": "error", "text": "", "error": str(e)}


@router.get("/music-library")
async def get_music_library():
    """Get list of available music files in the library."""
    try:
        music_files = list_music_library(str(MUSIC_DIR))
        return {"status": "success", "music_files": music_files}
    except Exception as e:
        return {"status": "error", "message": str(e), "music_files": []}


@router.get("/emotion-presets")
async def get_emotion_presets():
    """Get available emotion presets for ElevenLabs voiceover."""
    return {"status": "success", "presets": list(ELEVENLABS_EMOTION_SETTINGS.keys())}


# =============================================================================
# AI Thumbnail
# =============================================================================

@router.post("/generate-ai-thumbnail")
async def generate_ai_thumbnail_endpoint(request: AIThumbnailRequest):
    """Generate AI thumbnail using Leonardo AI."""
    output_path = OUTPUTS_DIR / f"{request.video_id}_ai_thumbnail.jpg"
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: generate_ai_thumbnail_image(request.prompt, request.title, str(output_path), None)
        )

        if isinstance(result, tuple):
            success, original_url = result
        else:
            success, original_url = result, None

        if success and output_path.exists():
            thumbnail_url = f"{SERVER_BASE_URL}/outputs/{output_path.name}"
            if original_url:
                ai_thumbnail_original_urls[request.video_id] = original_url
            return {"status": "success", "thumbnail_url": thumbnail_url, "original_url": original_url}

        raise HTTPException(status_code=500, detail="Failed to generate AI thumbnail")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry-download")
async def retry_download_endpoint(request: RetryDownloadRequest):
    """Retry downloading an image from original URL."""
    output_path = OUTPUTS_DIR / f"{request.video_id}_ai_thumbnail.jpg"
    try:
        success = download_image_from_url(request.original_url, str(output_path), request.title)
        if success and output_path.exists():
            return {"status": "success", "thumbnail_url": f"{SERVER_BASE_URL}/outputs/{output_path.name}"}
        raise HTTPException(status_code=500, detail="Failed to download image")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get-original-url/{video_id}")
async def get_original_url(video_id: str):
    """Get original URL for AI thumbnail."""
    original_url = ai_thumbnail_original_urls.get(video_id)
    if original_url:
        return {"status": "success", "original_url": original_url}
    raise HTTPException(status_code=404, detail="Original URL not found")
