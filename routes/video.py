"""
Video processing routes — upload, process, subtitle review, WebSocket progress.
"""
import os
import asyncio
import shutil
import uuid
import random
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from pydantic import BaseModel

from core import manager, pending_tasks, parse_bool
from services.audio_service import (
    transcribe_with_groq,
    generate_voiceover_from_srt_sync,
    get_random_music,
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
    extract_text_huggingface,
)
from services.text_service import (
    convert_srt_to_ass,
    fix_subtitles_with_ai,
    parse_srt_file,
    write_srt_from_entries,
)
from services.font_service import ensure_font_available
from services.marketing_service import generate_marketing_kit
from core import ai_thumbnail_original_urls
from utils.config import INPUTS_DIR, OUTPUTS_DIR, MUSIC_DIR, MUSIC_TEMP_DIR, SERVER_BASE_URL

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class UpdateSubtitlesRequest(BaseModel):
    subtitles: list[dict]


# =============================================================================
# Helper
# =============================================================================

def cleanup_source_file(v_path: Path, out_path: Path):
    # Keep source file for Effects Studio tab (Remotion rendering needs it)
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[CLEANUP] Keeping source file for Effects Studio: {v_path}")
    else:
        print(f"[CLEANUP] Output not found, keeping source: {v_path}")


# =============================================================================
# Upload
# =============================================================================

@router.post("/upload-video")
async def upload_video(video: UploadFile = File(...)):
    """Upload a video file and return its video_id."""
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
# WebSocket Progress
# =============================================================================

@router.websocket("/ws/progress/{file_id}")
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


# =============================================================================
# Main Process Endpoint
# =============================================================================

@router.post("/process")
async def process_video_api(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    music_file: UploadFile | None = File(None),
    do_subtitles: str = Form("true"),
    do_music: str = Form("true"),
    music_style: str = Form("calm"),
    music_source: str = Form("auto"),
    music_library_file: str = Form(""),
    music_url: str = Form(""),
    do_marketing: str = Form("true"),
    do_shorts: str = Form("false"),
    do_thumbnail: str = Form("true"),
    do_styled_subtitles: str = Form("true"),
    do_voiceover: str = Form("false"),
    do_ai_thumbnail: str = Form("false"),
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

    try:
        font_size_int = int(font_size)
    except (ValueError, TypeError):
        font_size_int = 24

    try:
        music_volume_float = float(music_volume)
    except (ValueError, TypeError):
        music_volume_float = 0.15

    print(f"\n{'='*60}")
    print(f"[PROCESS] === RECEIVED SETTINGS FROM FRONTEND ===")
    print(f"[PROCESS] FONT: '{font_name}' | COLOR: '{font_color}' | SIZE: {font_size_int}")
    print(f"[PROCESS] Music Source: {music_source}, Style: {music_style}")
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
        file_id, v_path, srt_path, out_path,
        do_music_bool, do_subtitles_bool, do_marketing_bool, do_shorts_bool,
        do_thumbnail_bool, do_styled_subtitles_bool, do_voiceover_bool,
        do_ai_thumbnail_bool, music_style, selected_music_path,
        font_name, font_color, font_size_int, music_volume_float, ducking_bool,
    )

    return {"file_id": file_id, "status": "processing", "message": "העיבוד התחיל"}


# =============================================================================
# Subtitle Review
# =============================================================================

@router.post("/update-subtitles/{file_id}")
async def update_subtitles(file_id: str, request: UpdateSubtitlesRequest):
    """Save user-edited subtitles to SRT file."""
    srt_path = OUTPUTS_DIR / f"{file_id}.srt"

    try:
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


@router.post("/continue-processing/{file_id}")
async def continue_processing(file_id: str, background_tasks: BackgroundTasks):
    """Resume video processing after subtitle review."""
    if file_id not in pending_tasks:
        raise HTTPException(status_code=404, detail="No pending task found for this file_id")

    task_data = pending_tasks.pop(file_id)
    print(f"[CONTINUE] Resuming processing for {file_id}")

    background_tasks.add_task(continue_video_task, file_id, **task_data)
    return {"status": "resuming", "message": "Processing resumed"}


# =============================================================================
# Video Processing Pipeline
# =============================================================================

