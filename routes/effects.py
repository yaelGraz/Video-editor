"""
Effects Studio routes — Remotion-based video rendering with effects overlay.
"""
import uuid
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from core import effects_render_status, url_to_local_path
from services.remotion_render_service import render_effects_video
from utils.config import INPUTS_DIR, OUTPUTS_DIR

router = APIRouter()


class EffectsRenderRequest(BaseModel):
    video_id: str = ""
    animation_style: str = "karaoke"
    highlight_color: str = "#FF6B35"
    subtitle_position: str = "bottom"
    subtitle_size: int = 56
    camera_shake_enabled: bool = False
    camera_shake_intensity: float = 0.5
    particles_enabled: bool = False
    dynamic_zoom_enabled: bool = False
    sound_waves_enabled: bool = False
    visualizer_style: str = "bars"
    effect_strength: float = 0.7
    dominant_color: str = "#00D1C1"
    audio_url: str = ""
    trim_start: float = 0.0
    trim_end: float = 0.0
    corrected_entries: list = []


@router.post("/api/render/effects")
async def render_effects(req: EffectsRenderRequest, background_tasks: BackgroundTasks):
    """Start a background Remotion render for effects overlay."""
    try:
        task_id = str(uuid.uuid4())[:8]
        effects_render_status[task_id] = {"status": "processing", "progress": 0, "message": "מתחיל רינדור..."}

        # Resolve video path
        video_path = None
        srt_path = None

        if req.video_id:
            vid = req.video_id
            vid_stem = Path(vid).stem if "." in vid else vid

            resolved = url_to_local_path(vid)
            if Path(resolved).exists():
                video_path = resolved

            if not video_path:
                for d in [INPUTS_DIR, OUTPUTS_DIR]:
                    candidate = d / vid
                    if candidate.exists():
                        video_path = str(candidate)
                        break

            if not video_path:
                for d in [INPUTS_DIR, OUTPUTS_DIR]:
                    for ext in [".mp4", ".webm", ".mov", ".avi"]:
                        candidate = d / f"{vid_stem}{ext}"
                        if candidate.exists():
                            video_path = str(candidate)
                            break
                    if video_path:
                        break

            if not video_path:
                for ext in [".mp4", ".webm", ".mov"]:
                    candidate = OUTPUTS_DIR / f"{vid_stem}_final{ext}"
                    if candidate.exists():
                        video_path = str(candidate)
                        break

        # Last resort: most recent input video
        if not video_path:
            video_exts = {".mp4", ".webm", ".mov", ".avi"}
            candidates = [f for f in INPUTS_DIR.iterdir() if f.is_file() and f.suffix.lower() in video_exts]
            if candidates:
                candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                video_path = str(candidates[0])

        # Find SRT
        if video_path:
            base = Path(video_path).stem
            base_clean = base.replace("_final", "")
            for srt_candidate in [
                OUTPUTS_DIR / f"{base}.srt", OUTPUTS_DIR / f"{base_clean}.srt",
                INPUTS_DIR / f"{base}.srt", INPUTS_DIR / f"{base_clean}.srt",
            ]:
                if srt_candidate.exists():
                    srt_path = str(srt_candidate)
                    break

        if not video_path:
            return {"status": "error", "message": f"לא נמצא קובץ וידאו (video_id='{req.video_id}')."}
        if not srt_path:
            return {"status": "error", "message": "לא נמצא קובץ כתוביות SRT."}

        # Resolve audio source (prefer _final.mp4 with mixed audio)
        audio_source_path = None
        vid_stem_for_audio = Path(video_path).stem.replace("_final", "")
        for candidate in [
            OUTPUTS_DIR / f"{vid_stem_for_audio}_final.mp4",
            OUTPUTS_DIR / f"{vid_stem_for_audio}_final.webm",
        ]:
            if candidate.exists():
                audio_source_path = str(candidate)
                break
        if not audio_source_path:
            audio_source_path = video_path

        print(f"[EffectsRender] Video: {video_path} | Audio: {audio_source_path} | SRT: {srt_path}")

        async def _run_render():
            import asyncio
            loop = asyncio.get_event_loop()

            def progress_cb(progress, message):
                effects_render_status[task_id] = {"status": "processing", "progress": progress, "message": message}

            try:
                result = await loop.run_in_executor(
                    None, lambda: render_effects_video(
                        video_path=video_path, srt_path=srt_path, audio_source_path=audio_source_path,
                        animation_style=req.animation_style, highlight_color=req.highlight_color,
                        subtitle_position=req.subtitle_position, subtitle_size=req.subtitle_size,
                        camera_shake_enabled=req.camera_shake_enabled,
                        camera_shake_intensity=req.camera_shake_intensity,
                        particles_enabled=req.particles_enabled,
                        dynamic_zoom_enabled=req.dynamic_zoom_enabled,
                        sound_waves_enabled=req.sound_waves_enabled,
                        visualizer_style=req.visualizer_style,
                        effect_strength=req.effect_strength, dominant_color=req.dominant_color,
                        trim_start=req.trim_start, trim_end=req.trim_end,
                        corrected_entries=req.corrected_entries, progress_callback=progress_cb,
                    ),
                )
                if "error" in result:
                    effects_render_status[task_id] = {"status": "error", "progress": 0, "message": result["error"]}
                else:
                    effects_render_status[task_id] = {
                        "status": "completed", "progress": 100, "message": "הרינדור הושלם!",
                        "url": result["url"], "filename": result.get("filename", ""),
                    }
            except Exception as e:
                effects_render_status[task_id] = {"status": "error", "progress": 0, "message": f"שגיאה: {str(e)}"}

        background_tasks.add_task(_run_render)
        return {"status": "success", "message": "הרינדור התחיל ברקע", "task_id": task_id}

    except Exception as e:
        return {"status": "error", "message": f"שגיאה: {str(e)}"}


@router.get("/api/render/effects/status/{task_id}")
async def effects_render_status_check(task_id: str):
    """Check background effects render status."""
    status = effects_render_status.get(task_id)
    if not status:
        return {"status": "error", "message": "Task not found"}
    return status
