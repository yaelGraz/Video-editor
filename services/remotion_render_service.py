"""
Remotion Render Service
Renders video effects using the Remotion CLI (npx remotion render).
Supports: Camera Shake, Particles, Dynamic Zoom, Sound Waves, Lyrics overlay.
"""
import os
import json
import subprocess
import uuid
import re
import multiprocessing
from pathlib import Path

from utils.config import BASE_DIR, OUTPUTS_DIR, SERVER_BASE_URL

# Path to the Remotion project
REMOTION_DIR = BASE_DIR / "remotion-renderer"
REMOTION_ENTRY = REMOTION_DIR / "src" / "index.ts"

# Map our animation style IDs to Remotion LyricsStyle values
STYLE_TO_REMOTION_STYLE = {
    "karaoke": "karaoke",
    "bounce": "karaoke",
    "cinematic": "fade",
    "neon": "minimal",
}


def _parse_srt_to_lyrics_data(srt_path: str) -> dict:
    """Parse an SRT file into LyricsData JSON for Remotion props."""
    lines = []
    content = Path(srt_path).read_text(encoding="utf-8")
    # Normalize line endings
    content = content.replace("\r\n", "\n")
    entries = re.split(r"\n\n+", content.strip())

    for entry in entries:
        entry_lines = entry.strip().split("\n")
        if len(entry_lines) < 3:
            continue

        time_line = entry_lines[1]
        text = " ".join(entry_lines[2:])

        time_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
            time_line,
        )
        if not time_match:
            continue

        start_time = _parse_srt_time(time_match.group(1))
        end_time = _parse_srt_time(time_match.group(2))

        word_texts = [w for w in text.split() if w]
        if not word_texts:
            continue

        total_duration = end_time - start_time
        word_duration = total_duration / len(word_texts)

        words = []
        for idx, word in enumerate(word_texts):
            emphasis = "normal"
            if word.endswith("!") or (len(word) > 2 and word == word.upper()):
                emphasis = "hero"
            elif "?" in word or '"' in word:
                emphasis = "strong"

            words.append({
                "word": word,
                "start": round(start_time + idx * word_duration, 3),
                "end": round(start_time + (idx + 1) * word_duration, 3),
                "emphasis": emphasis,
            })

        lines.append({
            "lineStart": round(start_time, 3),
            "lineEnd": round(end_time, 3),
            "words": words,
        })

    duration = lines[-1]["lineEnd"] if lines else 0
    return {"lines": lines, "duration": duration}


def _parse_srt_time(time_str: str) -> float:
    """Convert SRT timestamp to seconds."""
    time_str = time_str.replace(",", ".")
    parts = time_str.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def _ensure_remotion_installed() -> bool:
    """Check if Remotion dependencies are installed, install if not."""
    node_modules = REMOTION_DIR / "node_modules"
    if node_modules.exists() and (node_modules / "remotion").exists():
        return True

    print("[Remotion] Installing dependencies...")
    try:
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(REMOTION_DIR),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120,
            shell=True,
        )
        if result.returncode != 0:
            print(f"[Remotion] npm install failed: {result.stderr}")
            return False
        print("[Remotion] Dependencies installed successfully")
        return True
    except Exception as e:
        print(f"[Remotion] Install error: {e}")
        return False


def _corrected_entries_to_lyrics_data(entries: list) -> dict:
    """Convert corrected subtitle entries from the frontend into LyricsData JSON."""
    lines = []
    for entry in entries:
        text = entry.get("text", "")
        start_time = float(entry.get("start", 0))
        end_time = float(entry.get("end", 0))

        word_texts = [w for w in text.split() if w]
        if not word_texts:
            continue

        total_duration = end_time - start_time
        word_duration = total_duration / len(word_texts) if len(word_texts) > 0 else 0

        words = []
        for idx, word in enumerate(word_texts):
            emphasis = "normal"
            if word.endswith("!") or (len(word) > 2 and word == word.upper()):
                emphasis = "hero"
            elif "?" in word or '"' in word:
                emphasis = "strong"

            words.append({
                "word": word,
                "start": round(start_time + idx * word_duration, 3),
                "end": round(start_time + (idx + 1) * word_duration, 3),
                "emphasis": emphasis,
            })

        lines.append({
            "lineStart": round(start_time, 3),
            "lineEnd": round(end_time, 3),
            "words": words,
        })

    duration = lines[-1]["lineEnd"] if lines else 0
    return {"lines": lines, "duration": duration}


