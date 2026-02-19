"""
Publishing routes — YouTube and Facebook video upload.
"""
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from core import youtube_upload_status, facebook_upload_status, url_to_local_path
from services.youtube_upload_service import upload_to_youtube
from services.facebook_publish_service import publish_to_facebook
from utils.config import OUTPUTS_DIR

router = APIRouter()


# =============================================================================
# Request Models
# =============================================================================

class YouTubePublishRequest(BaseModel):
    title: str
    description: str = ""
    tags: list = []
    video_path: str = ""
    thumbnail_path: str = ""
    privacy_status: str = "private"
    is_short: bool = False
    video_id: str = ""


class FacebookPublishRequest(BaseModel):
    caption: str = ""
    video_path: str = ""
    video_id: str = ""
    is_reel: bool = False


# =============================================================================
# Shared Helpers
# =============================================================================

def _resolve_video_path(raw_path: str, video_id: str) -> str:
    """Resolve a video path from URL, video_id, or fallback to most recent."""
    video_path = ""

    if raw_path:
        resolved = url_to_local_path(raw_path)
        candidate = Path(resolved)
        if not candidate.is_absolute():
            candidate = OUTPUTS_DIR / resolved
        if candidate.exists():
            video_path = str(candidate)

    if not video_path and video_id:
        file_id = video_id.replace(" ", "_")
        for pattern in [f"{file_id}_final.mp4", f"{file_id}.mp4", f"final_{file_id}.mp4"]:
            candidate = OUTPUTS_DIR / pattern
            if candidate.exists():
                video_path = str(candidate)
                break
        if not video_path:
            for f in OUTPUTS_DIR.glob(f"*{file_id}*.mp4"):
                video_path = str(f)
                break

    if not video_path:
        mp4_files = sorted(OUTPUTS_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if mp4_files:
            video_path = str(mp4_files[0])

    return video_path


# =============================================================================
# YouTube
# =============================================================================

@router.post("/api/publish/youtube")
async def publish_to_youtube_endpoint(req: YouTubePublishRequest, background_tasks: BackgroundTasks):
    """Publish a video to YouTube (background task)."""
    try:
        video_path = _resolve_video_path(req.video_path, req.video_id)
        if not video_path:
            return {"status": "error", "message": "לא נמצא קובץ וידאו להעלאה."}

        # Resolve thumbnail
        thumbnail_path = ""
        if req.thumbnail_path:
            resolved = url_to_local_path(req.thumbnail_path)
            candidate = Path(resolved)
            if not candidate.is_absolute():
                candidate = OUTPUTS_DIR / resolved
            if candidate.exists():
                thumbnail_path = str(candidate)

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

        task_id = str(uuid.uuid4())[:8]
        youtube_upload_status[task_id] = {"status": "uploading", "progress": 0, "message": "ממתין להתחלת העלאה..."}

        def _run_upload():
            def progress_cb(percent, message):
                youtube_upload_status[task_id] = {"status": "uploading", "progress": percent, "message": message}

            try:
                result = upload_to_youtube(
                    video_path=video_path, title=req.title, description=req.description,
                    tags=req.tags, thumbnail_path=thumbnail_path or None,
                    privacy_status=req.privacy_status, is_short=req.is_short, progress_callback=progress_cb,
                )
                youtube_upload_status[task_id] = {
                    "status": "completed", "progress": 100, "message": "הסרטון הועלה בהצלחה!",
                    "video_id": result.get("video_id", ""), "url": result.get("url", ""),
                }
            except Exception as e:
                youtube_upload_status[task_id] = {"status": "error", "progress": 0, "message": f"שגיאה: {str(e)}"}

        background_tasks.add_task(_run_upload)
        return {"status": "success", "message": "ההעלאה התחילה ברקע", "task_id": task_id}

    except Exception as e:
        return {"status": "error", "message": f"שגיאה: {str(e)}"}


@router.get("/api/publish/youtube/status/{task_id}")
async def youtube_upload_status_check(task_id: str):
    """Check background YouTube upload status."""
    status = youtube_upload_status.get(task_id)
    if not status:
        return {"status": "error", "message": "Task not found"}
    return status


# =============================================================================
# Facebook
# =============================================================================

@router.post("/api/publish/facebook")
async def publish_to_facebook_endpoint(req: FacebookPublishRequest, background_tasks: BackgroundTasks):
    """Publish a video to a Facebook Page (background task)."""
    try:
        video_path = _resolve_video_path(req.video_path, req.video_id)
        if not video_path:
            return {"status": "error", "message": "לא נמצא קובץ וידאו להעלאה."}

        task_id = str(uuid.uuid4())[:8]
        facebook_upload_status[task_id] = {"status": "uploading", "progress": 0, "message": "ממתין להתחלת העלאה..."}

        def _run_upload():
            def progress_cb(percent, message):
                facebook_upload_status[task_id] = {"status": "uploading", "progress": percent, "message": message}

            try:
                result = publish_to_facebook(
                    video_path=video_path, caption=req.caption,
                    is_reel=req.is_reel, progress_callback=progress_cb,
                )
                facebook_upload_status[task_id] = {
                    "status": "completed", "progress": 100, "message": "הפוסט פורסם בהצלחה!",
                    "post_id": result.get("post_id", ""), "url": result.get("url", ""),
                }
            except Exception as e:
                facebook_upload_status[task_id] = {"status": "error", "progress": 0, "message": f"שגיאה: {str(e)}"}

        background_tasks.add_task(_run_upload)
        return {"status": "success", "message": "הפרסום התחיל ברקע", "task_id": task_id}

    except Exception as e:
        return {"status": "error", "message": f"שגיאה: {str(e)}"}


@router.get("/api/publish/facebook/status/{task_id}")
async def facebook_upload_status_check(task_id: str):
    """Check background Facebook upload status."""
    status = facebook_upload_status.get(task_id)
    if not status:
        return {"status": "error", "message": "Task not found"}
    return status
