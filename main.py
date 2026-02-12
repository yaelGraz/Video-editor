# =============================================================================
# CRITICAL: Force UTF-8 encoding on Windows (prevents charmap codec errors)
# =============================================================================
import os
os.environ['PYTHONUTF8'] = '1'
import sys
if sys.platform == 'win32':
    # Force UTF-8 for stdout/stderr to prevent encoding errors in subprocess output
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# =============================================================================
# CRITICAL SSL BYPASS: Execute before ANY other imports
# =============================================================================
import ssl
import certifi

# STEP 1: Remove ALL problematic environment variables FIRST
for env_var in ['HTTPLIB2_CA_CERTS', 'REQUESTS_CA_BUNDLE', 'SSL_CERT_FILE', 'CURL_CA_BUNDLE']:
    if env_var in os.environ:
        del os.environ[env_var]

# STEP 2: Create mock httplib2.certs module BEFORE httplib2 is imported
# This prevents the RuntimeError: HTTPLIB2_CA_CERTS not a valid file
class MockCerts:
    @staticmethod
    def where():
        return certifi.where()

sys.modules['httplib2.certs'] = MockCerts

# STEP 3: Set environment variables with valid paths
_cert_path = certifi.where()
os.environ['SSL_CERT_FILE'] = _cert_path
os.environ['REQUESTS_CA_BUNDLE'] = _cert_path
os.environ['GRPC_SSL_CIPHER_SUITES'] = 'HIGH+ECDSA'
os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = _cert_path
os.environ['PYTHONHTTPSVERIFY'] = '0'

# STEP 4: Disable SSL verification at Python level
ssl._create_default_https_context = ssl._create_unverified_context

# STEP 5: Patch httplib2 if already imported
try:
    import httplib2
    httplib2.CA_CERTS = _cert_path
except ImportError:
    pass

print(f"[SSL] Environment cleaned and certificates patched via certifi: {_cert_path}")

# =============================================================================
# Now safe to import everything else
# =============================================================================
"""
Video AI Studio - FastAPI Backend
Main application with all API routes.
"""
import sys
import asyncio
import shutil
import uuid
import random
from pathlib import Path
from typing import Dict, Set, Optional

# Setup additional SSL bypass (patches for requests, httpx, etc.)
from utils.helpers import setup_ssl_bypass
setup_ssl_bypass()

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# Import services
from services.audio_service import (
    transcribe_with_groq,
    generate_voiceover_sync,
    generate_voiceover_from_srt_sync,
    generate_voiceover_elevenlabs_sync,
    get_random_music,
    list_music_library,
    download_audio_from_url,
)
from services.video_service import (
    get_video_duration,
    get_video_resolution,
    check_video_has_audio,
    merge_final_video,
    cut_viral_shorts,
    generate_thumbnail,
    generate_ai_thumbnail_image,
    download_image_from_url,
    extract_text_huggingface,
    video_planner_chat,
)
from services.text_service import (
    convert_srt_to_ass,
    fix_subtitles_with_ai,
    create_srt_from_ocr,
    extract_text_from_file,
    parse_srt_file,
    write_srt_from_entries,
)
from services.font_service import ensure_font_available
from services.marketing_service import generate_marketing_kit
from services.youtube_upload_service import upload_to_youtube
from services.facebook_publish_service import publish_to_facebook
from services.remotion_render_service import render_effects_video
from utils.config import (
    BASE_DIR,
    INPUTS_DIR,
    OUTPUTS_DIR,
    MUSIC_DIR,
    MUSIC_TEMP_DIR,
    SHORTS_DIR,
    ELEVENLABS_EMOTION_SETTINGS,
)

# =============================================================================
# App Configuration
# =============================================================================

app = FastAPI(
    title="Video AI Studio",
    description="AI-powered video editing with subtitles, voiceover, and marketing tools",
    version="2.0.0"
)

# CORS middleware - full configuration to prevent connection drops
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "Content-Range", "Content-Disposition"],
    max_age=3600,
)


# ---------------------------------------------------------------------------
# Middleware: catch Windows ConnectionResetError (WinError 10054)
# When a browser tab closes mid-transfer or cancels a fetch, Windows raises
# ConnectionResetError.  Without this middleware the traceback floods the
# terminal and can look like a crash.  We silently swallow it here.
# ---------------------------------------------------------------------------
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class CatchConnectionResetMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        try:
            return await call_next(request)
        except ConnectionResetError:
            # Client disconnected — nothing we can do, just log quietly
            print(f"[INFO] Client disconnected (ConnectionReset): {request.method} {request.url.path}")
            from starlette.responses import Response
            return Response(status_code=499)  # nginx-style "client closed"
        except OSError as e:
            # WinError 10054 and similar socket errors
            if e.winerror == 10054 if hasattr(e, 'winerror') else False:
                print(f"[INFO] Client disconnected (WinError 10054): {request.method} {request.url.path}")
                from starlette.responses import Response
                return Response(status_code=499)
            raise

app.add_middleware(CatchConnectionResetMiddleware)


# Static files
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
app.mount("/inputs", StaticFiles(directory=str(INPUTS_DIR)), name="inputs")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")  # מוזיקה ופונטים

# --- הוספה כאן (אחרי ה-mount) ---
import yt_dlp
import re
import hashlib

@app.post("/download-youtube-audio")
async def download_yt_audio(url: str = Form(...)):
    """הורדה מיוטיוב עם חילוץ לינק נקי מתוך טקסט"""
    try:
        # 1. חילוץ הלינק הנקי מתוך הטקסט (מטפל במקרה שהמשתמש הוסיף מילים)
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+(?:&\S*)?)'
        match = re.search(youtube_regex, url)

        if not match:
            print(f"[WARNING] No valid URL found in: {url}")
            return {"status": "error", "message": "לא מצאתי לינק תקין בהודעה"}

        clean_url = match.group(0)
        print(f"[INFO] YouTube download: {clean_url}")

        # 2. יצירת מזהה ייחודי לפי הלינק הנקי
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:8]
        output_filename = f"yt_{url_hash}"
        file_path = MUSIC_DIR / f"{output_filename}.mp3"

        # 3. בדיקה אם כבר קיים
        if file_path.exists():
            print(f"[INFO] YouTube cache hit: {output_filename}.mp3")
            return {
                "status": "success",
                "audioUrl": f"http://localhost:8000/assets/music/{output_filename}.mp3",
                "filename": f"{output_filename}.mp3"
            }

        # 4. הורדה — run in thread executor to avoid blocking the event loop
        #    (yt-dlp is synchronous and can take 10-30s, which causes the browser
        #     to drop the connection → WinError 10054)
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

        print(f"[INFO] YouTube downloading (async executor)...")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_download)
        print(f"[SUCCESS] YouTube download complete: {output_filename}.mp3")

        return {
            "status": "success",
            "audioUrl": f"http://localhost:8000/assets/music/{output_filename}.mp3",
            "filename": f"{output_filename}.mp3"
        }
    except ConnectionResetError:
        print(f"[INFO] YouTube download: client disconnected (10054)")
        return {"status": "error", "message": "החיבור נותק. נסה שוב."}
    except Exception as e:
        print(f"[ERROR] YouTube download failed: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.post("/download-youtube-video")
async def download_youtube_video_endpoint(url: str = Form(...)):
    """
    הורדת וידאו MP4 מלא מיוטיוב עם הודעות שגיאה מפורטות.
    הוידאו נשמר ב-OUTPUTS_DIR כדי שיהיה נגיש דרך /outputs.
    """
    try:
        # חילוץ לינק נקי באמצעות Regex
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+(?:&\S*)?)'
        match = re.search(youtube_regex, url)
        if not match:
            raise HTTPException(status_code=400, detail="הלינק שסיפקת אינו תקין. וודא שזה קישור ישיר ליוטיוב.")

        clean_url = match.group(0)
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:8]
        filename = f"yt_video_{url_hash}.mp4"
        # שמירה ב-OUTPUTS_DIR כדי שיהיה נגיש דרך /outputs endpoint
        file_path = OUTPUTS_DIR / filename

        # בדיקה אם הקובץ כבר קיים
        if file_path.exists():
            print(f"[INFO] Video already exists: {file_path}")
            return {
                "status": "success",
                "videoUrl": f"http://localhost:8000/outputs/{filename}",
                "filename": filename,
                "message": "הוידאו כבר קיים במערכת"
            }

        print(f"[INFO] Downloading video from: {clean_url}")

        # הורדה עם yt-dlp — run in executor to avoid blocking event loop
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

        # מציאת הקובץ שהורד (עשוי להיות עם סיומת שונה)
        downloaded_file = None
        for ext in ['mp4', 'webm', 'mkv']:
            check_path = OUTPUTS_DIR / f"yt_video_{url_hash}.{ext}"
            if check_path.exists():
                downloaded_file = check_path
                break

        if not downloaded_file:
            raise HTTPException(status_code=500, detail="ההורדה נכשלה - הקובץ לא נוצר")

        print(f"[SUCCESS] Video downloaded: {downloaded_file}")
        return {
            "status": "success",
            "videoUrl": f"http://localhost:8000/outputs/{downloaded_file.name}",
            "filename": downloaded_file.name,
            "title": title,
            "message": f"הוידאו '{title}' הורד בהצלחה!"
        }

    except HTTPException:
        raise
    except ConnectionResetError:
        print(f"[INFO] YouTube video download: client disconnected (10054)")
        return {"status": "error", "message": "החיבור נותק. נסה שוב."}
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] YouTube video download failed: {error_msg}")

        # הודעות שגיאה ידידותיות
        detail = "שגיאה בהורדת הוידאו מיוטיוב"
        if "Video unavailable" in error_msg or "Private video" in error_msg:
            detail = "הסרטון אינו זמין (פרטי או הוסר)"
        elif "age" in error_msg.lower():
            detail = "הסרטון מוגבל לפי גיל ולא ניתן להורדה"
        elif "Incomplete" in error_msg:
            detail = "ההורדה נקטעה. נסה שוב"
        elif "copyright" in error_msg.lower():
            detail = "הסרטון חסום עקב זכויות יוצרים"
        elif "live" in error_msg.lower():
            detail = "לא ניתן להוריד שידורים חיים"

        raise HTTPException(status_code=500, detail=detail)





# In-memory storage
ai_thumbnail_original_urls: Dict[str, str] = {}


# =============================================================================
# WebSocket Connection Manager
# =============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.progress_data: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, file_id: str):
        await websocket.accept()
        if file_id not in self.active_connections:
            self.active_connections[file_id] = set()
        self.active_connections[file_id].add(websocket)

        if file_id in self.progress_data:
            await websocket.send_json(self.progress_data[file_id])

    def disconnect(self, websocket: WebSocket, file_id: str):
        if file_id in self.active_connections:
            self.active_connections[file_id].discard(websocket)
            if not self.active_connections[file_id]:
                del self.active_connections[file_id]

    async def send_progress(self, file_id: str, progress: int, status: str, message: str = "", extra_data: dict = None):
        data = {"status": status, "progress": progress, "message": message}
        if extra_data:
            data.update(extra_data)

        self.progress_data[file_id] = data

        if file_id in self.active_connections:
            disconnected = set()
            for connection in list(self.active_connections[file_id]):
                try:
                    await connection.send_json(data)
                except Exception:
                    disconnected.add(connection)

            for ws in disconnected:
                self.active_connections[file_id].discard(ws)

            # Clean up empty connection sets to stop future attempts
            if file_id in self.active_connections and not self.active_connections[file_id]:
                del self.active_connections[file_id]

    def cleanup(self, file_id: str):
        if file_id in self.progress_data:
            del self.progress_data[file_id]
        if file_id in self.active_connections:
            del self.active_connections[file_id]


manager = ConnectionManager()

# Storage for paused tasks waiting for subtitle review confirmation
pending_tasks: Dict[str, dict] = {}


# =============================================================================
# Request/Response Models
# =============================================================================

class AIThumbnailRequest(BaseModel):
    video_id: str
    prompt: str
    title: str


class RetryDownloadRequest(BaseModel):
    video_id: str
    original_url: str
    title: Optional[str] = None


class ElevenLabsVoiceoverRequest(BaseModel):
    text: str
    emotion: str = 'neutral'
    voice_id: Optional[str] = None


class ExtractTextResponse(BaseModel):
    status: str
    text: str = ""
    error: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================

def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


# =============================================================================
# Upload Video (without processing) - for Marketing-Only flow
# =============================================================================