async def process_video_task(
    file_id: str, v_path: Path, srt_path: Path, out_path: Path,
    do_music: bool, do_subtitles: bool, do_marketing: bool, do_shorts: bool,
    do_thumbnail: bool, do_styled_subtitles: bool, do_voiceover: bool = False,
    do_ai_thumbnail: bool = False, music_style: str = "calm",
    selected_music_path: Path = None,
    font_name: str = "Arial", font_color: str = "#FFFFFF", font_size: int = 24,
    music_volume: float = 0.15, ducking: bool = True,
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
            manager.send_progress(file_id, progress, "processing", message), loop,
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
                await manager.send_progress(file_id, 10, "processing", "מחלץ כתוביות מהוידאו...")
                transcript_text, entries = await loop.run_in_executor(
                    None, lambda: extract_text_huggingface(str(v_path), progress_callback, str(srt_path))
                )
                if srt_path.exists() and srt_path.stat().st_size > 0:
                    await manager.send_progress(file_id, 18, "processing", "מתקן כתוביות עם AI...")
                    await loop.run_in_executor(
                        None, lambda: fix_subtitles_with_ai(str(srt_path), progress_callback)
                    )
                elif transcript_text:
                    try:
                        with open(str(srt_path), 'w', encoding='utf-8') as f:
                            f.write(transcript_text)
                    except Exception as save_err:
                        print(f"[ERROR] Fallback save failed: {save_err}")

        # Subtitle review pause
        if do_subtitles and srt_path.exists() and srt_path.stat().st_size > 0:
            srt_entries = parse_srt_file(str(srt_path))

            if srt_entries:
                print(f"[SUBTITLE REVIEW] Pausing for user review. {len(srt_entries)} entries found.")

                pending_tasks[file_id] = {
                    "v_path": v_path, "srt_path": srt_path, "out_path": out_path,
                    "do_music": do_music, "do_subtitles": do_subtitles,
                    "do_marketing": do_marketing, "do_shorts": do_shorts,
                    "do_thumbnail": do_thumbnail, "do_styled_subtitles": do_styled_subtitles,
                    "do_voiceover": do_voiceover, "do_ai_thumbnail": do_ai_thumbnail,
                    "music_style": music_style, "selected_music_path": selected_music_path,
                    "font_name": font_name, "font_color": font_color, "font_size": font_size,
                    "music_volume": music_volume, "ducking": ducking,
                    "transcript_text": transcript_text,
                    "video_duration": video_duration,
                    "video_width": video_width, "video_height": video_height,
                    "has_audio": has_audio,
                }

                await manager.send_progress(
                    file_id, 20, "subtitle_review", "כתוביות מוכנות לעריכה",
                    {"subtitles": srt_entries, "total_entries": len(srt_entries)}
                )
                return

        # Continue with the rest of the pipeline
        await _run_post_subtitle_pipeline(
            file_id, v_path, srt_path, out_path, loop, progress_callback,
            do_music, do_subtitles, do_marketing, do_shorts, do_thumbnail,
            do_styled_subtitles, do_voiceover, do_ai_thumbnail,
            music_style, chosen_music, font_name, font_color, font_size,
            music_volume, ducking, transcript_text,
            get_video_duration(v_path),
            *get_video_resolution(v_path),
            check_video_has_audio(v_path),
        )

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        await manager.send_progress(file_id, 100, "error", f"שגיאה: {str(e)}")


async def continue_video_task(
    file_id: str, v_path: Path, srt_path: Path, out_path: Path,
    do_music: bool, do_subtitles: bool, do_marketing: bool, do_shorts: bool,
    do_thumbnail: bool, do_styled_subtitles: bool, do_voiceover: bool,
    do_ai_thumbnail: bool, music_style: str, selected_music_path: Path,
    font_name: str, font_color: str, font_size: int,
    music_volume: float, ducking: bool, transcript_text: str,
    video_duration: float, video_width: int, video_height: int, has_audio: bool,
):
    """Continue video processing after subtitle review."""
    loop = asyncio.get_event_loop()

    def progress_callback(progress: int, message: str):
        asyncio.run_coroutine_threadsafe(
            manager.send_progress(file_id, progress, "processing", message), loop,
        )

    try:
        await manager.send_progress(file_id, 22, "processing", "ממשיך בעיבוד...")

        await _run_post_subtitle_pipeline(
            file_id, v_path, srt_path, out_path, loop, progress_callback,
            do_music, do_subtitles, do_marketing, do_shorts, do_thumbnail,
            do_styled_subtitles, do_voiceover, do_ai_thumbnail,
            music_style, selected_music_path, font_name, font_color, font_size,
            music_volume, ducking, transcript_text,
            video_duration, video_width, video_height, has_audio,
        )

    except Exception as e:
        print(f"[ERROR] Continue processing failed: {e}")
        import traceback
        traceback.print_exc()
        await manager.send_progress(file_id, 100, "error", f"שגיאה: {str(e)}")


async def _run_post_subtitle_pipeline(
    file_id, v_path, srt_path, out_path, loop, progress_callback,
    do_music, do_subtitles, do_marketing, do_shorts, do_thumbnail,
    do_styled_subtitles, do_voiceover, do_ai_thumbnail,
    music_style, chosen_music, font_name, font_color, font_size,
    music_volume, ducking, transcript_text,
    video_duration, video_width, video_height, has_audio,
):
    """Shared pipeline logic: marketing, music, ASS, voiceover, merge, shorts, thumbnail."""
    marketing_data = None
    shorts_paths = []
    thumbnail_url = None
    ai_thumbnail_url = None
    voiceover_audio_path = None

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

    # 4) ASS subtitles
    subtitle_path = srt_path
    use_ass = False
    if do_styled_subtitles and do_subtitles and srt_path.exists():
        ass_path = OUTPUTS_DIR / f"{file_id}.ass"
        await manager.send_progress(file_id, 40, "processing", "בודק ומוריד גופן...")
        _font = await loop.run_in_executor(None, ensure_font_available, font_name)
        await manager.send_progress(file_id, 42, "processing", "ממיר לכתוביות מעוצבות...")

        _srt, _ass = str(srt_path), str(ass_path)
        _width, _height, _color, _size = video_width, video_height, font_color, font_size

        ok = await loop.run_in_executor(
            None, lambda: convert_srt_to_ass(
                _srt, _ass, _width, _height,
                font_name=_font, font_color=_color, font_size=_size
            )
        )
        if ok:
            subtitle_path = ass_path
            use_ass = True

    # 5) Voiceover
    if do_voiceover and srt_path.exists():
        await manager.send_progress(file_id, 55, "processing", "מייצר קריינות...")
        voiceover_audio_path = OUTPUTS_DIR / f"{file_id}_voiceover.mp3"
        ok = await loop.run_in_executor(
            None, lambda: generate_voiceover_from_srt_sync(
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
    elif do_subtitles and srt_path.exists() and os.path.getsize(str(srt_path)) > 0:
        final_subtitle_path = str(srt_path)

    merge_success = await loop.run_in_executor(
        None, lambda: merge_final_video(
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
            None, lambda: cut_viral_shorts(
                str(v_path), marketing_data["viral_moments"], str(OUTPUTS_DIR),
                subtitle_path=shorts_subtitle_path, use_ass=use_ass,
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
            thumbnail_url = f"{SERVER_BASE_URL}/outputs/{thumb_out.name}"

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
            ai_thumbnail_url = f"{SERVER_BASE_URL}/outputs/{ai_out.name}"
            if original_url:
                ai_thumbnail_original_urls[file_id] = original_url

    # Build result
    result_data = {"download_url": f"{SERVER_BASE_URL}/outputs/{out_path.name}"}
    result_data["file_id"] = file_id
    if chosen_music:
        result_data["music_url"] = f"{SERVER_BASE_URL}/assets/music/{Path(str(chosen_music)).name}"
    if marketing_data:
        result_data["marketing_kit"] = marketing_data
    if shorts_paths:
        result_data["shorts"] = [f"{SERVER_BASE_URL}/outputs/shorts/{Path(p).name}" for p in shorts_paths]
    if thumbnail_url:
        result_data["thumbnail"] = thumbnail_url
    if ai_thumbnail_url:
        result_data["ai_thumbnail"] = ai_thumbnail_url
        result_data["ai_thumbnail_original_url"] = ai_thumbnail_original_urls.get(file_id)
    if voiceover_audio_path and Path(voiceover_audio_path).exists():
        result_data["voiceover"] = f"{SERVER_BASE_URL}/outputs/{Path(voiceover_audio_path).name}"

    print(f"[INFO] Results for {file_id}: {list(result_data.keys())}")
    await manager.send_progress(file_id, 100, "completed", result_data["download_url"], result_data)
    cleanup_source_file(v_path, out_path)