def render_effects_video(
    video_path: str,
    srt_path: str,
    audio_source_path: str = None,
    animation_style: str = "karaoke",
    highlight_color: str = "#FF6B35",
    subtitle_position: str = "bottom",
    subtitle_size: int = 56,
    # Camera Effects
    camera_shake_enabled: bool = False,
    camera_shake_intensity: float = 0.5,
    # Ambience Layers
    particles_enabled: bool = False,
    dynamic_zoom_enabled: bool = False,
    # Sound Waves
    sound_waves_enabled: bool = False,
    visualizer_style: str = "bars",
    # Global Controls
    effect_strength: float = 0.7,
    dominant_color: str = "#00D1C1",
    # Trim
    trim_start: float = 0.0,
    trim_end: float = 0.0,
    # Corrected subtitles
    corrected_entries: list = None,
    fps: int = 25,
    progress_callback=None,
) -> dict:
    """
    Render a video with effects overlays using Remotion.

    Args:
        video_path: Path to the input video file
        srt_path: Path to the SRT subtitle file
        animation_style: One of 'karaoke', 'bounce', 'cinematic', 'neon'
        highlight_color: Hex color for highlighted words
        subtitle_position: 'bottom', 'center', or 'top'
        subtitle_size: Font size for subtitles
        camera_shake_enabled: Enable spring-based camera shake
        camera_shake_intensity: 0..1 shake intensity
        particles_enabled: Enable floating particles
        dynamic_zoom_enabled: Enable Ken Burns zoom
        sound_waves_enabled: Enable audio visualizer overlay
        visualizer_style: 'bars', 'wave', or 'circle'
        effect_strength: 0..1 master effect multiplier
        dominant_color: Hex color for particles, waves
        fps: Frames per second
        progress_callback: Optional callback(progress, message)

    Returns:
        dict with 'output_path' and 'url' on success, or 'error' on failure
    """
    try:
        if progress_callback:
            progress_callback(5, "מכין את הפרמטרים...")

        # Validate input files
        if not Path(video_path).exists():
            return {"error": f"Video file not found: {video_path}"}
        if not Path(srt_path).exists():
            return {"error": f"SRT file not found: {srt_path}"}

        # Ensure Remotion is installed
        if progress_callback:
            progress_callback(10, "בודק תלויות Remotion...")

        if not _ensure_remotion_installed():
            return {"error": "Failed to install Remotion dependencies"}

        # Parse subtitles: use corrected entries from frontend if available
        if progress_callback:
            progress_callback(15, "מעבד כתוביות...")

        if corrected_entries and len(corrected_entries) > 0:
            print(f"[Remotion] Using {len(corrected_entries)} corrected subtitle entries from frontend")
            # Log first and last entry to verify full range
            first = corrected_entries[0]
            last = corrected_entries[-1]
            print(f"[Remotion] Entries range: first={first.get('start',0):.1f}s-{first.get('end',0):.1f}s, last={last.get('start',0):.1f}s-{last.get('end',0):.1f}s")
            lyrics_data = _corrected_entries_to_lyrics_data(corrected_entries)
        else:
            print(f"[Remotion] No corrected entries, parsing SRT file: {srt_path}")
            lyrics_data = _parse_srt_to_lyrics_data(srt_path)

        if not lyrics_data["lines"]:
            return {"error": "No subtitle entries found in SRT file"}

        # Log lyrics data summary
        print(f"[Remotion] Lyrics data: {len(lyrics_data['lines'])} lines, duration={lyrics_data['duration']:.1f}s")
        if lyrics_data["lines"]:
            first_line = lyrics_data["lines"][0]
            last_line = lyrics_data["lines"][-1]
            print(f"[Remotion] First line: {first_line['lineStart']:.1f}s-{first_line['lineEnd']:.1f}s ({len(first_line['words'])} words)")
            print(f"[Remotion] Last line: {last_line['lineStart']:.1f}s-{last_line['lineEnd']:.1f}s ({len(last_line['words'])} words)")

        # Calculate duration in frames, applying trim if set
        from services.video_service import get_video_duration
        video_duration = get_video_duration(video_path)

        # Apply trim range
        effective_start = trim_start if trim_start > 0 else 0
        effective_end = trim_end if trim_end > 0 else video_duration
        effective_end = min(effective_end, video_duration)
        trimmed_duration = effective_end - effective_start

        start_frame = int(effective_start * fps)
        duration_frames = int(trimmed_duration * fps)

        print(f"[Remotion] Trim: {effective_start:.1f}s - {effective_end:.1f}s (duration: {trimmed_duration:.1f}s, frames: {start_frame}-{start_frame + duration_frames})")

        # Always use the new EffectsComposition
        composition_id = "EffectsComposition"
        remotion_style = STYLE_TO_REMOTION_STYLE.get(animation_style, "karaoke")

        # Build props - serve video via HTTP (Remotion's OffthreadVideo requires http/https)
        video_filename = Path(video_path).name
        # Determine if the video is in inputs or outputs directory
        if str(OUTPUTS_DIR) in str(Path(video_path).resolve()):
            video_src = f"{SERVER_BASE_URL}/outputs/{video_filename}"
        else:
            video_src = f"{SERVER_BASE_URL}/inputs/{video_filename}"

        props = {
            # Video
            "videoSrc": video_src,
            "useOffthreadVideo": True,
            # Dynamic duration - tells calculateMetadata the real frame count
            "durationInFrames": duration_frames,
            # Lyrics / Subtitles
            "lyrics": lyrics_data,
            "subtitleStyle": remotion_style,
            "fontSize": subtitle_size,
            "position": subtitle_position,
            "primaryColor": "#FFFFFF",
            "highlightColor": highlight_color,
            "fontFamily": "system-ui, -apple-system, sans-serif",
            "showGradientOverlay": True,
            # Camera Effects
            "cameraShakeEnabled": camera_shake_enabled,
            "cameraShakeIntensity": camera_shake_intensity,
            # Ambience Layers
            "particlesEnabled": particles_enabled,
            "dynamicZoomEnabled": dynamic_zoom_enabled,
            # Sound Waves
            "soundWavesEnabled": sound_waves_enabled,
            "soundWavesStyle": visualizer_style,
            # Global
            "effectStrength": effect_strength,
            "dominantColor": dominant_color,
        }

        # Write props to temp file
        props_file = OUTPUTS_DIR / f"remotion_props_{uuid.uuid4().hex[:8]}.json"
        props_json = json.dumps(props, ensure_ascii=False)
        props_file.write_text(props_json, encoding="utf-8")
        print(f"[Remotion] Props file: {props_file} ({len(props_json)} bytes, {len(props['lyrics']['lines'])} lyric lines)")

        # Output file
        output_filename = f"effects_{uuid.uuid4().hex[:8]}.mp4"
        output_path = OUTPUTS_DIR / output_filename

        if progress_callback:
            progress_callback(20, "מתחיל רינדור...")

        # Log active effects
        active = []
        if camera_shake_enabled:
            active.append(f"CameraShake({camera_shake_intensity:.0%})")
        if particles_enabled:
            active.append("Particles")
        if dynamic_zoom_enabled:
            active.append("DynamicZoom")
        if sound_waves_enabled:
            active.append(f"SoundWaves({visualizer_style})")
        print(f"[Remotion] Active effects: {', '.join(active) if active else 'None'}")
        print(f"[Remotion] Effect strength: {effect_strength:.0%}, Color: {dominant_color}")

        # Build Remotion CLI command
        # Duration is set via props.durationInFrames + calculateMetadata in Root.tsx
        cpu_total = multiprocessing.cpu_count()
        cpu_render = max(1, cpu_total - 2)  # Leave 2 cores free for OS/browser

        cmd = [
            "npx", "remotion", "render",
            str(REMOTION_ENTRY),
            composition_id,
            str(output_path),
            f"--props={str(props_file)}",
            f"--fps={fps}",
            "--codec=h264",
            "--crf=18",
            # --- Performance optimizations ---
            f"--concurrency={cpu_render}",       # Leave 2 cores free for OS responsiveness
            "--gl=angle",                        # GPU-accelerated rendering on Windows
            "--x264-preset=fast",                # Faster H.264 encoding with minimal quality loss
            "--jpeg-quality=80",                 # Slightly lower intermediate frame quality (faster I/O)
            "--overwrite",                       # Don't prompt if output exists
        ]

        print(f"[Remotion] Concurrency: {cpu_render}/{cpu_total} cores, GL: angle, Preset: fast")
        print(f"[Remotion] Running: {' '.join(cmd)}")
        print(f"[Remotion] CWD: {REMOTION_DIR}")

        # Run render
        process = subprocess.Popen(
            cmd,
            cwd=str(REMOTION_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
        )

        # Stream output and parse progress
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            print(f"[Remotion] {line}")

            # Parse progress from Remotion output (e.g., "Rendering frame 50/300")
            frame_match = re.search(r"(\d+)/(\d+)", line)
            if frame_match and progress_callback:
                current = int(frame_match.group(1))
                total = int(frame_match.group(2))
                pct = 20 + int((current / max(total, 1)) * 70)
                progress_callback(min(pct, 90), f"מרנדר פריים {current}/{total}")

        process.wait()

        # Clean up props file
        try:
            props_file.unlink()
        except Exception:
            pass

        if process.returncode != 0:
            return {"error": f"Remotion render failed (exit code {process.returncode})"}

        if not output_path.exists():
            return {"error": "Render completed but output file not found"}

        if progress_callback:
            progress_callback(92, "ממזג אודיו מהסרטון המקורי...")

        # --- Post-process: merge audio from source video into Remotion output ---
        # Remotion renders visual effects only. Use FFmpeg to take video from
        # Remotion output + audio from the _final.mp4 (which has background music).
        audio_src = audio_source_path or video_path
        final_output_filename = f"effects_final_{uuid.uuid4().hex[:8]}.mp4"
        final_output_path = OUTPUTS_DIR / final_output_filename

        ffmpeg_merge_cmd = [
            "ffmpeg", "-y",
            "-i", str(output_path),       # Remotion output (video with effects)
            "-i", str(audio_src),          # Audio source (_final.mp4 with background music)
            "-c:v", "copy",                # Copy video stream as-is (no re-encode)
            "-c:a", "aac", "-b:a", "192k", # Encode audio as AAC
            "-map", "0:v:0",              # Video from Remotion output
            "-map", "1:a:0",              # Audio from source (_final has music)
            "-shortest",                   # Match shorter stream duration
            str(final_output_path),
        ]

        print(f"[Remotion] Merging audio from: {audio_src}")
        print(f"[Remotion] Merging into: {final_output_path}")
        try:
            merge_result = subprocess.run(
                ffmpeg_merge_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=120,
            )
            if merge_result.returncode == 0 and final_output_path.exists():
                # Audio merge succeeded - use the merged file
                print(f"[Remotion] Audio merge successful: {final_output_path}")
                # Remove the intermediate Remotion-only output
                try:
                    output_path.unlink()
                except Exception:
                    pass
                output_path = final_output_path
                output_filename = final_output_filename
            else:
                # Audio merge failed - fall back to Remotion output (no audio)
                print(f"[Remotion] Audio merge failed (rc={merge_result.returncode}), using Remotion output without merged audio")
                if merge_result.stderr:
                    print(f"[Remotion] FFmpeg stderr: {merge_result.stderr[:500]}")
        except Exception as e:
            print(f"[Remotion] Audio merge error: {e}, using Remotion output without merged audio")

        if progress_callback:
            progress_callback(100, "הרינדור הושלם!")

        output_url = f"/outputs/{output_filename}"
        print(f"[Remotion] Render complete: {output_path}")

        return {
            "output_path": str(output_path),
            "url": output_url,
            "filename": output_filename,
        }

    except Exception as e:
        print(f"[Remotion] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