@app.post("/upload-video")
async def upload_video(video: UploadFile = File(...)):
    """
    מעלה סרטון לשרת ומחזיר את ה-video_id.
    משמש לפני קריאה ל-generate-marketing-only.
    """
    file_id = uuid.uuid4().hex[:8]
    suffix = Path(video.filename).suffix
    filename = f"{file_id}{suffix}"
    v_path = INPUTS_DIR / filename

    try:
        with open(v_path, "wb") as f:
            shutil.copyfileobj(video.file, f)
        print(f"[UPLOAD] Video saved: {v_path}")
        return {"status": "success", "video_id": filename}
    except Exception as e:
        print(f"[UPLOAD ERROR] {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# Marketing Endpoints (Separate for better UX)
# =============================================================================

# Cache for storing marketing data per video (to avoid re-transcribing)
marketing_cache: Dict[str, dict] = {}


@app.post("/generate-marketing-text")
async def generate_marketing_text(
    video_id: str = Form(...),
):
    """
    יוצר תוכן שיווקי טקסטואלי: כותרות, תיאור, תגיות, viral_moments.
    """
    v_path = INPUTS_DIR / video_id
    file_id = video_id.split('.')[0]
    thumb_out = OUTPUTS_DIR / f"{file_id}_thumb.jpg"

    if not v_path.exists():
        return {"status": "error", "error": "הקובץ לא נמצא בשרת."}

    try:
        print(f"[MARKETING-TEXT] Processing video: {v_path}")

        # 1) Get video info
        video_duration = get_video_duration(str(v_path))
        has_audio = check_video_has_audio(str(v_path))

        loop = asyncio.get_event_loop()
        transcript_text = ""

        # 2) Transcription
        print(f"[MARKETING-TEXT] Transcribing (has_audio={has_audio})...")
        if has_audio:
            srt_path = OUTPUTS_DIR / f"{file_id}_marketing.srt"
            success, transcript_text = await loop.run_in_executor(
                None, lambda: transcribe_with_groq(str(v_path), str(srt_path), None)
            )
            # Keep SRT for potential subtitle burning later
        else:
            transcript_text, _ = await loop.run_in_executor(
                None, lambda: extract_text_huggingface(str(v_path), None, None)
            )

        if not transcript_text:
            transcript_text = "סרטון ללא מלל מזוהה"

        print(f"[MARKETING-TEXT] Transcript length: {len(transcript_text)} chars")

        # 3) Generate marketing kit
        print(f"[MARKETING-TEXT] Generating marketing content...")
        marketing_data = await loop.run_in_executor(
            None, lambda: generate_marketing_kit(transcript_text, video_duration, None)
        )

        if not marketing_data:
            return {"status": "error", "error": "נכשל ביצירת תוכן שיווקי"}

        # 4) Generate basic thumbnail
        thumbnail_url = None
        title = marketing_data.get("titles", [""])[0] if marketing_data.get("titles") else "סרטון חדש"
        punchline = marketing_data.get("punchline", "")

        ok = await loop.run_in_executor(
            None, lambda: generate_thumbnail(str(v_path), title, str(thumb_out), None, punchline)
        )
        if ok and thumb_out.exists():
            thumbnail_url = f"http://localhost:8000/outputs/{thumb_out.name}"

        # 5) Cache for other endpoints
        marketing_cache[file_id] = {
            "marketing_data": marketing_data,
            "transcript_text": transcript_text,
            "video_duration": video_duration,
            "title": title,
            "punchline": punchline,
            "srt_path": str(OUTPUTS_DIR / f"{file_id}_marketing.srt") if has_audio else None
        }

        # 6) Format response
        marketing_kit = {
            "title": title,
            "description": marketing_data.get("facebook_post", ""),
            "tags": " ".join(marketing_data.get("hashtags", [])),
            "punchline": punchline,
            "image_prompt": marketing_data.get("image_prompt", ""),
            "viral_moments": marketing_data.get("viral_moments", []),
        }

        print(f"[MARKETING-TEXT] Success! Title: {title[:50]}...")
        return {
            "status": "success",
            "marketing_kit": marketing_kit,
            "thumbnail_url": thumbnail_url
        }

    except Exception as e:
        print(f"[MARKETING-TEXT ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@app.post("/generate-marketing-ai-image")
async def generate_marketing_ai_image(
    video_id: str = Form(...),
    custom_prompt: str = Form(None),
    provider: str = Form("leonardo"),
    netfree_mode: str = Form("false"),
):
    """
    יוצר תמונת AI באמצעות Leonardo או Gemini (Nano Banana).
    netfree_mode: "true" = save to file + return localhost URL (NetFree-safe)
    """
    is_netfree = netfree_mode.lower() == "true"
    file_id = video_id.split('.')[0]
    v_path = INPUTS_DIR / video_id

    if not v_path.exists():
        return {"status": "error", "error": "הקובץ לא נמצא בשרת."}

    try:
        # Get cached data or defaults
        cached = marketing_cache.get(file_id, {})
        marketing_data = cached.get("marketing_data", {})
        title = cached.get("title", "סרטון חדש")
        punchline = cached.get("punchline", "")

        # Determine prompt to use
        if custom_prompt and custom_prompt.strip():
            image_prompt = custom_prompt.strip()
            print(f"[MARKETING-AI-IMAGE] Using custom prompt: {image_prompt[:100]}...")
        else:
            image_prompt = marketing_data.get("image_prompt", "")
            if not image_prompt:
                return {"status": "error", "error": "אין prompt לתמונה. יש ליצור תוכן שיווקי קודם."}
            print(f"[MARKETING-AI-IMAGE] Using auto-generated prompt: {image_prompt[:100]}...")

        # Generate AI thumbnail
        ai_out = OUTPUTS_DIR / f"{file_id}_ai_thumb_{uuid.uuid4().hex[:4]}.jpg"
        loop = asyncio.get_event_loop()

        provider_name = "Nano Banana (Gemini)" if provider == "nano-banana" else "Leonardo"
        nf_label = " [NetFree]" if is_netfree else ""
        print(f"[MARKETING-AI-IMAGE] Calling {provider_name}{nf_label}...")
        success, result_data = await loop.run_in_executor(
            None, lambda: generate_ai_thumbnail_image(
                image_prompt, title, str(ai_out), None, punchline, provider, is_netfree
            )
        )

        if success:
            # Route 1: NetFree mode — file saved locally, return localhost URL for approval flow
            if is_netfree and result_data == "file" and ai_out.exists():
                local_url = f"http://localhost:8000/outputs/{ai_out.name}"
                print(f"[MARKETING-AI-IMAGE] NetFree mode: {local_url}")
                return {
                    "status": "netfree_preview",
                    "preview_url": local_url,
                    "prompt_used": image_prompt
                }
            # Route 2: Normal Nano Banana — base64 data URI
            elif result_data and isinstance(result_data, str) and result_data.startswith("data:"):
                print(f"[MARKETING-AI-IMAGE] Base64 data URI ({len(result_data) // 1024}KB)")
                return {
                    "status": "success",
                    "ai_thumbnail_url": result_data,
                    "prompt_used": image_prompt
                }
            # Route 3: Leonardo — file saved
            elif ai_out.exists():
                local_url = f"http://localhost:8000/outputs/{ai_out.name}"
                print(f"[MARKETING-AI-IMAGE] File URL: {local_url}")
                return {
                    "status": "success",
                    "ai_thumbnail_url": local_url,
                    "prompt_used": image_prompt
                }
            else:
                return {"status": "error", "error": "נכשל ביצירת תמונת AI"}
        else:
            return {"status": "error", "error": "נכשל ביצירת תמונת AI"}

    except Exception as e:
        print(f"[MARKETING-AI-IMAGE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@app.post("/generate-marketing-shorts")
async def generate_marketing_shorts(
    video_id: str = Form(...),
    with_subtitles: bool = Form(False),  # Whether to burn subtitles
    subtitle_color: str = Form(None),  # Subtitle color in hex (e.g., "#FFFF00")
):
    """
    יוצר Shorts אנכיים (9:16) מ-viral_moments.
    אם with_subtitles=True - שורף כתוביות על הסרטון.
    subtitle_color - צבע כתוביות בפורמט hex.
    """
    file_id = video_id.split('.')[0]
    v_path = INPUTS_DIR / video_id

    if not v_path.exists():
        return {"status": "error", "error": "הקובץ לא נמצא בשרת."}

    try:
        # Get cached data
        cached = marketing_cache.get(file_id, {})
        marketing_data = cached.get("marketing_data", {})
        viral_moments = marketing_data.get("viral_moments", [])
        srt_path = cached.get("srt_path")

        if not viral_moments:
            return {"status": "error", "error": "אין viral_moments. יש ליצור תוכן שיווקי קודם."}

        print(f"[MARKETING-SHORTS] Creating {len(viral_moments)} shorts (with_subtitles={with_subtitles}, color={subtitle_color})...")

        # Determine subtitle path
        subtitle_path = None
        if with_subtitles:
            if srt_path and Path(srt_path).exists():
                subtitle_path = srt_path
                print(f"[MARKETING-SHORTS] Will burn subtitles from: {subtitle_path}")
            else:
                print(f"[MARKETING-SHORTS] Warning: Subtitles requested but no SRT found")

        loop = asyncio.get_event_loop()

        shorts_paths = await loop.run_in_executor(
            None, lambda: cut_viral_shorts(
                video_path=str(v_path),
                viral_moments=viral_moments,
                output_dir=str(OUTPUTS_DIR),
                subtitle_path=subtitle_path,
                use_ass=False,
                progress_callback=None,
                vertical=True,  # 9:16 format
                subtitle_color=subtitle_color,
                with_subtitles=with_subtitles  # CRITICAL: Enable transcription + burning
            )
        )

        if shorts_paths:
            shorts_urls = [f"http://localhost:8000/outputs/shorts/{Path(p).name}" for p in shorts_paths]
            print(f"[MARKETING-SHORTS] Success! Created {len(shorts_urls)} shorts")
            return {
                "status": "success",
                "shorts_urls": shorts_urls,
                "with_subtitles": with_subtitles,
                "subtitle_color": subtitle_color
            }
        else:
            return {"status": "error", "error": "לא נוצרו קליפים"}

    except Exception as e:
        print(f"[MARKETING-SHORTS ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

def cleanup_source_file(v_path: Path, out_path: Path):
    # Keep source file for Effects Studio tab (Remotion rendering needs it)
    # Only log that we're intentionally keeping it
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[CLEANUP] Keeping source file for Effects Studio: {v_path}")
    else:
        print(f"[CLEANUP] Output not found, keeping source: {v_path}")


# =============================================================================
# Video Processing Task
# =============================================================================

async def process_video_task(
    file_id: str,
    v_path: Path,
    srt_path: Path,
    out_path: Path,
    do_music: bool,
    do_subtitles: bool,
    do_marketing: bool,
    do_shorts: bool,
    do_thumbnail: bool,
    do_styled_subtitles: bool,
    do_voiceover: bool = False,
    do_ai_thumbnail: bool = False,
    music_style: str = "calm",
    selected_music_path: Path = None,
    # Font settings from chat - defaults to clean readable font
    font_name: str = "Arial",
    font_color: str = "#FFFFFF",
    font_size: int = 24,
    music_volume: float = 0.15,
    ducking: bool = True,
):
    """Process video with all selected features."""

    print(f"[TASK] Using font: {font_name}, color: {font_color}, size: {font_size}")
    loop = asyncio.get_event_loop()
    marketing_data = None
    transcript_text = ""
    shorts_paths = []
    thumbnail_url = None
    ai_thumbnail_url = None
    voiceover_audio_path = None
    chosen_music = selected_music_path

    def progress_callback(progress: int, message: str):
        asyncio.run_coroutine_threadsafe(
            manager.send_progress(file_id, progress, "processing", message),
            loop,
        )

    try:
        await manager.send_progress(file_id, 0, "processing", "מתחיל עיבוד...")

        # 1) Video properties
        video_duration = get_video_duration(v_path)
        video_width, video_height = get_video_resolution(v_path)
        has_audio = check_video_has_audio(v_path)

        # 2) Transcription
        need_transcript = do_subtitles or do_marketing or do_voiceover

        if need_transcript:
            if has_audio:
                await manager.send_progress(file_id, 10, "processing", "מתמלל אודיו...")
                success, transcript_text = await loop.run_in_executor(
                    None, lambda: transcribe_with_groq(str(v_path), str(srt_path), progress_callback)
                )
                if not success:
                    transcript_text = ""
                else:
                    if srt_path.exists():
                        await manager.send_progress(file_id, 18, "processing", "מתקן כתוביות עם AI...")
                        await loop.run_in_executor(
                            None, lambda: fix_subtitles_with_ai(str(srt_path), progress_callback)
                        )
            else:
                # Video has no audio - extract text/subtitles using Gemini File API
                await manager.send_progress(file_id, 10, "processing", "מחלץ כתוביות מהוידאו...")
                print(f"[INFO] Starting Gemini subtitle extraction for video without audio...")
                print(f"[INFO] SRT will be saved directly to: {srt_path}")

                # Pass srt_path directly to extract_text_huggingface - it will save the file
                transcript_text, entries = await loop.run_in_executor(
                    None, lambda: extract_text_huggingface(str(v_path), progress_callback, str(srt_path))
                )
                print(f"[INFO] Gemini extraction complete: {len(entries)} entries found")

                # Verify SRT was saved successfully by the function
                if srt_path.exists() and srt_path.stat().st_size > 0:
                    print(f"[SUCCESS] SRT file verified: {srt_path} ({srt_path.stat().st_size} bytes)")
                    await manager.send_progress(file_id, 18, "processing", "מתקן כתוביות עם AI...")
                    await loop.run_in_executor(
                        None, lambda: fix_subtitles_with_ai(str(srt_path), progress_callback)
                    )
                    print(f"[INFO] SRT file ready for merge: {srt_path}")
                else:
                    print(f"[ERROR] SRT file was not created or is empty: {srt_path}")
                    if transcript_text:
                        # Fallback: try to save manually if function didn't save
                        print(f"[INFO] Attempting fallback save of {len(transcript_text)} chars...")
                        try:
                            with open(str(srt_path), 'w', encoding='utf-8') as f:
                                f.write(transcript_text)
                            print(f"[SUCCESS] Fallback save succeeded: {srt_path}")
                        except Exception as save_err:
                            print(f"[ERROR] Fallback save failed: {save_err}")

        # =====================================================================
        # SUBTITLE REVIEW PAUSE - Let user review/edit before continuing
        # =====================================================================
        if do_subtitles and srt_path.exists() and srt_path.stat().st_size > 0:
            # Debug: log SRT file content before parsing
            try:
                with open(str(srt_path), 'r', encoding='utf-8') as _dbg:
                    _srt_content = _dbg.read()
                print(f"[DEBUG] SRT file size: {len(_srt_content)} chars, first 500 chars:\n{_srt_content[:500]}")
                # Check for line ending issues
                cr_count = _srt_content.count('\r')
                lf_count = _srt_content.count('\n')
                print(f"[DEBUG] SRT line endings: \\r count={cr_count}, \\n count={lf_count}")
            except Exception as _dbg_err:
                print(f"[DEBUG] Could not read SRT for debug: {_dbg_err}")

            # Read SRT entries for review
            srt_entries = parse_srt_file(str(srt_path))

            if srt_entries:
                print(f"[SUBTITLE REVIEW] Pausing for user review. {len(srt_entries)} entries found.")
                print(f"[SUBTITLE REVIEW] First entry: {srt_entries[0]}")
                if len(srt_entries) > 1:
                    print(f"[SUBTITLE REVIEW] Last entry: {srt_entries[-1]}")

                # Store task state for resumption
                pending_tasks[file_id] = {
                    "v_path": v_path,
                    "srt_path": srt_path,
                    "out_path": out_path,
                    "do_music": do_music,
                    "do_subtitles": do_subtitles,
                    "do_marketing": do_marketing,
                    "do_shorts": do_shorts,
                    "do_thumbnail": do_thumbnail,
                    "do_styled_subtitles": do_styled_subtitles,
                    "do_voiceover": do_voiceover,
                    "do_ai_thumbnail": do_ai_thumbnail,
                    "music_style": music_style,
                    "selected_music_path": selected_music_path,
                    "font_name": font_name,
                    "font_color": font_color,
                    "font_size": font_size,
                    "music_volume": music_volume,
                    "ducking": ducking,
                    "transcript_text": transcript_text,
                    "video_duration": video_duration,
                    "video_width": video_width,
                    "video_height": video_height,
                    "has_audio": has_audio,
                }

                # Send subtitles for review and PAUSE
                print(f"[SUBTITLE REVIEW] Sending {len(srt_entries)} entries via WebSocket for file_id={file_id}")
                await manager.send_progress(
                    file_id, 20, "subtitle_review",
                    "כתוביות מוכנות לעריכה",
                    {"subtitles": srt_entries, "total_entries": len(srt_entries)}
                )
                print(f"[SUBTITLE REVIEW] WebSocket message sent successfully")

                # Exit task - will resume when user confirms via /continue-processing
                return

        # 3) Marketing + Music
        if do_marketing and transcript_text:
            await manager.send_progress(file_id, 25, "processing", "יוצר ערכת שיווק...")
            marketing_data = await loop.run_in_executor(
                None, lambda: generate_marketing_kit(transcript_text, video_duration, progress_callback)
            )
            if marketing_data and do_music and not chosen_music:
                auto_style = marketing_data.get("music_style", music_style)
                chosen_music = get_random_music(auto_style, str(MUSIC_DIR))

        if do_music and not chosen_music:
            chosen_music = get_random_music(music_style, str(MUSIC_DIR))
            if not chosen_music:
                all_music = list(MUSIC_DIR.glob("*.mp3"))
                if all_music:
                    chosen_music = random.choice(all_music)

        # 4) ASS subtitles - with custom font from chat
        subtitle_path = srt_path
        use_ass = False
        if do_styled_subtitles and do_subtitles and srt_path.exists():
            ass_path = OUTPUTS_DIR / f"{file_id}.ass"
            await manager.send_progress(file_id, 40, "processing", "בודק ומוריד גופן...")

            # Ensure font is available locally (downloads from Google Fonts if needed)
            _font = await loop.run_in_executor(None, ensure_font_available, font_name)

            await manager.send_progress(file_id, 42, "processing", "ממיר לכתוביות מעוצבות...")

            # CRITICAL: Capture values for lambda to avoid closure issues
            _srt = str(srt_path)
            _ass = str(ass_path)
            _width = video_width
            _height = video_height
            _color = font_color
            _size = font_size

            print(f"\n{'='*60}")
            print(f"[TASK] === FONT SETTINGS FOR ASS ===")
            print(f"[TASK] font_name: '{_font}'")
            print(f"[TASK] font_color: '{_color}'")
            print(f"[TASK] font_size: {_size}")
            print(f"{'='*60}\n")

            ok = await loop.run_in_executor(
                None, lambda: convert_srt_to_ass(
                    _srt, _ass, _width, _height,
                    font_name=_font,
                    font_color=_color,
                    font_size=_size
                )
            )
            if ok:
                subtitle_path = ass_path
                use_ass = True
                # Verify the ASS file contains the correct font
                try:
                    with open(ass_path, 'r', encoding='utf-8') as f:
                        ass_content = f.read()
                        if _font in ass_content:
                            print(f"[SUCCESS] ASS file contains font: {_font}")
                        else:
                            print(f"[WARNING] ASS file does NOT contain font: {_font}")
                            print(f"[DEBUG] ASS Style line: {[l for l in ass_content.split(chr(10)) if 'Style:' in l]}")
                except Exception as e:
                    print(f"[ERROR] Could not verify ASS file: {e}")

        # 5) Voiceover
        if do_voiceover and srt_path.exists():
            await manager.send_progress(file_id, 55, "processing", "מייצר קריינות...")
            voiceover_audio_path = OUTPUTS_DIR / f"{file_id}_voiceover.mp3"
            ok = await loop.run_in_executor(
                None,
                lambda: generate_voiceover_from_srt_sync(
                    str(srt_path), str(voiceover_audio_path), video_duration, progress_callback
                ),
            )
            if not ok:
                voiceover_audio_path = None

        # 6) Final merge - IMPORTANT: Ensure subtitle file is ready before merge
        await manager.send_progress(file_id, 75, "processing", "ממזג את כל הערוצים...")

        # Debug: Print ALL relevant status
        print(f"\n{'='*60}")
        print(f"[DEBUG] === SUBTITLE PATH CHECK ===")
        print(f"[DEBUG] do_subtitles (param): {do_subtitles}")
        print(f"[DEBUG] do_styled_subtitles: {do_styled_subtitles}")
        print(f"[DEBUG] use_ass: {use_ass}")
        print(f"[DEBUG] subtitle_path: {subtitle_path}")
        print(f"[DEBUG] subtitle_path exists: {subtitle_path.exists() if subtitle_path else 'N/A'}")
        print(f"[DEBUG] srt_path: {srt_path}")
        print(f"[DEBUG] srt_path exists: {srt_path.exists()}")
        if srt_path.exists():
            srt_size = os.path.getsize(str(srt_path))
            print(f"[DEBUG] srt_path size: {srt_size} bytes")
        ass_path = OUTPUTS_DIR / f"{file_id}.ass"
        print(f"[DEBUG] ass_path: {ass_path}")
        print(f"[DEBUG] ass_path exists: {ass_path.exists()}")
        if ass_path.exists():
            ass_size = os.path.getsize(str(ass_path))
            print(f"[DEBUG] ass_path size: {ass_size} bytes")
        print(f"{'='*60}\n")

        # Verify subtitle file exists if subtitles are enabled
        final_subtitle_path = None
        if do_subtitles and subtitle_path and subtitle_path.exists():
            file_size = os.path.getsize(str(subtitle_path))
            print(f"[INFO] Subtitle file found: {subtitle_path} ({file_size} bytes)")

            if file_size > 0:
                final_subtitle_path = str(subtitle_path)
                print(f"[SUCCESS] Using subtitle file for merge: {final_subtitle_path}")
            else:
                print(f"[WARNING] Subtitle file is empty, skipping subtitles")
        elif do_subtitles:
            print(f"[WARNING] Subtitles requested but file not found: {subtitle_path}")
            # Try the original srt_path as fallback
            if srt_path.exists() and os.path.getsize(str(srt_path)) > 0:
                final_subtitle_path = str(srt_path)
                print(f"[INFO] Using fallback SRT path: {final_subtitle_path}")

        print(f"[DEBUG] final_subtitle_path for merge: {final_subtitle_path}")

        merge_success = await loop.run_in_executor(
            None,
            lambda: merge_final_video(
                v_input=str(v_path),
                srt_input=final_subtitle_path,
                v_output=str(out_path),
                music_path=str(chosen_music) if chosen_music else None,
                voice_path=str(voiceover_audio_path) if voiceover_audio_path else None
            ),
        )

        if not merge_success or not out_path.exists():
            raise RuntimeError("FFmpeg merge failed - קובץ פלט לא נוצר")

        # 7) Shorts
        if do_shorts and marketing_data and marketing_data.get("viral_moments"):
            await manager.send_progress(file_id, 82, "processing", "חותך קליפים...")
            shorts_subtitle_path = str(subtitle_path) if (do_subtitles and subtitle_path.exists()) else None
            shorts_paths = await loop.run_in_executor(
                None,
                lambda: cut_viral_shorts(
                    str(v_path),
                    marketing_data["viral_moments"],
                    str(OUTPUTS_DIR),
                    subtitle_path=shorts_subtitle_path,
                    use_ass=use_ass,
                    progress_callback=progress_callback,
                ),
            )

        # 8) Thumbnail
        if do_thumbnail and marketing_data and marketing_data.get("titles"):
            await manager.send_progress(file_id, 88, "processing", "יוצר תמונה ממוזערת...")
            thumb_out = OUTPUTS_DIR / f"{file_id}_thumbnail.jpg"
            title = marketing_data["titles"][0]
            punchline = marketing_data.get("punchline")
            ok = await loop.run_in_executor(
                None, lambda: generate_thumbnail(str(v_path), title, str(thumb_out), progress_callback, punchline)
            )
            if ok and thumb_out.exists():
                thumbnail_url = f"http://localhost:8000/outputs/{thumb_out.name}"

        # 9) AI Thumbnail
        if do_ai_thumbnail and marketing_data:
            await manager.send_progress(file_id, 92, "processing", "יוצר תמונת AI...")
            ai_out = OUTPUTS_DIR / f"{file_id}_ai_thumbnail.jpg"
            title = marketing_data["titles"][0] if marketing_data.get("titles") else "סרטון וידאו"
            punchline = marketing_data.get("punchline")
            image_prompt = marketing_data.get("image_prompt", "Cinematic scene, dramatic lighting")
            result = await loop.run_in_executor(
                None, lambda: generate_ai_thumbnail_image(image_prompt, title, str(ai_out), progress_callback, punchline)
            )
            if isinstance(result, tuple):
                ok, original_url = result
            else:
                ok, original_url = result, None

            if ok and ai_out.exists():
                ai_thumbnail_url = f"http://localhost:8000/outputs/{ai_out.name}"
                if original_url:
                    ai_thumbnail_original_urls[file_id] = original_url

        # Build result
        result_data = {"download_url": f"http://localhost:8000/outputs/{out_path.name}"}
        result_data["file_id"] = file_id
        if chosen_music:
            result_data["music_url"] = f"http://localhost:8000/assets/music/{Path(str(chosen_music)).name}"
        if marketing_data:
            result_data["marketing_kit"] = marketing_data
        if shorts_paths:
            result_data["shorts"] = [f"http://localhost:8000/outputs/shorts/{Path(p).name}" for p in shorts_paths]
        if thumbnail_url:
            result_data["thumbnail"] = thumbnail_url
        if ai_thumbnail_url:
            result_data["ai_thumbnail"] = ai_thumbnail_url
            result_data["ai_thumbnail_original_url"] = ai_thumbnail_original_urls.get(file_id)
        if voiceover_audio_path and Path(voiceover_audio_path).exists():
            result_data["voiceover"] = f"http://localhost:8000/outputs/{Path(voiceover_audio_path).name}"

        print(f"[INFO] Results for {file_id}: {list(result_data.keys())}")
        await manager.send_progress(file_id, 100, "completed", result_data["download_url"], result_data)
        cleanup_source_file(v_path, out_path)

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        await manager.send_progress(file_id, 100, "error", f"שגיאה: {str(e)}")


# =============================================================================
# API Routes
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


# =============================================================================
# Subtitle Review Endpoints
# =============================================================================

class SubtitleEntry(BaseModel):
    index: int
    start: float
    end: float
    text: str


class UpdateSubtitlesRequest(BaseModel):
    subtitles: list[dict]


@app.post("/update-subtitles/{file_id}")
async def update_subtitles(file_id: str, request: UpdateSubtitlesRequest):
    """
    Save user-edited subtitles to SRT file.
    Called when user edits subtitles in the review panel.
    """
    srt_path = OUTPUTS_DIR / f"{file_id}.srt"

    try:
        # Convert to list of dicts for write_srt_from_entries
        entries = []
        for i, sub in enumerate(request.subtitles):
            entries.append({
                'index': i + 1,
                'start': sub.get('start', 0),
                'end': sub.get('end', 0),
                'text': sub.get('text', '')
            })

        write_srt_from_entries(entries, str(srt_path))
        print(f"[SUBTITLE UPDATE] Saved {len(entries)} edited entries to {srt_path}")

        return {"status": "success", "message": f"Saved {len(entries)} subtitles"}

    except Exception as e:
        print(f"[ERROR] Failed to update subtitles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/continue-processing/{file_id}")
async def continue_processing(file_id: str, background_tasks: BackgroundTasks):
    """
    Resume video processing after subtitle review.
    Called when user clicks 'Confirm and Continue' or 'Skip'.
    """
    if file_id not in pending_tasks:
        raise HTTPException(status_code=404, detail="No pending task found for this file_id")

    task_data = pending_tasks.pop(file_id)
    print(f"[CONTINUE] Resuming processing for {file_id}")

    # Resume processing from step 3 onwards
    background_tasks.add_task(
        continue_video_task,
        file_id,
        **task_data
    )

    return {"status": "resuming", "message": "Processing resumed"}


async def continue_video_task(
    file_id: str,
    v_path: Path,
    srt_path: Path,
    out_path: Path,
    do_music: bool,
    do_subtitles: bool,
    do_marketing: bool,
    do_shorts: bool,
    do_thumbnail: bool,
    do_styled_subtitles: bool,
    do_voiceover: bool,
    do_ai_thumbnail: bool,
    music_style: str,
    selected_music_path: Path,
    font_name: str,
    font_color: str,
    font_size: int,
    music_volume: float,
    ducking: bool,
    transcript_text: str,
    video_duration: float,
    video_width: int,
    video_height: int,
    has_audio: bool,
):
    """
    Continue video processing after subtitle review.
    Picks up from step 3 (Marketing + Music) onwards.
    """
    loop = asyncio.get_event_loop()
    marketing_data = None
    shorts_paths = []
    thumbnail_url = None
    ai_thumbnail_url = None
    voiceover_audio_path = None
    chosen_music = selected_music_path

    def progress_callback(progress: int, message: str):
        asyncio.run_coroutine_threadsafe(
            manager.send_progress(file_id, progress, "processing", message),
            loop,
        )

    try:
        await manager.send_progress(file_id, 22, "processing", "ממשיך בעיבוד...")

        # === DEBUG: Check subtitle file state ===
        print(f"[CONTINUE-DEBUG] srt_path = {srt_path}")
        print(f"[CONTINUE-DEBUG] srt_path.exists() = {srt_path.exists()}")
        if srt_path.exists():
            srt_size = srt_path.stat().st_size
            print(f"[CONTINUE-DEBUG] srt file size = {srt_size} bytes")
            with open(str(srt_path), 'r', encoding='utf-8') as _f:
                _first = _f.read(300)
            print(f"[CONTINUE-DEBUG] srt first 300 chars: {_first}")
        else:
            print(f"[CONTINUE-DEBUG] *** SRT FILE DOES NOT EXIST! ***")
        print(f"[CONTINUE-DEBUG] do_subtitles={do_subtitles}, do_styled_subtitles={do_styled_subtitles}")
        print(f"[CONTINUE-DEBUG] v_path={v_path}, v_path.exists()={v_path.exists()}")
        print(f"[CONTINUE-DEBUG] font_name={font_name}, font_color={font_color}, font_size={font_size}")

        # 3) Marketing + Music
        if do_marketing and transcript_text:
            await manager.send_progress(file_id, 25, "processing", "יוצר ערכת שיווק...")
            marketing_data = await loop.run_in_executor(
                None, lambda: generate_marketing_kit(transcript_text, video_duration, progress_callback)
            )
            if marketing_data and do_music and not chosen_music:
                auto_style = marketing_data.get("music_style", music_style)
                chosen_music = get_random_music(auto_style, str(MUSIC_DIR))

        if do_music and not chosen_music:
            chosen_music = get_random_music(music_style, str(MUSIC_DIR))
            if not chosen_music:
                all_music = list(MUSIC_DIR.glob("*.mp3"))
                if all_music:
                    chosen_music = random.choice(all_music)

        # 4) ASS subtitles - with custom font from chat
        subtitle_path = srt_path
        use_ass = False
        print(f"[CONTINUE-DEBUG] Step 4: do_styled_subtitles={do_styled_subtitles}, do_subtitles={do_subtitles}, srt exists={srt_path.exists()}")
        if do_styled_subtitles and do_subtitles and srt_path.exists():
            ass_path = OUTPUTS_DIR / f"{file_id}.ass"
            await manager.send_progress(file_id, 40, "processing", "בודק ומוריד גופן...")

            # Ensure font is available locally (downloads from Google Fonts if needed)
            _font = await loop.run_in_executor(None, ensure_font_available, font_name)

            await manager.send_progress(file_id, 42, "processing", "ממיר לכתוביות מעוצבות...")

            _srt = str(srt_path)
            _ass = str(ass_path)
            _width = video_width
            _height = video_height
            _color = font_color
            _size = font_size

            ok = await loop.run_in_executor(
                None, lambda: convert_srt_to_ass(
                    _srt, _ass, _width, _height,
                    font_name=_font,
                    font_color=_color,
                    font_size=_size
                )
            )
            print(f"[CONTINUE-DEBUG] ASS conversion result: ok={ok}, ass exists={ass_path.exists()}")
            if ok:
                subtitle_path = ass_path
                use_ass = True
                print(f"[CONTINUE-DEBUG] Using ASS: {ass_path}")
        else:
            print(f"[CONTINUE-DEBUG] SKIPPED ASS conversion!")

        # 5) Voiceover
        if do_voiceover and srt_path.exists():
            await manager.send_progress(file_id, 55, "processing", "מייצר קריינות...")
            voiceover_audio_path = OUTPUTS_DIR / f"{file_id}_voiceover.mp3"
            ok = await loop.run_in_executor(
                None,
                lambda: generate_voiceover_from_srt_sync(
                    str(srt_path), str(voiceover_audio_path), video_duration, progress_callback
                ),
            )
            if not ok:
                voiceover_audio_path = None

        # 6) Final merge
        await manager.send_progress(file_id, 75, "processing", "ממזג את כל הערוצים...")

        final_subtitle_path = None
        if do_subtitles and subtitle_path and subtitle_path.exists():
            file_size = os.path.getsize(str(subtitle_path))
            if file_size > 0:
                final_subtitle_path = str(subtitle_path)

        print(f"[CONTINUE-DEBUG] Step 6 MERGE:")
        print(f"[CONTINUE-DEBUG]   subtitle_path = {subtitle_path}")
        print(f"[CONTINUE-DEBUG]   final_subtitle_path = {final_subtitle_path}")
        print(f"[CONTINUE-DEBUG]   v_path = {v_path} (exists={v_path.exists()})")
        print(f"[CONTINUE-DEBUG]   chosen_music = {chosen_music}")

        merge_success = await loop.run_in_executor(
            None,
            lambda: merge_final_video(
                v_input=str(v_path),
                srt_input=final_subtitle_path,
                v_output=str(out_path),
                music_path=str(chosen_music) if chosen_music else None,
                voice_path=str(voiceover_audio_path) if voiceover_audio_path else None
            ),
        )
        print(f"[CONTINUE-DEBUG] merge_success = {merge_success}, out_path exists = {out_path.exists()}")

        if not merge_success or not out_path.exists():
            raise RuntimeError("FFmpeg merge failed - קובץ פלט לא נוצר")

        # 7) Shorts
        if do_shorts and marketing_data and marketing_data.get("viral_moments"):
            await manager.send_progress(file_id, 82, "processing", "חותך קליפים...")
            shorts_subtitle_path = str(subtitle_path) if (do_subtitles and subtitle_path.exists()) else None
            shorts_paths = await loop.run_in_executor(
                None,
                lambda: cut_viral_shorts(
                    str(v_path),
                    marketing_data["viral_moments"],
                    str(OUTPUTS_DIR),
                    subtitle_path=shorts_subtitle_path,
                    use_ass=use_ass,
                    progress_callback=progress_callback,
                ),
            )

        # 8) Thumbnail
        if do_thumbnail and marketing_data and marketing_data.get("titles"):
            await manager.send_progress(file_id, 88, "processing", "יוצר תמונה ממוזערת...")
            thumb_out = OUTPUTS_DIR / f"{file_id}_thumbnail.jpg"
            title = marketing_data["titles"][0]
            punchline = marketing_data.get("punchline")
            ok = await loop.run_in_executor(
                None, lambda: generate_thumbnail(str(v_path), title, str(thumb_out), progress_callback, punchline)
            )
            if ok and thumb_out.exists():
                thumbnail_url = f"http://localhost:8000/outputs/{thumb_out.name}"

        # 9) AI Thumbnail
        if do_ai_thumbnail and marketing_data:
            await manager.send_progress(file_id, 92, "processing", "יוצר תמונת AI...")
            ai_out = OUTPUTS_DIR / f"{file_id}_ai_thumbnail.jpg"
            title = marketing_data["titles"][0] if marketing_data.get("titles") else "סרטון וידאו"
            punchline = marketing_data.get("punchline")
            image_prompt = marketing_data.get("image_prompt", "Cinematic scene, dramatic lighting")
            result = await loop.run_in_executor(
                None, lambda: generate_ai_thumbnail_image(image_prompt, title, str(ai_out), progress_callback, punchline)
            )
            if isinstance(result, tuple):
                ok, original_url = result
            else:
                ok, original_url = result, None

            if ok and ai_out.exists():
                ai_thumbnail_url = f"http://localhost:8000/outputs/{ai_out.name}"
                if original_url:
                    ai_thumbnail_original_urls[file_id] = original_url

        # Build result
        result_data = {"download_url": f"http://localhost:8000/outputs/{out_path.name}"}
        result_data["file_id"] = file_id
        if chosen_music:
            result_data["music_url"] = f"http://localhost:8000/assets/music/{Path(str(chosen_music)).name}"
        if marketing_data:
            result_data["marketing_kit"] = marketing_data
        if shorts_paths:
            result_data["shorts"] = [f"http://localhost:8000/outputs/shorts/{Path(p).name}" for p in shorts_paths]
        if thumbnail_url:
            result_data["thumbnail"] = thumbnail_url
        if ai_thumbnail_url:
            result_data["ai_thumbnail"] = ai_thumbnail_url
            result_data["ai_thumbnail_original_url"] = ai_thumbnail_original_urls.get(file_id)
        if voiceover_audio_path and Path(voiceover_audio_path).exists():
            result_data["voiceover"] = f"http://localhost:8000/outputs/{Path(voiceover_audio_path).name}"

        print(f"[INFO] Results for {file_id}: {list(result_data.keys())}")
        await manager.send_progress(file_id, 100, "completed", result_data["download_url"], result_data)
        cleanup_source_file(v_path, out_path)

    except Exception as e:
        print(f"[ERROR] Continue processing failed: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_progress(file_id, 100, "error", f"שגיאה: {str(e)}")


# =============================================================================
# Frontend Settings Sync Endpoint
# =============================================================================

class UpdateSettingsRequest(BaseModel):
    font: Optional[str] = None
    fontUrl: Optional[str] = None
    fontColor: Optional[str] = None
    fontSize: Optional[int] = None
    subtitleText: Optional[str] = None
    timestamp: Optional[int] = None


@app.post("/update-settings")
async def update_settings(request: UpdateSettingsRequest):
    """
    Receive font/style settings from frontend.
    Logs the update and can be extended to store settings per session.
    """
    print(f"[SETTINGS] Received font update: font={request.font}, fontUrl={request.fontUrl}")

    # Log all received settings
    settings_dict = request.model_dump(exclude_none=True)
    print(f"[SETTINGS] Full settings: {settings_dict}")

    return {
        "status": "success",
        "message": "Settings received",
        "received": settings_dict
    }


# =============================================================================
# User Library - Persistent 3-Slot Audio Storage
# =============================================================================

import json

# Path for storing user library data
USER_LIBRARY_FILE = BASE_DIR / "user_library.json"
USER_LIBRARY_DIR = MUSIC_DIR / "user_library"

# Ensure user library directory exists
USER_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def load_user_library() -> dict:
    """Load user library from JSON file."""
    default_library = {
        "slots": [
            {"id": 0, "filename": None, "filepath": None, "displayName": None},
            {"id": 1, "filename": None, "filepath": None, "displayName": None},
            {"id": 2, "filename": None, "filepath": None, "displayName": None}
        ]
    }

    if USER_LIBRARY_FILE.exists():
        try:
            with open(USER_LIBRARY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Validate slots exist and have correct structure
                if "slots" in data and len(data["slots"]) == 3:
                    return data
        except Exception as e:
            print(f"[LIBRARY] Error loading library: {e}")

    return default_library


def save_user_library(library: dict):
    """Save user library to JSON file."""
    try:
        with open(USER_LIBRARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(library, f, ensure_ascii=False, indent=2)
        print(f"[LIBRARY] Saved library to {USER_LIBRARY_FILE}")
    except Exception as e:
        print(f"[LIBRARY] Error saving library: {e}")


@app.get("/user-library")
async def get_user_library():
    """
    Get the user's 3-slot music library.
    Returns slot info with URLs for playback.
    """
    library = load_user_library()

    # Add URLs for existing files
    for slot in library["slots"]:
        if slot["filepath"]:
            filepath = Path(slot["filepath"])
            if filepath.exists():
                slot["url"] = f"http://localhost:8000/assets/music/user_library/{filepath.name}"
            else:
                # File no longer exists, clear the slot
                slot["filename"] = None
                slot["filepath"] = None
                slot["displayName"] = None
                slot["url"] = None
        else:
            slot["url"] = None

    return {"status": "success", "library": library}


class LibrarySlotUpdate(BaseModel):
    slot_id: int
    filename: Optional[str] = None
    displayName: Optional[str] = None


@app.put("/user-library/{slot_id}")
async def update_library_slot(slot_id: int, update: LibrarySlotUpdate):
    """
    Update metadata for a library slot (e.g., displayName).
    Does not change the audio file itself.
    """
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        library = load_user_library()
        slot = library["slots"][slot_id]

        if not slot.get("filepath"):
            raise HTTPException(status_code=400, detail="Slot is empty. Upload a file first.")

        # Update displayName if provided
        if update.displayName:
            slot["displayName"] = update.displayName[:30]  # Truncate to 30 chars

        save_user_library(library)

        # Build response with URL
        url = None
        if slot.get("filepath"):
            filepath = Path(slot["filepath"])
            if filepath.exists():
                url = f"http://localhost:8000/assets/music/user_library/{filepath.name}"

        return {
            "status": "success",
            "slot": {
                "id": slot_id,
                "filename": slot.get("filename"),
                "displayName": slot.get("displayName"),
                "url": url
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY] Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/user-library/save-from-library/{slot_id}")
async def save_from_main_library(slot_id: int, filename: str = Form(...)):
    """
    Copy a music file from the main music library to a user library slot.
    This allows users to "save" tracks they like from the general library.
    """
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        # Find source file in main music library
        source_path = MUSIC_DIR / filename
        if not source_path.exists():
            raise HTTPException(status_code=404, detail=f"Music file not found: {filename}")

        # Generate unique filename for user library
        file_ext = source_path.suffix.lower()
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = f"slot{slot_id}_{unique_id}{file_ext}"
        dest_path = USER_LIBRARY_DIR / safe_filename

        # Load current library
        library = load_user_library()

        # Delete old file if exists in this slot
        old_filepath = library["slots"][slot_id].get("filepath")
        if old_filepath:
            old_path = Path(old_filepath)
            if old_path.exists():
                try:
                    old_path.unlink()
                    print(f"[LIBRARY] Deleted old file: {old_path}")
                except Exception as e:
                    print(f"[LIBRARY] Could not delete old file: {e}")

        # Copy file to user library
        shutil.copy2(source_path, dest_path)

        # Update library
        display_name = source_path.stem[:30]  # Use original name without extension

        library["slots"][slot_id] = {
            "id": slot_id,
            "filename": safe_filename,
            "filepath": str(dest_path),
            "displayName": display_name,
            "originalName": filename
        }

        save_user_library(library)

        url = f"http://localhost:8000/assets/music/user_library/{safe_filename}"

        print(f"[LIBRARY] Copied {filename} to slot {slot_id}: {safe_filename}")

        return {
            "status": "success",
            "slot": {
                "id": slot_id,
                "filename": safe_filename,
                "displayName": display_name,
                "url": url
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY] Copy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/user-library/upload/{slot_id}")
async def upload_to_library_slot(
    slot_id: int,
    file: UploadFile = File(...)
):
    """
    Upload an audio file to a specific library slot (0, 1, or 2).
    Replaces any existing file in that slot.
    """
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        # Generate unique filename
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ['.mp3', '.wav', '.ogg', '.m4a', '.aac']:
            raise HTTPException(status_code=400, detail="Invalid audio format")

        unique_id = str(uuid.uuid4())[:8]
        safe_filename = f"slot{slot_id}_{unique_id}{file_ext}"
        filepath = USER_LIBRARY_DIR / safe_filename

        # Load current library
        library = load_user_library()

        # Delete old file if exists
        old_filepath = library["slots"][slot_id].get("filepath")
        if old_filepath:
            old_path = Path(old_filepath)
            if old_path.exists():
                try:
                    old_path.unlink()
                    print(f"[LIBRARY] Deleted old file: {old_path}")
                except Exception as e:
                    print(f"[LIBRARY] Could not delete old file: {e}")

        # Save new file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update library
        original_name = file.filename
        display_name = Path(original_name).stem[:30]  # Truncate display name

        library["slots"][slot_id] = {
            "id": slot_id,
            "filename": safe_filename,
            "filepath": str(filepath),
            "displayName": display_name,
            "originalName": original_name
        }

        save_user_library(library)

        url = f"http://localhost:8000/assets/music/user_library/{safe_filename}"

        print(f"[LIBRARY] Uploaded to slot {slot_id}: {safe_filename}")

        return {
            "status": "success",
            "slot": {
                "id": slot_id,
                "filename": safe_filename,
                "displayName": display_name,
                "url": url
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY] Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/user-library/{slot_id}")
async def clear_library_slot(slot_id: int):
    """Clear a specific library slot."""
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id")

    try:
        library = load_user_library()

        # Delete file if exists
        filepath = library["slots"][slot_id].get("filepath")
        if filepath:
            path = Path(filepath)
            if path.exists():
                path.unlink()

        # Clear slot
        library["slots"][slot_id] = {
            "id": slot_id,
            "filename": None,
            "filepath": None,
            "displayName": None
        }

        save_user_library(library)

        return {"status": "success", "message": f"Slot {slot_id} cleared"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/user-library/save-from-url/{slot_id}")
async def save_from_url_to_library(
    slot_id: int,
    url: str = Form(...),
    displayName: str = Form("")
):
    """
    Download audio from YouTube URL and save directly to a library slot.
    Combines download + save in one step for convenience.
    """
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        # Extract clean YouTube URL
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+(?:&\S*)?)'
        match = re.search(youtube_regex, url)

        if not match:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        clean_url = match.group(0)
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:8]

        # Download to user library directory directly
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"slot{slot_id}_{url_hash}_{unique_id}"
        output_template = str(USER_LIBRARY_DIR / output_filename)

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True
        }

        # Get video title for display name
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            video_title = info.get('title', 'YouTube Audio')[:30]

        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([clean_url])

        # Find the downloaded file
        final_filename = f"{output_filename}.mp3"
        final_path = USER_LIBRARY_DIR / final_filename

        if not final_path.exists():
            raise HTTPException(status_code=500, detail="Download failed - file not created")

        # Load and update library
        library = load_user_library()

        # Delete old file if exists
        old_filepath = library["slots"][slot_id].get("filepath")
        if old_filepath:
            old_path = Path(old_filepath)
            if old_path.exists():
                try:
                    old_path.unlink()
                except:
                    pass

        # Use provided displayName or video title
        final_display_name = displayName[:30] if displayName else video_title

        library["slots"][slot_id] = {
            "id": slot_id,
            "filename": final_filename,
            "filepath": str(final_path),
            "displayName": final_display_name,
            "originalName": video_title,
            "sourceUrl": clean_url
        }

        save_user_library(library)

        file_url = f"http://localhost:8000/assets/music/user_library/{final_filename}"

        print(f"[LIBRARY] Downloaded YouTube to slot {slot_id}: {final_filename}")

        return {
            "status": "success",
            "slot": {
                "id": slot_id,
                "filename": final_filename,
                "displayName": final_display_name,
                "url": file_url
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY] YouTube download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/music-library")
async def get_music_library():
    """Get list of available music files in the library."""
    try:
        music_files = list_music_library(str(MUSIC_DIR))
        return {"status": "success", "music_files": music_files}
    except Exception as e:
        return {"status": "error", "message": str(e), "music_files": []}


@app.get("/emotion-presets")
async def get_emotion_presets():
    """Get available emotion presets for ElevenLabs voiceover."""
    return {
        "status": "success",
        "presets": list(ELEVENLABS_EMOTION_SETTINGS.keys())
    }


@app.websocket("/ws/progress/{file_id}")
async def websocket_progress(websocket: WebSocket, file_id: str):
    """WebSocket endpoint for progress updates."""
    await manager.connect(websocket, file_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, file_id)
    except Exception:
        manager.disconnect(websocket, file_id)


@app.post("/process")
async def process_video_api(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    music_file: Optional[UploadFile] = File(None),
    do_subtitles: str = Form("true"),  # Default TRUE - subtitles should be on by default
    do_music: str = Form("true"),
    music_style: str = Form("calm"),
    music_source: str = Form("auto"),
    music_library_file: str = Form(""),
    music_url: str = Form(""),
    do_marketing: str = Form("true"),  # Default TRUE for marketing
    do_shorts: str = Form("false"),
    do_thumbnail: str = Form("true"),  # Default TRUE for thumbnail
    do_styled_subtitles: str = Form("true"),  # Default TRUE - styled subtitles
    do_voiceover: str = Form("false"),
    do_ai_thumbnail: str = Form("false"),
    # Font settings from chat - defaults to clean readable font
    font_name: str = Form("Arial"),
    font_color: str = Form("#FFFFFF"),
    font_size: str = Form("24"),
    music_volume: str = Form("0.15"),
    ducking: str = Form("true"),
):
    """Main video processing endpoint."""
    do_subtitles_bool = parse_bool(do_subtitles)
    do_music_bool = parse_bool(do_music)
    do_marketing_bool = parse_bool(do_marketing)
    do_shorts_bool = parse_bool(do_shorts)
    do_thumbnail_bool = parse_bool(do_thumbnail)
    do_styled_subtitles_bool = parse_bool(do_styled_subtitles)
    do_voiceover_bool = parse_bool(do_voiceover)
    do_ai_thumbnail_bool = parse_bool(do_ai_thumbnail)
    ducking_bool = parse_bool(ducking)

    # Parse numeric values
    try:
        font_size_int = int(font_size)
    except:
        font_size_int = 24

    try:
        music_volume_float = float(music_volume)
    except:
        music_volume_float = 0.15

    # Log received settings from chat - DETAILED
    print(f"\n{'='*60}")
    print(f"[PROCESS] === RECEIVED SETTINGS FROM FRONTEND ===")
    print(f"[PROCESS] FONT NAME: '{font_name}'")
    print(f"[PROCESS] FONT COLOR: '{font_color}'")
    print(f"[PROCESS] FONT SIZE: {font_size_int}")
    print(f"[PROCESS] do_subtitles: {do_subtitles_bool}")
    print(f"[PROCESS] do_styled_subtitles: {do_styled_subtitles_bool}")
    print(f"[PROCESS] Music Source: {music_source}, Library File: {music_library_file}")
    print(f"[PROCESS] Music Volume: {music_volume_float}, Ducking: {ducking_bool}")
    print(f"{'='*60}\n")

    file_id = str(uuid.uuid4())[:8]
    v_path = INPUTS_DIR / f"{file_id}.mp4"

    try:
        with open(v_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
    except Exception as e:
        return {"error": f"Failed to save uploaded file: {e}"}

    # Handle music source
    selected_music_path = None

    if do_music_bool:
        if music_source == "library" and music_library_file:
            library_path = MUSIC_DIR / music_library_file
            if library_path.exists():
                selected_music_path = library_path

        elif music_source == "upload" and music_file:
            music_upload_path = MUSIC_TEMP_DIR / f"{file_id}_uploaded.mp3"
            try:
                with open(music_upload_path, "wb") as buffer:
                    shutil.copyfileobj(music_file.file, buffer)
                selected_music_path = music_upload_path
            except Exception as e:
                print(f"[ERROR] Failed to save uploaded music: {e}")

        elif music_source == "link" and music_url:
            downloaded_path = download_audio_from_url(music_url, str(MUSIC_TEMP_DIR))
            if downloaded_path:
                selected_music_path = downloaded_path

    srt_path = OUTPUTS_DIR / f"{file_id}.srt"
    out_path = OUTPUTS_DIR / f"{file_id}_final.mp4"

    background_tasks.add_task(
        process_video_task,
        file_id,
        v_path,
        srt_path,
        out_path,
        do_music_bool,
        do_subtitles_bool,
        do_marketing_bool,
        do_shorts_bool,
        do_thumbnail_bool,
        do_styled_subtitles_bool,
        do_voiceover_bool,
        do_ai_thumbnail_bool,
        music_style,
        selected_music_path,
        # Font settings from chat
        font_name,
        font_color,
        font_size_int,
        music_volume_float,
        ducking_bool,
    )

    return {"file_id": file_id, "status": "processing", "message": "העיבוד התחיל"}


@app.post("/extract-text")
async def extract_text_endpoint(file: UploadFile = File(...)):
    """
    Extract text from uploaded Word (.docx) or Text (.txt) file.
    Returns extracted text for editing before voiceover.
    """
    try:
        # Save uploaded file temporarily
        file_id = str(uuid.uuid4())[:8]
        suffix = Path(file.filename).suffix.lower()
        temp_path = INPUTS_DIR / f"{file_id}_doc{suffix}"

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Extract text
        text = extract_text_from_file(str(temp_path))

        # Cleanup
        try:
            temp_path.unlink()
        except:
            pass

        return {"status": "success", "text": text}

    except Exception as e:
        return {"status": "error", "text": "", "error": str(e)}


@app.post("/generate-voiceover-elevenlabs")
async def generate_voiceover_elevenlabs_endpoint(
    text: str = Form(...),
    emotion: str = Form("neutral"),
    voice_id: Optional[str] = Form(None),
):
    """
    Generate voiceover using ElevenLabs API.
    Supports emotion presets: emotional, pastoral, happy, neutral.
    """
    try:
        file_id = str(uuid.uuid4())[:8]
        output_path = OUTPUTS_DIR / f"{file_id}_elevenlabs_voiceover.mp3"

        success = generate_voiceover_elevenlabs_sync(
            text=text,
            output_path=str(output_path),
            emotion=emotion,
            voice_id=voice_id
        )

        if success and output_path.exists():
            return {
                "status": "success",
                "voiceover_url": f"http://localhost:8000/outputs/{output_path.name}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate voiceover")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-ai-thumbnail")
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
            thumbnail_url = f"http://localhost:8000/outputs/{output_path.name}"
            if original_url:
                ai_thumbnail_original_urls[request.video_id] = original_url
            return {"status": "success", "thumbnail_url": thumbnail_url, "original_url": original_url}

        raise HTTPException(status_code=500, detail="Failed to generate AI thumbnail")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retry-download")
async def retry_download_endpoint(request: RetryDownloadRequest):
    """Retry downloading an image from original URL."""
    output_path = OUTPUTS_DIR / f"{request.video_id}_ai_thumbnail.jpg"
    try:
        success = download_image_from_url(request.original_url, str(output_path), request.title)

        if success and output_path.exists():
            thumbnail_url = f"http://localhost:8000/outputs/{output_path.name}"
            return {"status": "success", "thumbnail_url": thumbnail_url}

        raise HTTPException(status_code=500, detail="Failed to download image")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-original-url/{video_id}")
async def get_original_url(video_id: str):
    """Get original URL for AI thumbnail."""
    original_url = ai_thumbnail_original_urls.get(video_id)
    if original_url:
        return {"status": "success", "original_url": original_url}
    raise HTTPException(status_code=404, detail="Original URL not found")
    
import hashlib
import re
from pathlib import Path
from fastapi import HTTPException, Form

async def download_youtube_audio_endpoint(url: str = Form(...)):
    """
    Download audio from YouTube URL.
    Extracts URL from text if needed and returns the filename.
    Includes duplicate check to skip redownloading.
    """
    try:
        # 1. חילוץ הלינק מתוך הטקסט - מטפל במקרה שהמשתמש שלח משפט שלם
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+(?:&\S*)?)'
        match = re.search(youtube_regex, url)
        
        if not match:
            print(f"[WARNING] No valid URL found in input: {url}")
            raise HTTPException(status_code=400, detail="לא נמצא קישור תקין של יוטיוב בהודעה שלך")
        
        clean_url = match.group(0)
        
        # --- מנגנון מניעת הורדות כפולות ---
        # יוצרים מזהה ייחודי (Hash) ללינק כדי לבדוק אם הקובץ כבר קיים
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:10]
        # אנחנו מחפשים קבצים שמתחילים ב-downloaded_ ומכילים את ה-Hash או פשוט בודקים אם יש קובץ כזה
        # הערה: אם הפונקציה download_audio_from_url שלך נותנת שמות אחרים, המערכת תוריד פעם אחת ותלמד
        
        # חיפוש קובץ קיים בתיקיית ה-temp כדי לחסוך זמן
        existing_files = list(MUSIC_TEMP_DIR.glob(f"*{url_hash}*"))
        if existing_files:
            filename = existing_files[0].name
            print(f"[INFO] קובץ כבר קיים, מדלג על הורדה: {filename}")
            return {
                "status": "success",
                "file_path": filename,
                "audioUrl": f"http://localhost:8000/assets/music/temp/{filename}",
                "message": "המוזיקה נטענה מהזכרון (כבר הורדה בעבר)"
            }
        # ----------------------------------

        print(f"[INFO] Extracting and downloading audio from: {clean_url}")

        # 2. ביצוע ההורדה (משתמשים ב-clean_url במקום ב-url המקורי)
        # אנחנו שולחים את ה-url_hash כחלק מהנתיב אם הפונקציה שלך תומכת בזה, 
        # אם לא, היא פשוט תוריד כרגיל והבדיקה תעבוד בפעם הבאה.
        downloaded_path = download_audio_from_url(clean_url, str(MUSIC_TEMP_DIR))

        if downloaded_path and Path(downloaded_path).exists():
            filename = Path(downloaded_path).name
            
            # (בונוס) שינוי שם הקובץ כך שיכיל את ה-Hash לזיהוי עתידי קל יותר אם צריך
            # זה קורה בתוך download_audio_from_url בד"כ
            
            # מחזירים גם audioUrl כדי שה-React יוכל לנגן מיד ב-Preview
            return {
                "status": "success",
                "file_path": filename,
                "audioUrl": f"http://localhost:8000/assets/music/temp/{filename}", # נתיב לתצוגה מקדימה
                "message": "הורדה הושלמה בהצלחה"
            }
        else:
            raise HTTPException(status_code=500, detail="השרת לא הצליח לשמור את הקובץ מיוטיוב")

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] YouTube download failed: {error_msg}")
        
        # זיהוי שגיאות נפוצות של yt-dlp כדי להחזיר הודעה ידידותית
        friendly_error = "שגיאה בהורדה מיוטיוב"
        if "Video unavailable" in error_msg:
            friendly_error = "הסרטון ביוטיוב אינו זמין (פרטי או הוסר)"
        elif "Incomplete" in error_msg:
            friendly_error = "ההורדה הופסקה באמצע, נסה שוב"
            
        raise HTTPException(status_code=500, detail=friendly_error)



@app.post("/generate-voiceover")
async def generate_voiceover_endpoint(video_id: str = Form(...), text: str = Form(...)):
    """Generate voiceover using Edge-TTS (free)."""
    output_path = OUTPUTS_DIR / f"{video_id}_voiceover.mp3"
    try:
        success = generate_voiceover_sync(text, str(output_path), None)
        if success and output_path.exists():
            voiceover_url = f"http://localhost:8000/outputs/{output_path.name}"
            return {"status": "success", "voiceover_url": voiceover_url}
        raise HTTPException(status_code=500, detail="Failed to generate voiceover")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# AI Editor Chat - Styling Commands Interface
# =============================================================================

@app.post("/chat")
async def ai_editor_chat(
    message: str = Form(...),
    history: str = Form("[]"),
    currentContext: str = Form("{}"),
    has_video: str = Form("false"),
):
    """
    AI chat endpoint for video editing styling commands.
    Multi-intent: extracts all commands from a single sentence.

    Returns { answer, commands: [...] } format.
    """
    import json
    from groq import Groq
    from utils.config import GROQ_API_KEY

    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key not configured")

    try:
        # Parse inputs
        history_list = json.loads(history) if history else []
        context = json.loads(currentContext) if currentContext else {}

        # =====================================================================
        # PRE-PROCESSING: Regex extraction of embedded data the LLM might miss
        # =====================================================================
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w-]+(?:[?&]\S*)?)'
        extracted_youtube_urls = re.findall(youtube_regex, message)

        hex_color_regex = r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b'
        extracted_colors = re.findall(hex_color_regex, message)

        font_size_regex = r'(?:גודל|size)\s*[=:]?\s*(\d{1,3})'
        extracted_sizes = re.findall(font_size_regex, message, re.IGNORECASE)

        volume_regex = r'(?:ווליום|volume|עוצמ[הת])\s*[=:]?\s*(\d{1,3})\s*%?'
        extracted_volumes = re.findall(volume_regex, message, re.IGNORECASE)

        # Build a hint string so the LLM knows what regex already found
        pre_extracted_hint = ""
        if extracted_youtube_urls:
            pre_extracted_hint += f"\n[המערכת זיהתה לינק יוטיוב: {extracted_youtube_urls[0]}]"
        if extracted_colors:
            pre_extracted_hint += f"\n[המערכת זיהתה צבע: {extracted_colors[0]}]"
        if extracted_sizes:
            pre_extracted_hint += f"\n[המערכת זיהתה גודל: {extracted_sizes[0]}]"
        if extracted_volumes:
            pre_extracted_hint += f"\n[המערכת זיהתה ווליום: {extracted_volumes[0]}%]"

        # Get available music files
        music_files = list_music_library(str(MUSIC_DIR))
        music_list_str = ", ".join([f['name'] for f in music_files[:10]]) if music_files else "אין קבצי מוזיקה"

        # Extract current settings from context
        current_font = context.get("font", "Assistant")
        current_color = context.get("fontColor", "#FFFFFF")
        current_size = context.get("fontSize", 48)
        current_music_vol = context.get("musicVolume", 0.3)
        # Convert to percentage for display
        music_vol_percent = int(current_music_vol * 100) if current_music_vol <= 1 else int(current_music_vol)
        current_ducking = context.get("ducking", True)
        current_subtitles = context.get("subtitlesEnabled", context.get("subtitles", True))
        has_video_bool = has_video.lower() == "true"

        # Build system prompt with state awareness (Multi-Intent Support)
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
1. **שלב הזיהוי**: אם המשתמש מבקש "מוזיקה" או מציין סגנון (למשל: "שים משהו שמח", "רוצה מוזיקה רגועה"):
   - **אסור לך לבחור קובץ ואסור לך להוריד כלום עדיין!**
   - ענה: "בשמחה! הבנתי שאתה מחפש מוזיקה {{סגנון}}. האם תרצה לשלוח לי לינק מיוטיוב, להעלות קובץ משלך, או שתרצה שאבחר עבורך משהו מתאים מהספרייה שלי?"
   - ב-JSON החזר commands ריק: {{"answer": "...", "commands": [{{}}]}}

2. **שלב הביצוע (רק אחרי אישור המשתמש)**:
   - אם המשתמש אומר "תבחר אתה" / "מהספרייה": בחר את הקובץ המתאים ביותר מהרשימה לעיל. חובה להשתמש בשם הקובץ המדויק כולל .mp3.
   - אם המשתמש שולח לינק יוטיוב: החזר אותו בשדה "youtubeUrl".
   - אם המשתמש אומר "לא משנה" / ג'יבריש: הודע לו שאתה בוחר ברירת מחדל ושם את הקובץ 'peaceful_nature.mp3'.

=== הגבלות והזהרות (קריטי!) ===
- **איסור המצאה**: לעולם אל תמציא שמות קבצים (כמו 'happy_summer.mp3'). השתמש אך ורק בשמות מרשימת הקבצים לעיל.
- **איסור עריכה אוטומטית**: לעולם אל תחזיר "action": "process_video" אלא אם המשתמש כתב במפורש: "תערוך", "תייצא", "תבצע עיבוד" או "Export". בקשות לשמיעה/ראייה הן לתצוגה מקדימה (Preview) בלבד.
- **עדכון Preview**: כשאתה מוסיף מוזיקה (מיוטיוב או קובץ), כתוב למשתמש "לחץ Play בנגן כדי לשמוע".
- חוק בל יעבור: ברגע שהורדת מוזיקה מיוטיוב, אתה חייב לענות: "הורדתי את המוזיקה! לחץ Play בנגן שמעל הוידאו כדי לשמוע."
- אסור לך להגיד שאי אפשר לשמוע את המוזיקה ב-Preview.
- חובה להחזיר ב-JSON את ה-youtubeUrl המקורי כדי שהמערכת תדע לסנכרן אותו.

=== Multi-Intent: זיהוי מספר פקודות במשפט אחד (קריטי!) ===
המשתמש יכול לשלוח משפט עם מספר בקשות.  **חובה** לזהות את **כל** הכוונות ולהחזיר אותן ב-commands.
סדר הפקודות חשוב: שינויי סגנון (פונט, צבע, גודל, מוזיקה, youtubeUrl) תמיד **לפני** פעולות (process_video).
אם המשתמש שולח גם לינק יוטיוב וגם בקשות סגנון — החזר הכל באותו commands, הלינק בפקודה ראשונה.
{pre_extracted_hint}

=== פורמט תשובה (JSON בלבד) ===
{{
  "answer": "התשובה שלך בעברית - תאר את כל הפעולות שביצעת",
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

=== דוגמאות (חובה ללמוד!) ===
משתמש: "שנה פונט לאריאל וצבע לצהוב"
תשובה: {{"answer": "שיניתי את הפונט לאריאל והצבע לצהוב!", "commands": [{{"font": "Arial", "fontColor": "#FFD700"}}]}}

משתמש: "שים מוזיקה שמחה"
תשובה: {{"answer": "אני אשמח להוסיף מוזיקה שמחה! האם תרצה לשלוח לי קישור מיוטיוב, להעלות קובץ משלך, או שאבחר עבורך משהו מהספרייה שלי?", "commands": [{{}}]}}

משתמש: "תבחר אתה מהספרייה"
תשובה: {{"answer": "מעולה, בחרתי עבורך מנגינה שמחה מהספרייה. לחץ Play כדי לשמוע!", "commands": [{{"musicFile": "happy_energetic.mp3"}}]}}

משתמש: "שנה צבע לאדום, כתוביות גודל 32, הורד מוזיקה ל-20% ותערוך"
תשובה: {{"answer": "שיניתי צבע לאדום, גודל כתוביות ל-32, עוצמת מוזיקה ל-20%, ומתחיל בעיבוד! 🚀", "commands": [{{"fontColor": "#FF0000", "fontSize": 32, "musicVolume": 20}}, {{"action": "process_video"}}]}}

משתמש: "קח מוזיקה מ-https://youtube.com/watch?v=abc123 וגם שנה צבע כתוביות ל-#00FF00 וגודל 28"
תשובה: {{"answer": "מוריד את המוזיקה מיוטיוב, משנה צבע ל-#00FF00 וגודל ל-28!", "commands": [{{"youtubeUrl": "https://youtube.com/watch?v=abc123", "fontColor": "#00FF00", "fontSize": 28}}]}}

משתמש: "הפעל כתוביות, פונט דויד, גודל 40, צבע צהוב, עוצמה 30% ותערוך"
תשובה: {{"answer": "הפעלתי כתוביות בפונט דויד, גודל 40, צבע צהוב, עוצמה 30%. מתחיל עיבוד! 🚀", "commands": [{{"subtitlesEnabled": true, "font": "David", "fontSize": 40, "fontColor": "#FFD700", "musicVolume": 30}}, {{"action": "process_video"}}]}}

משתמש: "תערוך לי את הסרטון עכשיו"
תשובה: {{"answer": "מתחיל בעיבוד הסרטון עם כל ההגדרות שבחרנו... 🚀", "commands": [{{"action": "process_video"}}]}}

החזר רק JSON תקין, ללא טקסט נוסף.
"""

        # =================================================================
        # STEP 1: Log incoming request
        # =================================================================
        print(f"\n[INFO] ======== CHAT REQUEST ========")
        print(f"[INFO] User message: {message}")
        print(f"[INFO] Regex pre-scan: youtube={extracted_youtube_urls}, colors={extracted_colors}, sizes={extracted_sizes}, volumes={extracted_volumes}")

        # Build messages for Groq
        messages = [{"role": "system", "content": system_prompt}]

        # Add history (last 8 messages for context)
        for msg in history_list[-8:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        # Add current message
        messages.append({"role": "user", "content": message})

        # =================================================================
        # STEP 2: Call Groq API
        # =================================================================
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )

        ai_response = response.choices[0].message.content.strip()
        print(f"[INFO] LLM raw response ({len(ai_response)} chars): {ai_response[:200]}...")

        # =================================================================
        # STEP 3: Parse JSON response
        # =================================================================
        try:
            # Remove markdown code blocks if present
            cleaned_response = ai_response
            if cleaned_response.startswith("```"):
                parts = cleaned_response.split("```")
                if len(parts) >= 2:
                    cleaned_response = parts[1]
                    if cleaned_response.startswith("json"):
                        cleaned_response = cleaned_response[4:]
                    cleaned_response = cleaned_response.strip()

            result = json.loads(cleaned_response)
            print(f"[INFO] JSON parsed OK. Keys: {list(result.keys())}")

            # Normalize response to { answer, commands[] } format
            answer = result.get("answer", result.get("message", ai_response))

            # Support both "commands" (array) and legacy "command" (single object)
            commands_raw = result.get("commands", None)
            if commands_raw is None:
                # Fallback: legacy single "command" object -> wrap in array
                single_cmd = result.get("command", result.get("style_updates", {}))
                commands_raw = [single_cmd] if single_cmd else [{}]
                print(f"[INFO] LLM used legacy 'command' key — wrapped into array")

            # Ensure it's a list
            if not isinstance(commands_raw, list):
                commands_raw = [commands_raw]

            print(f"[INFO] Raw commands from LLM ({len(commands_raw)}):")
            for i, raw_cmd in enumerate(commands_raw):
                print(f"[INFO]   cmd[{i}] raw: {raw_cmd}")

            # =============================================================
            # STEP 4: Normalize each command
            # =============================================================
            commands = []
            for i, cmd in enumerate(commands_raw):
                if not isinstance(cmd, dict):
                    print(f"[INFO]   cmd[{i}] SKIPPED (not a dict): {type(cmd)}")
                    continue

                # Remove null/None values AND string "null" the LLM sometimes returns
                before_keys = set(cmd.keys())
                cmd = {k: v for k, v in cmd.items() if v is not None and v != "null" and v != ""}
                stripped = before_keys - set(cmd.keys())
                if stripped:
                    print(f"[INFO]   cmd[{i}] stripped null/empty keys: {stripped}")

                # Convert musicVolume from percentage (0-100) to decimal (0-1)
                if "musicVolume" in cmd:
                    vol = cmd["musicVolume"]
                    if isinstance(vol, (int, float)) and vol > 1:
                        cmd["musicVolume"] = vol / 100.0
                        print(f"[INFO]   cmd[{i}] musicVolume converted: {vol}% -> {cmd['musicVolume']}")

                if cmd:  # Only add non-empty commands
                    commands.append(cmd)
                    print(f"[INFO]   cmd[{i}] FINAL: {cmd}")
                else:
                    print(f"[INFO]   cmd[{i}] DROPPED (empty after cleanup)")

            # =============================================================
            # STEP 5: POST-PROCESSING — merge regex-extracted data LLM missed
            # =============================================================
            # Check if ANY command already contains a youtubeUrl
            has_yt = any(c.get("youtubeUrl") for c in commands)
            if extracted_youtube_urls and not has_yt:
                if commands:
                    commands[0]["youtubeUrl"] = extracted_youtube_urls[0]
                else:
                    commands.append({"youtubeUrl": extracted_youtube_urls[0]})
                print(f"[INFO] POST-FIX: Injected YouTube URL: {extracted_youtube_urls[0]}")

            has_color = any(c.get("fontColor") for c in commands)
            if extracted_colors and not has_color:
                target = commands[0] if commands else {}
                target["fontColor"] = extracted_colors[0]
                if not commands:
                    commands.append(target)
                print(f"[INFO] POST-FIX: Injected color: {extracted_colors[0]}")

            has_size = any(c.get("fontSize") for c in commands)
            if extracted_sizes and not has_size:
                target = commands[0] if commands else {}
                target["fontSize"] = int(extracted_sizes[0])
                if not commands:
                    commands.append(target)
                print(f"[INFO] POST-FIX: Injected fontSize: {extracted_sizes[0]}")

            has_vol = any(c.get("musicVolume") is not None for c in commands)
            if extracted_volumes and not has_vol:
                target = commands[0] if commands else {}
                vol_val = int(extracted_volumes[0])
                target["musicVolume"] = vol_val / 100.0 if vol_val > 1 else vol_val
                if not commands:
                    commands.append(target)
                print(f"[INFO] POST-FIX: Injected volume: {extracted_volumes[0]}%")

            # =============================================================
            # STEP 6: Build the complete action list for diagnostics
            # =============================================================
            detected_actions = []
            for cmd in commands:
                for key, val in cmd.items():
                    if key == "action":
                        detected_actions.append(f"ACTION:{val}")
                    elif key == "youtubeUrl":
                        detected_actions.append(f"YOUTUBE:{val[:40]}...")
                    elif key == "musicFile":
                        detected_actions.append(f"MUSIC:{val}")
                    else:
                        detected_actions.append(f"{key}={val}")

            print(f"[SUCCESS] ======== CHAT RESPONSE ========")
            print(f"[SUCCESS] Detected intents ({len(detected_actions)}): {detected_actions}")
            print(f"[SUCCESS] Commands to frontend ({len(commands)}): {json.dumps(commands, ensure_ascii=False)}")
            print(f"[SUCCESS] Answer: {answer[:80]}...")
            print(f"[SUCCESS] ================================\n")

            return {
                "answer": answer,
                "commands": commands,
                "debug": {
                    "detected_intents": detected_actions,
                    "command_count": len(commands),
                    "regex_extracted": {
                        "youtube": extracted_youtube_urls,
                        "colors": extracted_colors,
                        "sizes": extracted_sizes,
                        "volumes": extracted_volumes,
                    }
                }
            }

        except json.JSONDecodeError as jde:
            # If not valid JSON, build commands from regex extractions as fallback
            print(f"[ERROR] LLM returned non-JSON! Error: {jde}")
            print(f"[ERROR] Raw text was: {ai_response[:300]}")

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

            fallback_actions = list(fallback_cmd.keys())
            print(f"[INFO] Fallback regex commands: {fallback_cmd}")
            return {
                "answer": ai_response,
                "commands": [fallback_cmd] if fallback_cmd else [],
                "debug": {
                    "detected_intents": fallback_actions,
                    "command_count": 1 if fallback_cmd else 0,
                    "parse_error": str(jde),
                    "regex_extracted": {
                        "youtube": extracted_youtube_urls,
                        "colors": extracted_colors,
                        "sizes": extracted_sizes,
                        "volumes": extracted_volumes,
                    }
                }
            }

    except Exception as e:
        print(f"[ERROR] ======== CHAT FAILED ========")
        print(f"[ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
        print(f"[ERROR] =============================\n")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Video Planner - AI Script Chat Interface
# =============================================================================

class VideoPlannerChatRequest(BaseModel):
    user_input: str
    history: list = []
    current_script: str = ""


@app.post("/video-planner/chat")
async def video_planner_chat_endpoint(request: VideoPlannerChatRequest):
    """
    Chat with AI to create and refine a video script.

    Args:
        user_input: User's instruction/request
        history: List of previous messages [{role, content}, ...]
        current_script: Current state of the script

    Returns:
        JSON with AI message and updated script
    """
    try:
        # Limit history to last 10 messages
        history = request.history[-10:] if request.history else []

        # Call the video planner chat function
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: video_planner_chat(
                user_message=request.user_input,
                conversation_history=history,
                current_script=request.current_script,
                file_context=""
            )
        )

        if result["success"]:
            return {
                "status": "success",
                "ai_message": result["ai_message"],
                "script": result["script"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Video planner chat failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/video-planner/extract-file")
async def video_planner_extract_file(file: UploadFile = File(...)):
    """
    Extract text from uploaded file for use as context.
    Supports .docx and .txt files.
    """
    try:
        file_id = str(uuid.uuid4())[:8]
        suffix = Path(file.filename).suffix.lower()

        if suffix not in ['.txt', '.docx']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {suffix}. Use .txt or .docx"
            )

        temp_path = INPUTS_DIR / f"{file_id}_extract{suffix}"

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Extract text
        extracted_text = extract_text_from_file(str(temp_path))

        # Cleanup
        try:
            temp_path.unlink()
        except:
            pass

        return {
            "status": "success",
            "text": extracted_text,
            "filename": file.filename,
            "char_count": len(extracted_text)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] File extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WhatsApp / n8n Unified Command Endpoint
# =============================================================================

class WhatsAppCommandRequest(BaseModel):
    message: str
    media_url: Optional[str] = None


@app.post("/api/whatsapp-command")
async def whatsapp_command(req: WhatsAppCommandRequest):
    """
    Unified AI command endpoint for n8n / WhatsApp integration.

    Receives a text message (and optional media_url), uses AI to classify
    the intent, then routes to the appropriate service.

    Returns clean JSON:
      {"type": "video",     "url": "...", "message": "..."}
      {"type": "text",      "content": "...", "message": "..."}
      {"type": "marketing", "data": {...},    "message": "..."}
      {"type": "error",     "message": "..."}
    """
    import json as _json
    from groq import Groq
    from utils.config import GROQ_API_KEY

    message = req.message.strip()
    media_url = req.media_url

    print(f"\n[INFO] ======== WHATSAPP COMMAND ========")
    print(f"[INFO] Message: {message}")
    print(f"[INFO] Media URL: {media_url or '(none)'}")

    if not message:
        return {"type": "error", "message": "לא התקבלה הודעה"}

    # -----------------------------------------------------------------
    # STEP 1: Use AI to classify the intent
    # -----------------------------------------------------------------
    if not GROQ_API_KEY:
        return {"type": "error", "message": "Groq API key not configured"}

    classify_prompt = """אתה מנתח בקשות לעריכת וידאו. סווג את הבקשה לאחת מהקטגוריות הבאות:

1. "editing" — בקשה לעריכת וידאו, כתוביות, חיתוך shorts, הוספת מוזיקה, ייצוא
2. "script" — בקשה ליצירת תסריט, סקריפט, תכנון תוכן, רעיונות לסרטון
3. "marketing" — בקשה לכותרות, תיאורים, תגיות, פוסט לפייסבוק, SEO, hashtags
4. "chat" — שאלה כללית, שיחה, עזרה

החזר JSON בלבד:
{"intent": "editing|script|marketing|chat", "summary": "תיאור קצר של מה שהמשתמש רוצה"}
"""

    try:
        client = Groq(api_key=GROQ_API_KEY)

        loop = asyncio.get_event_loop()
        classify_response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": classify_prompt},
                    {"role": "user", "content": message},
                ],
                temperature=0.1,
                max_tokens=150,
            ),
        )

        raw_intent = classify_response.choices[0].message.content.strip()
        # Parse classification
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
        summary = intent_data.get("summary", message)

    except Exception as e:
        print(f"[ERROR] Intent classification failed: {e}")
        # Fallback: keyword-based classification
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["תסריט", "סקריפט", "script", "רעיון", "תכנון"]):
            intent = "script"
        elif any(w in msg_lower for w in ["שיווק", "marketing", "כותרת", "תיאור", "hashtag", "פוסט", "תגיות"]):
            intent = "marketing"
        elif any(w in msg_lower for w in ["עריכה", "edit", "כתוביות", "subtitle", "shorts", "מוזיקה", "ייצוא", "עבד"]):
            intent = "editing"
        else:
            intent = "chat"
        summary = message

    print(f"[INFO] Classified intent: {intent}")
    print(f"[INFO] Summary: {summary}")

    # -----------------------------------------------------------------
    # STEP 2: Route to the appropriate handler
    # -----------------------------------------------------------------

    # ===================== SCRIPT =====================
    if intent == "script":
        try:
            result = await loop.run_in_executor(
                None,
                lambda: video_planner_chat(
                    user_message=message,
                    conversation_history=[],
                    current_script="",
                    file_context="",
                ),
            )

            if result.get("success"):
                print(f"[SUCCESS] Script generated ({len(result.get('script', ''))} chars)")
                return {
                    "type": "text",
                    "content": result.get("script", ""),
                    "message": result.get("ai_message", "התסריט נוצר בהצלחה"),
                }
            else:
                return {"type": "error", "message": result.get("error", "שגיאה ביצירת תסריט")}

        except Exception as e:
            print(f"[ERROR] Script generation failed: {e}")
            return {"type": "error", "message": f"שגיאה ביצירת תסריט: {str(e)}"}

    # ===================== MARKETING =====================
    if intent == "marketing":
        # Marketing requires a video — either via media_url or the last uploaded video
        video_path = None
        file_id = None

        if media_url:
            # Download the video from the provided URL
            try:
                file_id = uuid.uuid4().hex[:8]
                video_path = INPUTS_DIR / f"{file_id}.mp4"
                print(f"[INFO] Downloading media from: {media_url}")
                download_ok = await loop.run_in_executor(
                    None, lambda: download_audio_from_url(media_url, str(video_path))
                )
                if not download_ok or not video_path.exists():
                    return {"type": "error", "message": "נכשל בהורדת הקובץ מהקישור"}
            except Exception as e:
                return {"type": "error", "message": f"שגיאה בהורדת מדיה: {str(e)}"}
        else:
            # Try the most recently uploaded video in inputs
            input_files = sorted(INPUTS_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
            if input_files:
                video_path = input_files[0]
                file_id = video_path.stem
            else:
                return {
                    "type": "error",
                    "message": "לא נמצא סרטון. שלח קישור לסרטון או העלה קובץ קודם.",
                }

        try:
            video_duration = get_video_duration(str(video_path))
            has_audio = check_video_has_audio(str(video_path))

            transcript_text = ""
            if has_audio:
                srt_path = OUTPUTS_DIR / f"{file_id}_wa_marketing.srt"
                success, transcript_text = await loop.run_in_executor(
                    None, lambda: transcribe_with_groq(str(video_path), str(srt_path), None)
                )
            else:
                transcript_text, _ = await loop.run_in_executor(
                    None, lambda: extract_text_huggingface(str(video_path), None, None)
                )

            if not transcript_text:
                transcript_text = "סרטון ללא מלל מזוהה"

            marketing_data = await loop.run_in_executor(
                None, lambda: generate_marketing_kit(transcript_text, video_duration, None)
            )

            if not marketing_data:
                return {"type": "error", "message": "נכשל ביצירת תוכן שיווקי"}

            print(f"[SUCCESS] Marketing kit generated: {list(marketing_data.keys())}")
            return {
                "type": "marketing",
                "data": marketing_data,
                "message": "חומרי שיווק נוצרו בהצלחה!",
            }

        except Exception as e:
            print(f"[ERROR] Marketing generation failed: {e}")
            return {"type": "error", "message": f"שגיאה ביצירת שיווק: {str(e)}"}

    # ===================== EDITING =====================
    if intent == "editing":
        if not media_url:
            # Check for last uploaded video
            input_files = sorted(INPUTS_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
            if not input_files:
                return {
                    "type": "error",
                    "message": "לעריכת וידאו נדרש קישור לסרטון. שלח קישור (media_url) או העלה קובץ קודם.",
                }
            video_path = input_files[0]
            file_id = video_path.stem
        else:
            # Download from media_url
            try:
                file_id = uuid.uuid4().hex[:8]
                video_path = INPUTS_DIR / f"{file_id}.mp4"
                print(f"[INFO] Downloading media for editing: {media_url}")
                download_ok = await loop.run_in_executor(
                    None, lambda: download_audio_from_url(media_url, str(video_path))
                )
                if not download_ok or not video_path.exists():
                    return {"type": "error", "message": "נכשל בהורדת הסרטון מהקישור"}
            except Exception as e:
                return {"type": "error", "message": f"שגיאה בהורדת מדיה: {str(e)}"}

        srt_path = OUTPUTS_DIR / f"{file_id}.srt"
        out_path = OUTPUTS_DIR / f"{file_id}_edited.mp4"

        try:
            # Run the full processing pipeline
            await process_video_task(
                file_id=file_id,
                v_path=video_path,
                srt_path=srt_path,
                out_path=out_path,
                do_music=True,
                do_subtitles=True,
                do_marketing=False,
                do_shorts=False,
                do_thumbnail=False,
                do_styled_subtitles=True,
                do_voiceover=False,
                music_style="calm",
                font_name="Arial",
                font_color="#FFFFFF",
                font_size=24,
            )

            if out_path.exists():
                video_url = f"http://localhost:8000/outputs/{out_path.name}"
                print(f"[SUCCESS] Edited video: {video_url}")
                return {
                    "type": "video",
                    "url": video_url,
                    "message": "הסרטון עובד בהצלחה עם כתוביות ומוזיקה!",
                }
            else:
                return {"type": "error", "message": "העיבוד הסתיים אך קובץ הפלט לא נמצא"}

        except Exception as e:
            print(f"[ERROR] Video editing failed: {e}")
            return {"type": "error", "message": f"שגיאה בעריכת וידאו: {str(e)}"}

    # ===================== CHAT (general) =====================
    try:
        chat_response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "אתה עוזר AI מקצועי לעריכת וידאו בעברית. ענה בצורה ידידותית וקצרה.",
                    },
                    {"role": "user", "content": message},
                ],
                temperature=0.7,
                max_tokens=500,
            ),
        )

        answer = chat_response.choices[0].message.content.strip()
        print(f"[SUCCESS] Chat response: {answer[:80]}...")
        return {
            "type": "text",
            "content": answer,
            "message": "תשובה מה-AI",
        }

    except Exception as e:
        print(f"[ERROR] Chat response failed: {e}")
        return {"type": "error", "message": f"שגיאה: {str(e)}"}


# =============================================================================
# YouTube Publish Endpoint
# =============================================================================

# Store for tracking YouTube upload status per task
youtube_upload_status: Dict[str, dict] = {}


class YouTubePublishRequest(BaseModel):
    title: str
    description: str = ""
    tags: list = []
    video_path: str = ""
    thumbnail_path: str = ""
    privacy_status: str = "private"
    is_short: bool = False
    video_id: str = ""  # file_id from frontend to locate the processed video


def _url_to_local_path(url_or_path: str) -> str:
    """
    Convert a URL like http://localhost:8000/outputs/file.mp4
    or /outputs/shorts/file.mp4 to a local file path.
    Returns the original string if it's already a local path.
    """
    if not url_or_path:
        return ""
    s = url_or_path.strip()
    # Strip http://localhost:PORT/outputs/ prefix
    import re as _re
    m = _re.match(r'https?://[^/]+/outputs/(.+)', s)
    if m:
        return str(OUTPUTS_DIR / m.group(1))
    # Strip bare /outputs/ prefix
    if s.startswith("/outputs/"):
        return str(OUTPUTS_DIR / s[len("/outputs/"):])
    return s


@app.post("/api/publish/youtube")
async def publish_to_youtube(req: YouTubePublishRequest, background_tasks: BackgroundTasks):
    """
    Publish a video to YouTube. Runs as a background task so the UI stays responsive.
    Receives marketing data (title, description, tags) from the frontend.
    """
    try:
        print(f"[YOUTUBE-PUBLISH] Request received:")
        print(f"  Title: {req.title}")
        print(f"  Tags: {req.tags}")
        print(f"  Short: {req.is_short}")
        print(f"  Privacy: {req.privacy_status}")
        print(f"  Video path (raw): {req.video_path}")
        print(f"  Thumbnail path (raw): {req.thumbnail_path}")

        # --- Resolve video path ---
        video_path = ""

        # Option 1: Explicit path provided (may be a URL from frontend)
        if req.video_path:
            resolved = _url_to_local_path(req.video_path)
            candidate = Path(resolved)
            if not candidate.is_absolute():
                candidate = OUTPUTS_DIR / resolved
            if candidate.exists():
                video_path = str(candidate)

        # Option 2: Find by video_id (file_id) in outputs
        if not video_path and req.video_id:
            file_id = req.video_id.replace(" ", "_")
            # Check common output patterns
            for pattern in [f"{file_id}_final.mp4", f"{file_id}.mp4", f"final_{file_id}.mp4"]:
                candidate = OUTPUTS_DIR / pattern
                if candidate.exists():
                    video_path = str(candidate)
                    break
            # Fallback: search outputs dir
            if not video_path:
                for f in OUTPUTS_DIR.glob(f"*{file_id}*.mp4"):
                    video_path = str(f)
                    break

        # Option 3: Find most recent mp4 in outputs
        if not video_path:
            mp4_files = sorted(OUTPUTS_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True)
            if mp4_files:
                video_path = str(mp4_files[0])

        if not video_path:
            return {
                "status": "error",
                "message": "לא נמצא קובץ וידאו להעלאה. עבד את הסרטון קודם."
            }

        print(f"[YOUTUBE-PUBLISH] Video file resolved: {video_path}")

        # --- Resolve thumbnail path ---
        thumbnail_path = ""

        # Option 1: Path/URL provided from frontend
        if req.thumbnail_path:
            resolved = _url_to_local_path(req.thumbnail_path)
            candidate = Path(resolved)
            if not candidate.is_absolute():
                candidate = OUTPUTS_DIR / resolved
            if candidate.exists():
                thumbnail_path = str(candidate)

        # Fallback: find thumbnail by video_id
        if not thumbnail_path and req.video_id:
            file_id = req.video_id.replace(" ", "_")
            for ext in [".jpg", ".png", ".jpeg"]:
                for pattern in [f"{file_id}_thumb{ext}", f"thumb_{file_id}{ext}", f"{file_id}_thumbnail{ext}"]:
                    candidate = OUTPUTS_DIR / pattern
                    if candidate.exists():
                        thumbnail_path = str(candidate)
                        break
                if thumbnail_path:
                    break

        # Fallback: find most recent image in outputs
        if not thumbnail_path:
            for ext in ["*.jpg", "*.png", "*.jpeg"]:
                images = sorted(OUTPUTS_DIR.glob(ext), key=os.path.getmtime, reverse=True)
                if images:
                    thumbnail_path = str(images[0])
                    break

        print(f"[YOUTUBE-PUBLISH] Thumbnail resolved: {thumbnail_path or 'none'}")

        # --- Generate a task_id for status tracking ---
        task_id = str(uuid.uuid4())[:8]
        youtube_upload_status[task_id] = {
            "status": "uploading",
            "progress": 0,
            "message": "ממתין להתחלת העלאה...",
        }

        # --- Run upload in background ---
        def _run_upload():
            def progress_cb(percent, message):
                youtube_upload_status[task_id] = {
                    "status": "uploading",
                    "progress": percent,
                    "message": message,
                }

            try:
                result = upload_to_youtube(
                    video_path=video_path,
                    title=req.title,
                    description=req.description,
                    tags=req.tags,
                    thumbnail_path=thumbnail_path or None,
                    privacy_status=req.privacy_status,
                    is_short=req.is_short,
                    progress_callback=progress_cb,
                )
                youtube_upload_status[task_id] = {
                    "status": "completed",
                    "progress": 100,
                    "message": "הסרטון הועלה בהצלחה!",
                    "video_id": result.get("video_id", ""),
                    "url": result.get("url", ""),
                }
                print(f"[SUCCESS] YouTube upload completed: {result.get('url')}")
            except Exception as e:
                youtube_upload_status[task_id] = {
                    "status": "error",
                    "progress": 0,
                    "message": f"שגיאה בהעלאה: {str(e)}",
                }
                print(f"[ERROR] YouTube upload failed: {e}")

        background_tasks.add_task(_run_upload)

        return {
            "status": "success",
            "message": "ההעלאה התחילה ברקע",
            "task_id": task_id,
        }

    except Exception as e:
        print(f"[ERROR] YouTube publish endpoint: {e}")
        return {"status": "error", "message": f"שגיאה: {str(e)}"}


@app.get("/api/publish/youtube/status/{task_id}")
async def youtube_upload_status_check(task_id: str):
    """Check the status of a background YouTube upload."""
    status = youtube_upload_status.get(task_id)
    if not status:
        return {"status": "error", "message": "Task not found"}
    return status


# =============================================================================
# Facebook Publish Endpoint
# =============================================================================

facebook_upload_status: Dict[str, dict] = {}


class FacebookPublishRequest(BaseModel):
    caption: str = ""
    video_path: str = ""
    video_id: str = ""  # file_id from frontend
    is_reel: bool = False  # True = Reel (shorts), False = regular video post


@app.post("/api/publish/facebook")
async def publish_to_facebook_endpoint(req: FacebookPublishRequest, background_tasks: BackgroundTasks):
    """
    Publish a video to a Facebook Page (as a video post or Reel).
    Runs as a background task so the UI stays responsive.
    """
    try:
        print(f"[FACEBOOK-PUBLISH] Request received:")
        print(f"  Caption: {req.caption[:80]}...")
        print(f"  Reel: {req.is_reel}")
        print(f"  Video path (raw): {req.video_path}")

        # --- Resolve video path ---
        video_path = ""

        # Option 1: Explicit path/URL provided
        if req.video_path:
            resolved = _url_to_local_path(req.video_path)
            candidate = Path(resolved)
            if not candidate.is_absolute():
                candidate = OUTPUTS_DIR / resolved
            if candidate.exists():
                video_path = str(candidate)

        # Option 2: Find by video_id in outputs
        if not video_path and req.video_id:
            file_id = req.video_id.replace(" ", "_")
            for pattern in [f"{file_id}_final.mp4", f"{file_id}.mp4", f"final_{file_id}.mp4"]:
                candidate = OUTPUTS_DIR / pattern
                if candidate.exists():
                    video_path = str(candidate)
                    break
            if not video_path:
                for f in OUTPUTS_DIR.glob(f"*{file_id}*.mp4"):
                    video_path = str(f)
                    break

        # Option 3: Most recent mp4
        if not video_path:
            mp4_files = sorted(OUTPUTS_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True)
            if mp4_files:
                video_path = str(mp4_files[0])

        if not video_path:
            return {
                "status": "error",
                "message": "לא נמצא קובץ וידאו להעלאה. עבד את הסרטון קודם."
            }

        print(f"[FACEBOOK-PUBLISH] Video file resolved: {video_path}")

        # --- Generate task_id ---
        task_id = str(uuid.uuid4())[:8]
        facebook_upload_status[task_id] = {
            "status": "uploading",
            "progress": 0,
            "message": "ממתין להתחלת העלאה...",
        }

        # --- Run upload in background ---
        def _run_upload():
            def progress_cb(percent, message):
                facebook_upload_status[task_id] = {
                    "status": "uploading",
                    "progress": percent,
                    "message": message,
                }

            try:
                result = publish_to_facebook(
                    video_path=video_path,
                    caption=req.caption,
                    is_reel=req.is_reel,
                    progress_callback=progress_cb,
                )
                facebook_upload_status[task_id] = {
                    "status": "completed",
                    "progress": 100,
                    "message": "הפוסט פורסם בהצלחה!",
                    "post_id": result.get("post_id", ""),
                    "url": result.get("url", ""),
                }
                print(f"[SUCCESS] Facebook publish completed: {result.get('url')}")
            except Exception as e:
                facebook_upload_status[task_id] = {
                    "status": "error",
                    "progress": 0,
                    "message": f"שגיאה בפרסום: {str(e)}",
                }
                print(f"[ERROR] Facebook publish failed: {e}")

        background_tasks.add_task(_run_upload)

        return {
            "status": "success",
            "message": "הפרסום התחיל ברקע",
            "task_id": task_id,
        }

    except Exception as e:
        print(f"[ERROR] Facebook publish endpoint: {e}")
        return {"status": "error", "message": f"שגיאה: {str(e)}"}


@app.get("/api/publish/facebook/status/{task_id}")
async def facebook_upload_status_check(task_id: str):
    """Check the status of a background Facebook upload."""
    status = facebook_upload_status.get(task_id)
    if not status:
        return {"status": "error", "message": "Task not found"}
    return status


# =============================================================================
# Effects Studio - Remotion Render Endpoints
# =============================================================================

class EffectsRenderRequest(BaseModel):
    video_id: str = ""
    animation_style: str = "karaoke"
    highlight_color: str = "#FF6B35"
    subtitle_position: str = "bottom"
    subtitle_size: int = 56
    # Camera Effects
    camera_shake_enabled: bool = False
    camera_shake_intensity: float = 0.5
    # Ambience Layers
    particles_enabled: bool = False
    dynamic_zoom_enabled: bool = False
    # Sound Waves
    sound_waves_enabled: bool = False
    visualizer_style: str = "bars"
    # Global Controls
    effect_strength: float = 0.7
    dominant_color: str = "#00D1C1"
    audio_url: str = ""
    # Trim
    trim_start: float = 0.0
    trim_end: float = 0.0
    # Corrected subtitles (from manual timing editor)
    corrected_entries: list = []

effects_render_status: Dict[str, dict] = {}

@app.post("/api/render/effects")
async def render_effects(req: EffectsRenderRequest, background_tasks: BackgroundTasks):
    """Start a background Remotion render for effects overlay."""
    try:
        task_id = str(uuid.uuid4())[:8]
        effects_render_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "מתחיל רינדור...",
        }

        # Resolve video path from video_id
        video_path = None
        srt_path = None

        print(f"[EffectsRender] === Resolving video_id='{req.video_id}' ===")

        if req.video_id:
            vid = req.video_id
            # Strip the stem (without extension) for extension-based lookups
            vid_stem = Path(vid).stem if "." in vid else vid

            # 1) Check if it's a URL or absolute path
            resolved = _url_to_local_path(vid)
            if Path(resolved).exists():
                video_path = resolved
                print(f"[EffectsRender] Found via URL/path: {video_path}")

            # 2) Try as direct filename in both directories
            if not video_path:
                for d in [INPUTS_DIR, OUTPUTS_DIR]:
                    candidate = d / vid
                    if candidate.exists():
                        video_path = str(candidate)
                        print(f"[EffectsRender] Found via direct name: {video_path}")
                        break

            # 3) Try stem + common video extensions (handles UUID-only IDs like "a1b2c3d4")
            if not video_path:
                for d in [INPUTS_DIR, OUTPUTS_DIR]:
                    for ext in [".mp4", ".webm", ".mov", ".avi"]:
                        candidate = d / f"{vid_stem}{ext}"
                        if candidate.exists():
                            video_path = str(candidate)
                            print(f"[EffectsRender] Found via stem+ext: {video_path}")
                            break
                    if video_path:
                        break

            # 3b) Try {stem}_final.mp4 in OUTPUTS_DIR (source may have been cleaned up)
            if not video_path:
                for ext in [".mp4", ".webm", ".mov"]:
                    candidate = OUTPUTS_DIR / f"{vid_stem}_final{ext}"
                    if candidate.exists():
                        video_path = str(candidate)
                        print(f"[EffectsRender] Found via _final fallback: {video_path}")
                        break

        # 4) Last resort: find most recently modified video in INPUTS_DIR
        if not video_path:
            print(f"[EffectsRender] All lookups failed. Scanning INPUTS_DIR for recent videos...")
            video_exts = {".mp4", ".webm", ".mov", ".avi"}
            candidates = [
                f for f in INPUTS_DIR.iterdir()
                if f.is_file() and f.suffix.lower() in video_exts
            ]
            if candidates:
                candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                video_path = str(candidates[0])
                print(f"[EffectsRender] Using most recent input video: {video_path}")
            else:
                print(f"[EffectsRender] No video files found in {INPUTS_DIR}")

        # Find SRT - look for matching SRT file
        if video_path:
            base = Path(video_path).stem
            # Also try without _final suffix for SRT matching
            base_clean = base.replace("_final", "")
            for srt_candidate in [
                OUTPUTS_DIR / f"{base}.srt",
                OUTPUTS_DIR / f"{base_clean}.srt",
                INPUTS_DIR / f"{base}.srt",
                INPUTS_DIR / f"{base_clean}.srt",
            ]:
                if srt_candidate.exists():
                    srt_path = str(srt_candidate)
                    print(f"[EffectsRender] Found SRT: {srt_path}")
                    break

        if not video_path:
            print(f"[EffectsRender] ERROR: No video found for video_id='{req.video_id}'")
            return {"status": "error", "message": f"לא נמצא קובץ וידאו (video_id='{req.video_id}'). יש לעבד סרטון קודם."}
        if not srt_path:
            print(f"[EffectsRender] ERROR: No SRT found for video={video_path}")
            return {"status": "error", "message": "לא נמצא קובץ כתוביות SRT. יש לעבד כתוביות קודם."}

        # Resolve the audio source: prefer _final.mp4 (has background music mixed in)
        audio_source_path = None
        vid_stem_for_audio = Path(video_path).stem.replace("_final", "")
        for candidate in [
            OUTPUTS_DIR / f"{vid_stem_for_audio}_final.mp4",
            OUTPUTS_DIR / f"{vid_stem_for_audio}_final.webm",
            OUTPUTS_DIR / f"{vid_stem_for_audio}_final.mov",
        ]:
            if candidate.exists():
                audio_source_path = str(candidate)
                break
        if not audio_source_path:
            audio_source_path = video_path  # Fallback to raw input
        print(f"[EffectsRender] Video (visual): {video_path}")
        print(f"[EffectsRender] Audio source: {audio_source_path}")
        print(f"[EffectsRender] SRT: {srt_path}")
        print(f"[EffectsRender] Style: {req.animation_style}, Color: {req.highlight_color}")
        print(f"[EffectsRender] Trim: {req.trim_start:.1f}s - {req.trim_end:.1f}s")
        print(f"[EffectsRender] Corrected entries: {len(req.corrected_entries)} lines")

        async def _run_render():
            import asyncio
            loop = asyncio.get_event_loop()

            def progress_cb(progress, message):
                effects_render_status[task_id] = {
                    "status": "processing",
                    "progress": progress,
                    "message": message,
                }

            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: render_effects_video(
                        video_path=video_path,
                        srt_path=srt_path,
                        audio_source_path=audio_source_path,
                        animation_style=req.animation_style,
                        highlight_color=req.highlight_color,
                        subtitle_position=req.subtitle_position,
                        subtitle_size=req.subtitle_size,
                        camera_shake_enabled=req.camera_shake_enabled,
                        camera_shake_intensity=req.camera_shake_intensity,
                        particles_enabled=req.particles_enabled,
                        dynamic_zoom_enabled=req.dynamic_zoom_enabled,
                        sound_waves_enabled=req.sound_waves_enabled,
                        visualizer_style=req.visualizer_style,
                        effect_strength=req.effect_strength,
                        dominant_color=req.dominant_color,
                        trim_start=req.trim_start,
                        trim_end=req.trim_end,
                        corrected_entries=req.corrected_entries,
                        progress_callback=progress_cb,
                    ),
                )

                if "error" in result:
                    effects_render_status[task_id] = {
                        "status": "error",
                        "progress": 0,
                        "message": result["error"],
                    }
                else:
                    effects_render_status[task_id] = {
                        "status": "completed",
                        "progress": 100,
                        "message": "הרינדור הושלם בהצלחה!",
                        "url": result["url"],
                        "filename": result.get("filename", ""),
                    }
                    print(f"[EffectsRender] Success: {result['url']}")
            except Exception as e:
                effects_render_status[task_id] = {
                    "status": "error",
                    "progress": 0,
                    "message": f"שגיאה ברינדור: {str(e)}",
                }
                print(f"[EffectsRender] Error: {e}")

        background_tasks.add_task(_run_render)

        return {
            "status": "success",
            "message": "הרינדור התחיל ברקע",
            "task_id": task_id,
        }

    except Exception as e:
        print(f"[EffectsRender] Endpoint error: {e}")
        return {"status": "error", "message": f"שגיאה: {str(e)}"}


@app.get("/api/render/effects/status/{task_id}")
async def effects_render_status_check(task_id: str):
    """Check the status of a background effects render."""
    status = effects_render_status.get(task_id)
    if not status:
        return {"status": "error", "message": "Task not found"}
    return status


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
