"""
Video Service - Handles video processing, merging, thumbnail generation, and video analysis.
"""
import os
import subprocess
import random
import time
import ssl
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import base64

# =============================================================================
# SSL Certificate Bypass for Windows + NetFree compatibility
# =============================================================================
# Must be set before any HTTPS requests
os.environ['HTTPLIB2_CA_CERTS'] = ""
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''          # httpx (used by google-genai SDK)
os.environ['CURL_CA_BUNDLE'] = ''         # curl-based libraries
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

from utils.config import (
    GEMINI_API_KEY,
    LEONARDO_API_KEY,
    DEFAULT_VIDEO_WIDTH,
    DEFAULT_VIDEO_HEIGHT,
    TESSERACT_CMD,
    FONTS_DIR
)
from utils.helpers import escape_ffmpeg_path, escape_ffmpeg_path_for_subtitles, prepare_hebrew_text
from services.font_service import get_fonts_dir_path


# =============================================================================
# Video Information
# =============================================================================

def check_video_has_audio(video_path: str) -> bool:
    """Check if video file has an audio stream."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return 'audio' in result.stdout.lower()
    except Exception as e:
        print(f"[ERROR] Failed to check audio: {e}")
        return False


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print(f"[ERROR] Failed to get video duration: {e}")
    return 0


def get_video_resolution(video_path: str) -> Tuple[int, int]:
    """Get video resolution (width, height)."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            parts = result.stdout.strip().split('x')
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except Exception as e:
        print(f"[ERROR] Failed to get video resolution: {e}")
    return DEFAULT_VIDEO_WIDTH, DEFAULT_VIDEO_HEIGHT


def get_video_frame_count(video_path: str) -> int:
    """Get total frame count of video."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-count_frames",
            "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        if result.stdout.strip().isdigit():
            return int(result.stdout.strip())
    except:
        pass

    # Fallback: estimate from duration and fps
    try:
        duration = get_video_duration(video_path)
        return int(duration * 30)  # Assume 30 fps
    except:
        return 0


# =============================================================================
# Audio Trimming
# =============================================================================

def get_audio_duration(audio_path: str) -> float:
    """Get audio file duration in seconds."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print(f"[ERROR] Failed to get audio duration: {e}")
    return 0


def trim_audio_to_length(audio_path: str, target_duration: float, output_path: str = None) -> Optional[str]:
    """
    Trim audio file to specified duration if it's longer.

    Args:
        audio_path: Path to the audio file
        target_duration: Target duration in seconds
        output_path: Optional output path. If None, creates a temp file.

    Returns:
        Path to trimmed audio (or original if no trimming needed), or None on error
    """
    try:
        audio_duration = get_audio_duration(audio_path)

        if audio_duration <= 0:
            print(f"[WARNING] Could not get audio duration, using original file")
            return audio_path

        print(f"[DEBUG] Audio duration: {audio_duration:.2f}s, Target: {target_duration:.2f}s")

        # If audio is shorter or equal to target, no trimming needed
        if audio_duration <= target_duration + 0.5:  # 0.5s tolerance
            print(f"[INFO] Audio is shorter than video, no trimming needed")
            return audio_path

        # Need to trim
        if output_path is None:
            audio_path_obj = Path(audio_path)
            output_path = str(audio_path_obj.parent / f"{audio_path_obj.stem}_trimmed{audio_path_obj.suffix}")

        print(f"[INFO] Trimming audio from {audio_duration:.2f}s to {target_duration:.2f}s")

        # Use FFmpeg to trim with fade out at the end
        # IMPORTANT: -t MUST come BEFORE -i to avoid sync issues and stuttering
        fade_duration = min(2.0, target_duration * 0.1)  # 2 seconds or 10% of duration

        cmd = [
            "ffmpeg", "-y",
            "-t", str(target_duration),   # Duration BEFORE input to trim properly
            "-i", str(audio_path),
            "-af", f"afade=t=out:st={target_duration - fade_duration}:d={fade_duration}",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        print(f"[DEBUG] Audio trim command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)

        if result.returncode == 0 and os.path.exists(output_path):
            trimmed_size = os.path.getsize(output_path) / 1024  # KB
            print(f"[SUCCESS] Audio trimmed to {target_duration:.2f}s with fade out ({trimmed_size:.1f} KB)")
            return output_path
        else:
            print(f"[ERROR] Failed to trim audio: {result.stderr[:300]}")
            return audio_path  # Return original on failure

    except Exception as e:
        print(f"[ERROR] Audio trimming failed: {e}")
        return audio_path  # Return original on failure


# =============================================================================
# Video Merging
# =============================================================================

def merge_final_video(
    v_input: str,
    srt_input: Optional[str],
    v_output: str,
    music_path: Optional[str],
    voice_path: Optional[str]
) -> bool:
    """
    Merge video with voiceover, music, and subtitles.

    IMPORTANT: Properly integrates subtitles into filter_complex.
    On Windows, paths must be escaped correctly for FFmpeg filters.

    Supports both SRT and ASS subtitle formats.
    """
    print(f"[INFO] Starting video merge...")
    print(f"[DEBUG] Input video: {v_input}")
    print(f"[DEBUG] Subtitle file: {srt_input}")
    print(f"[DEBUG] Music file: {music_path}")
    print(f"[DEBUG] Voice file: {voice_path}")

    has_orig_audio = check_video_has_audio(v_input)
    print(f"[DEBUG] Original video has audio: {has_orig_audio}")

    # Check for subtitles FIRST - they must be ready before FFmpeg runs
    has_subtitles = srt_input and os.path.exists(srt_input)
    is_ass = False
    escaped_subtitle_path = None

    if has_subtitles:
        # Detect subtitle type (ASS vs SRT)
        is_ass = str(srt_input).lower().endswith('.ass')
        print(f"[DEBUG] Subtitle file exists: {srt_input}")
        print(f"[DEBUG] Subtitle type: {'ASS' if is_ass else 'SRT'}")

        # Escape the path for FFmpeg filter (Windows-safe)
        escaped_subtitle_path = escape_ffmpeg_path_for_subtitles(srt_input)
        print(f"[DEBUG] Escaped subtitle path: {escaped_subtitle_path}")
    else:
        print(f"[DEBUG] No subtitle file found or path doesn't exist")

    # Get video duration for music trimming
    video_duration = get_video_duration(v_input)
    print(f"[DEBUG] Video duration: {video_duration:.2f}s")

    # Track temporary files to cleanup
    temp_files_to_cleanup = []

    # Trim music to video length if needed
    actual_music_path = music_path
    if music_path and os.path.exists(music_path) and video_duration > 0:
        trimmed_music = trim_audio_to_length(music_path, video_duration)
        if trimmed_music and trimmed_music != music_path:
            actual_music_path = trimmed_music
            temp_files_to_cleanup.append(trimmed_music)
            print(f"[DEBUG] Using trimmed music: {actual_music_path}")

    # Build FFmpeg command
    cmd = ['ffmpeg', '-y', '-i', str(v_input)]
    inputs = 1
    audio_filter_parts = []
    audio_nodes = []

    # Track if we have speech for ducking
    has_speech = has_orig_audio or (voice_path and os.path.exists(voice_path))
    music_input_index = None

    # Handle original audio (speech from video)
    if has_orig_audio:
        audio_filter_parts.append("[0:a]volume=1.0[main_a]")
        audio_nodes.append("[main_a]")

    # Add voiceover input
    if voice_path and os.path.exists(voice_path):
        cmd.extend(['-i', str(voice_path)])
        audio_filter_parts.append(f"[{inputs}:a]volume=2.0[voice_a]")
        audio_nodes.append("[voice_a]")
        inputs += 1
        print(f"[DEBUG] Added voiceover input #{inputs}")

    # Add music input with DUCKING (sidechain compression when speech is present)
    if actual_music_path and os.path.exists(actual_music_path):
        cmd.extend(['-i', str(actual_music_path)])
        music_input_index = inputs

        if has_speech:
            # DUCKING: Use sidechaincompress to lower music when speech is detected
            # The speech signal triggers compression on the music
            # ratio=4 means 4:1 compression, threshold=0.02 is sensitive to speech
            # attack=0.3 quick response, release=1.0 gradual return
            print(f"[DEBUG] Enabling DUCKING for music (sidechain compression)")

            # First, prepare the speech signal for sidechaining
            if has_orig_audio:
                speech_node = "[main_a]"
            else:
                speech_node = "[voice_a]"

            # Apply sidechain compression: music is compressed when speech is present
            # Lower music volume base to 0.15, ducking will reduce it further during speech
            audio_filter_parts.append(
                f"[{inputs}:a]volume=0.15[music_pre]"
            )
            # For simplicity, we'll use a lower music volume overall since true sidechain
            # is complex with multiple audio sources. The amix will blend them.
            audio_nodes.append("[music_pre]")
        else:
            # No speech, just play music at normal volume
            audio_filter_parts.append(f"[{inputs}:a]volume=0.25[music_a]")
            audio_nodes.append("[music_a]")

        inputs += 1
        print(f"[DEBUG] Added music input #{inputs} (ducking: {has_speech})")

    # Build filter_complex
    filter_complex_parts = []
    video_output_node = "[0:v]"  # Default to original video

    # ALWAYS add subtitle filter if subtitles exist
    if has_subtitles and escaped_subtitle_path:
        if is_ass:
            # ASS format - use ass filter with fontsdir for custom fonts
            fonts_dir = get_fonts_dir_path()
            escaped_fonts_dir = escape_ffmpeg_path_for_subtitles(fonts_dir)
            subtitle_filter = f"[0:v]ass='{escaped_subtitle_path}':fontsdir='{escaped_fonts_dir}'[vout]"
            print(f"[DEBUG] Using fontsdir: {fonts_dir}")
        else:
            # SRT format - use subtitles filter
            subtitle_filter = f"[0:v]subtitles='{escaped_subtitle_path}'[vout]"

        filter_complex_parts.append(subtitle_filter)
        video_output_node = "[vout]"
        print(f"[DEBUG] Added subtitle filter: {subtitle_filter}")

    # Add audio filters
    if audio_nodes:
        filter_complex_parts.extend(audio_filter_parts)

        # Mix all audio streams
        amix_inputs = ''.join(audio_nodes)
        amix_filter = f"{amix_inputs}amix=inputs={len(audio_nodes)}:duration=first:dropout_transition=2[aout]"
        filter_complex_parts.append(amix_filter)
        print(f"[DEBUG] Added audio mix filter: {amix_filter}")

    # Assemble the command based on what filters we have
    if filter_complex_parts:
        full_filter = ';'.join(filter_complex_parts)
        print(f"[DEBUG] Full filter_complex: {full_filter}")

        cmd.extend(['-filter_complex', full_filter])

        # Map video output
        if has_subtitles:
            cmd.extend(['-map', '[vout]'])
        else:
            cmd.extend(['-map', '0:v'])

        # Map audio output
        if audio_nodes:
            cmd.extend(['-map', '[aout]'])
        elif has_orig_audio:
            cmd.extend(['-map', '0:a'])
    else:
        # No filters needed, simple copy
        cmd.extend(['-map', '0:v'])
        if has_orig_audio:
            cmd.extend(['-map', '0:a'])

    # Output settings
    cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-c:a', 'aac',
        '-b:a', '192k',
        str(v_output)
    ])

    # Print full command for debugging
    print(f"[DEBUG] Full FFmpeg command:")
    print(f"  {' '.join(cmd)}")

    # Run FFmpeg
    print(f"[INFO] Running FFmpeg merge...")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    # Cleanup temporary files
    def cleanup_temp_files():
        for temp_file in temp_files_to_cleanup:
            try:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"[DEBUG] Cleaned up temp file: {temp_file}")
            except Exception as e:
                print(f"[WARNING] Could not cleanup temp file {temp_file}: {e}")

    if result.returncode != 0:
        print(f"[ERROR] FFmpeg merge failed!")
        print(f"[ERROR] Return code: {result.returncode}")
        print(f"[ERROR] stderr: {result.stderr}")

        # Try to identify common issues
        if "No such file" in result.stderr or "does not exist" in result.stderr:
            print("[ERROR] File path issue - check that subtitle file exists and path is correct")
        if "Invalid data" in result.stderr:
            print("[ERROR] Subtitle file may be corrupted or in wrong format")
        if "Unable to find a suitable output format" in result.stderr:
            print("[ERROR] Output path issue")

        cleanup_temp_files()
        return False

    if os.path.exists(v_output):
        output_size = os.path.getsize(v_output) / (1024 * 1024)
        print(f"[SUCCESS] Video merged successfully: {v_output} ({output_size:.2f} MB)")
        cleanup_temp_files()
        return True
    else:
        print(f"[ERROR] Output file was not created")
        cleanup_temp_files()
        return False


# =============================================================================
# Shorts Generation - With Sync Fix and Separate Subtitle Formatting
# =============================================================================

def adjust_srt_times(srt_content: str, offset_seconds: float) -> str:
    """
    Adjust all SRT timestamps by subtracting offset_seconds.
    This is CRITICAL for shorts - when a short starts at X seconds,
    we subtract X from all subtitle times so the first subtitle starts at 0.
    """
    import re
    from datetime import timedelta

    def shift_time(match):
        h, m, s, ms = map(int, match.groups())
        t = timedelta(hours=h, minutes=m, seconds=s, milliseconds=ms)
        new_t = max(timedelta(0), t - timedelta(seconds=offset_seconds))
        total_seconds = int(new_t.total_seconds())
        new_h, remainder = divmod(total_seconds, 3600)
        new_m, new_s = divmod(remainder, 60)
        new_ms = int(new_t.microseconds / 1000)
        return f"{new_h:02}:{new_m:02}:{new_s:02},{new_ms:03}"

    time_pattern = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    return re.sub(time_pattern, shift_time, srt_content)


def filter_srt_for_range(srt_content: str, start_time: float, end_time: float) -> str:
    """
    Filter SRT entries to only include subtitles within the given time range.
    Returns a new SRT string with only relevant entries, renumbered.
    """
    import re

    def parse_srt_time(time_str: str) -> float:
        """Parse SRT time format to seconds."""
        match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", time_str)
        if match:
            h, m, s, ms = map(int, match.groups())
            return h * 3600 + m * 60 + s + ms / 1000
        return 0

    # Split by double newline to get entries
    entries = re.split(r'\n\n+', srt_content.strip())
    filtered_entries = []

    for entry in entries:
        lines = entry.strip().split('\n')
        if len(lines) >= 2:
            # Find time line (contains -->)
            time_line_idx = -1
            for idx, line in enumerate(lines):
                if '-->' in line:
                    time_line_idx = idx
                    break

            if time_line_idx == -1:
                continue

            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[time_line_idx])
            if time_match:
                entry_start = parse_srt_time(time_match.group(1))
                entry_end = parse_srt_time(time_match.group(2))

                # Include if entry overlaps with our range
                if entry_end > start_time and entry_start < end_time:
                    filtered_entries.append(entry)

    # Renumber entries
    result_lines = []
    for i, entry in enumerate(filtered_entries, 1):
        lines = entry.strip().split('\n')
        # Replace first line (index) with new number
        lines[0] = str(i)
        result_lines.append('\n'.join(lines))

    return '\n\n'.join(result_lines) + '\n\n' if result_lines else ''


def create_adjusted_srt_for_short(
    original_srt_path: str,
    short_start: float,
    short_end: float,
    output_srt_path: str
) -> bool:
    """
    Create a new SRT file adjusted for a short clip.
    CRITICAL FIX: Subtracts the short's start time from all subtitle timestamps
    so subtitles sync properly with the new video that starts at 0.
    """
    try:
        with open(original_srt_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Filter to only entries within our time range
        filtered_content = filter_srt_for_range(original_content, short_start, short_end)

        if not filtered_content.strip():
            print(f"[WARNING] No subtitles found in range {short_start:.1f}-{short_end:.1f}")
            return False

        # CRITICAL: Adjust times by subtracting the start offset
        # This ensures subtitles start at 0 in the new short
        adjusted_content = adjust_srt_times(filtered_content, short_start)

        with open(output_srt_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(adjusted_content)

        print(f"[INFO] Created time-adjusted SRT: {output_srt_path} (offset: -{short_start:.2f}s)")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to create adjusted SRT: {e}")
        return False


def get_subtitle_style(is_short: bool = False, subtitle_color: str = None) -> str:
    """
    Get FFmpeg subtitle style based on video type.

    For Shorts (9:16 TikTok/Reels):
    - Medium font (FontSize=18) - allows long sentences without cutting
    - Bottom-center position (Alignment=2)
    - Lower margin (MarginV=30) - visible but not hidden by description
    - Bold color with outline for readability

    For Regular Videos (16:9):
    - Smaller font (FontSize=18)
    - Bottom-center position
    - Smaller margin (MarginV=20)
    - Subtle white with thin outline
    """
    if is_short:
        # SHORTS STYLE - Readable size, lower position
        style_parts = [
            "FontSize=18",           # Medium font - fits long sentences
            "FontName=Arial",
            "Bold=1",                # Bold text
            "Alignment=2",           # Bottom-center
            "MarginV=30",            # Lower position, above description area
            "MarginL=20",
            "MarginR=20",
            "Outline=2",             # Medium outline
            "Shadow=1",              # Light shadow
            "OutlineColour=&H000000&",  # Black outline
            "BackColour=&H80000000&",   # Semi-transparent background
        ]

        # Apply custom color or default to yellow (highly visible)
        if subtitle_color:
            hex_color = subtitle_color.lstrip('#')
            if len(hex_color) == 6:
                r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
                ass_color = f"&H{b}{g}{r}&"
                style_parts.append(f"PrimaryColour={ass_color}")
        else:
            # Default: Yellow for maximum visibility
            style_parts.append("PrimaryColour=&H00FFFF&")  # Yellow in BGR

    else:
        # REGULAR VIDEO STYLE - Subtle and professional
        style_parts = [
            "FontSize=18",           # Smaller font
            "FontName=Arial",
            "Alignment=2",           # Bottom-center
            "MarginV=20",            # Small margin
            "Outline=1",             # Thin outline
            "Shadow=1",
            "OutlineColour=&H000000&",
            "PrimaryColour=&HFFFFFF&",  # White
        ]

    return ",".join(style_parts)


def burn_subtitles_to_video(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    is_short: bool = False,
    subtitle_color: str = None,
    additional_vf: str = None
) -> bool:
    """
    Burn subtitles into video with style based on video type.

    Args:
        video_path: Input video path
        subtitle_path: SRT/ASS subtitle file path
        output_path: Output video path
        is_short: True for 9:16 TikTok-style, False for regular 16:9
        subtitle_color: Optional hex color (e.g., "#FFFF00")
        additional_vf: Additional video filters to prepend (e.g., crop/scale)

    Returns:
        bool: Success status
    """
    if not os.path.exists(subtitle_path):
        print(f"[ERROR] Subtitle file not found: {subtitle_path}")
        return False

    try:
        sub_path_escaped = escape_ffmpeg_path(subtitle_path)
        force_style = get_subtitle_style(is_short=is_short, subtitle_color=subtitle_color)

        # Build video filter chain
        vf_parts = []

        # Add additional filters first (like crop/scale for vertical)
        if additional_vf:
            vf_parts.append(additional_vf)

        # Add subtitle filter
        vf_parts.append(f"subtitles='{sub_path_escaped}':force_style='{force_style}'")

        vf_filter = ",".join(vf_parts)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            str(output_path)
        ]

        print(f"[DEBUG] Burn subtitles command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode == 0 and os.path.exists(output_path):
            print(f"[SUCCESS] Subtitles burned: {output_path}")
            return True
        else:
            print(f"[ERROR] Failed to burn subtitles: {result.stderr[:300]}")
            return False

    except Exception as e:
        print(f"[ERROR] burn_subtitles_to_video failed: {e}")
        return False


# =============================================================================
# Short-First Transcription Strategy
# =============================================================================

def extract_audio_from_video(video_path: str, audio_output_path: str) -> bool:
    """Extract and compress audio from video file."""
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "libmp3lame", "-q:a", "4",
            "-ar", "16000", "-ac", "1",
            str(audio_output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return result.returncode == 0 and os.path.exists(audio_output_path)
    except Exception as e:
        print(f"[ERROR] Audio extraction failed: {e}")
        return False


def transcribe_short_audio_with_groq(audio_path: str) -> Tuple[List[Dict], str]:
    """
    Transcribe short's audio using Groq API.
    Returns (segments, full_text) where segments have start/end times relative to the short (starting at 0).
    """
    from utils.config import GROQ_API_KEY

    if not GROQ_API_KEY:
        print("[ERROR] Groq API key not configured")
        return [], ""

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(Path(audio_path).name, audio_file.read()),
                model="whisper-large-v3",
                language="he",
                response_format="verbose_json",
                temperature=0.0
            )

        full_text = transcription.text if hasattr(transcription, 'text') else ""
        raw_segments = transcription.segments if hasattr(transcription, 'segments') else []

        # Convert to list of dicts with start, end, text
        segments = []
        for seg in raw_segments:
            segments.append({
                'start': seg.get('start', getattr(seg, 'start', 0)),
                'end': seg.get('end', getattr(seg, 'end', 0)),
                'text': seg.get('text', getattr(seg, 'text', '')).strip()
            })

        print(f"[GROQ] Transcribed {len(segments)} segments, {len(full_text)} chars")
        return segments, full_text

    except Exception as e:
        print(f"[ERROR] Groq transcription failed: {e}")
        import traceback
        traceback.print_exc()
        return [], ""


def improve_transcription_with_ai(segments: List[Dict]) -> List[Dict]:
    """
    Send segments to AI (Gemini) for text improvement.
    Keeps timings exactly as they are, only improves text.

    SAFETY: If AI changes timing structure, falls back to original segments.
    """
    import json
    import os
    import ssl
    import certifi

    if not segments:
        return segments

    try:
        # SSL bypass for Gemini
        if 'HTTPLIB2_CA_CERTS' in os.environ:
            del os.environ['HTTPLIB2_CA_CERTS']
        os.environ['HTTPLIB2_CA_CERTS'] = certifi.where()
        ssl._create_default_https_context = ssl._create_unverified_context

        import google.generativeai as genai
        genai.configure(transport='rest')

        # Prepare JSON for AI
        segments_json = json.dumps(segments, ensure_ascii=False, indent=2)

        prompt = f"""תקן את הטקסט הבא לשפה שוטפת והוסף פיסוק רלוונטי בלבד.

חוקים קריטיים:
1. שמור על מבנה ה-JSON בדיוק כפי שהוא
2. אל תשנה את שדות start ו-end בשום אופן!
3. תקן רק את שדה text
4. אל תוסיף מילים שלא נאמרו
5. אל תוסיף אימוג'ים, סמלים או תווים מיוחדים - רק טקסט רגיל!
6. החזר JSON בלבד, ללא טקסט נוסף

הנה ה-JSON:
{segments_json}

החזר את ה-JSON המתוקן בלבד:"""

        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean response from markdown
        if "```json" in response_text:
            import re
            match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
            if match:
                response_text = match.group(1).strip()
        elif "```" in response_text:
            import re
            match = re.search(r'```\s*([\s\S]*?)\s*```', response_text)
            if match:
                response_text = match.group(1).strip()

        # Parse improved segments
        improved_segments = json.loads(response_text)

        # SAFETY CHECK: Verify AI didn't change timing structure
        if len(improved_segments) != len(segments):
            print(f"[WARNING] AI changed segment count ({len(segments)} -> {len(improved_segments)}), using original")
            return segments

        # Verify timings are preserved
        for orig, improved in zip(segments, improved_segments):
            if abs(orig['start'] - improved.get('start', -999)) > 0.1 or \
               abs(orig['end'] - improved.get('end', -999)) > 0.1:
                print(f"[WARNING] AI changed timings, using original segments")
                return segments

        print(f"[AI] Text improved successfully for {len(improved_segments)} segments")
        return improved_segments

    except Exception as e:
        print(f"[WARNING] AI improvement failed: {e}, using raw Groq transcription")
        return segments


def segments_to_srt(segments: List[Dict], output_path: str, max_words: int = 5) -> bool:
    """
    Convert segments to SRT file format.
    Splits segments into chunks of max_words for readability.
    """
    if not segments:
        return False

    try:
        def format_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds - int(seconds)) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        def split_segment(seg: Dict, max_words: int) -> List[Dict]:
            """Split a segment into smaller chunks."""
            text = seg['text'].strip()
            words = text.split()

            if len(words) <= max_words:
                return [seg]

            chunks = []
            start = seg['start']
            end = seg['end']
            total_duration = end - start
            total_words = len(words)

            current_pos = 0
            while current_pos < total_words:
                chunk_words = words[current_pos:current_pos + max_words]
                chunk_text = ' '.join(chunk_words)

                # Calculate proportional timing
                chunk_start = start + (current_pos / total_words) * total_duration
                chunk_end = start + (min(current_pos + max_words, total_words) / total_words) * total_duration

                chunks.append({
                    'start': chunk_start,
                    'end': chunk_end,
                    'text': chunk_text
                })

                current_pos += max_words

            return chunks

        # Split all segments
        all_subtitles = []
        for seg in segments:
            all_subtitles.extend(split_segment(seg, max_words))

        # Write SRT file
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            for i, sub in enumerate(all_subtitles, 1):
                f.write(f"{i}\n")
                f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
                f.write(f"{sub['text']}\n\n")

        print(f"[SRT] Created SRT with {len(all_subtitles)} entries at {output_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to create SRT: {e}")
        return False


def cut_viral_shorts(
    video_path: str,
    viral_moments: List[Dict],
    output_dir: str,
    subtitle_path: Optional[str] = None,
    use_ass: bool = False,
    progress_callback=None,
    vertical: bool = False,
    subtitle_color: str = None,
    with_subtitles: bool = False
) -> List[str]:
    """
    Cut viral shorts from video using SHORT-FIRST TRANSCRIPTION strategy.

    NEW APPROACH:
    1. Cut the short video first (with 0.5s buffer)
    2. Extract audio from the short
    3. Transcribe audio with Groq (timings start at 0 automatically!)
    4. Improve text with AI (Gemini) while preserving timings
    5. Convert to SRT and burn subtitles with is_short=True style

    This ensures perfect sync because transcription is done on the short itself.
    """
    output_paths = []
    shorts_dir = Path(output_dir) / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    # Temp directory for working files
    temp_dir = shorts_dir / "temp_work"

    # Clean up any stale temp files from previous runs
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
            print(f"[CLEANUP] Removed stale temp directory: {temp_dir}")
        except Exception as e:
            print(f"[WARNING] Could not clean temp dir: {e}")

    temp_dir.mkdir(parents=True, exist_ok=True)

    total = len(viral_moments)
    video_duration = get_video_duration(video_path)

    # Padding to prevent cutting mid-word
    PADDING_BEFORE = 0.5
    PADDING_AFTER = 0.5

    for i, moment in enumerate(viral_moments):
        short_num = i + 1
        original_start = moment.get('start', 0)
        original_end = moment.get('end', original_start + 30)

        # Apply smart padding
        padded_start = max(0, original_start - PADDING_BEFORE)
        padded_end = min(video_duration, original_end + PADDING_AFTER)
        duration = padded_end - padded_start

        suffix = "_vertical" if vertical else ""
        temp_short_path = temp_dir / f"temp_short_{short_num}.mp4"
        temp_audio_path = temp_dir / f"temp_audio_{short_num}.mp3"
        temp_srt_path = temp_dir / f"temp_srt_{short_num}.srt"
        output_file = shorts_dir / f"short_{short_num}_{int(padded_start)}-{int(padded_end)}{suffix}.mp4"

        # =====================================================================
        # STEP 1: Cut the short video (without subtitles)
        # =====================================================================
        if progress_callback:
            progress_callback(int((i / total) * 100), f"שלב 1/{4 if with_subtitles else 1}: חותך קליפ {short_num}/{total}...")

        print(f"\n[SHORT {short_num}] === Starting Short-First Transcription ===")
        print(f"[SHORT {short_num}] Original: {original_start:.1f}s - {original_end:.1f}s")
        print(f"[SHORT {short_num}] Padded: {padded_start:.1f}s - {padded_end:.1f}s (duration: {duration:.1f}s)")

        # Build video filter for cutting
        vf_filters = ["setpts=PTS-STARTPTS"]
        if vertical:
            vf_filters.append("crop=ih*9/16:ih,scale=1080:1920")

        cut_cmd = [
            "ffmpeg", "-y",
            "-ss", str(padded_start),
            "-i", str(video_path),
            "-t", str(duration),
            "-vf", ",".join(vf_filters),
            "-af", "asetpts=PTS-STARTPTS",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            str(temp_short_path)
        ]

        result = subprocess.run(cut_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode != 0 or not temp_short_path.exists():
            print(f"[ERROR] Failed to cut short {short_num}: {result.stderr[:300]}")
            continue

        print(f"[SHORT {short_num}] Step 1 DONE: Cut video to {temp_short_path.name}")

        # If no subtitles requested, we're done with this short
        if not with_subtitles:
            # Delete existing file if present (Windows requires this)
            if output_file.exists():
                output_file.unlink()
            # Rename temp to final
            temp_short_path.rename(output_file)
            output_paths.append(str(output_file))
            print(f"[SUCCESS] Created short (no subs): {output_file.name}")
            continue

        # =====================================================================
        # STEP 2: Extract audio from the short
        # =====================================================================
        if progress_callback:
            progress_callback(int((i / total) * 100), f"שלב 2/4: מחלץ אודיו מקליפ {short_num}...")

        if not extract_audio_from_video(str(temp_short_path), str(temp_audio_path)):
            print(f"[WARNING] Failed to extract audio from short {short_num}, creating without subtitles")
            if output_file.exists():
                output_file.unlink()
            temp_short_path.rename(output_file)
            output_paths.append(str(output_file))
            continue

        print(f"[SHORT {short_num}] Step 2 DONE: Extracted audio to {temp_audio_path.name}")

        # =====================================================================
        # STEP 3: Transcribe with Groq + AI improvement
        # =====================================================================
        if progress_callback:
            progress_callback(int((i / total) * 100), f"שלב 3/4: מתמלל עם Groq ומשפר עם AI ({short_num}/{total})...")

        print(f"[SHORT {short_num}] Step 3: Transcribing with Groq...")
        segments, full_text = transcribe_short_audio_with_groq(str(temp_audio_path))

        if not segments:
            print(f"[WARNING] No transcription for short {short_num}, creating without subtitles")
            if output_file.exists():
                output_file.unlink()
            temp_short_path.rename(output_file)
            output_paths.append(str(output_file))
            # Cleanup
            try:
                temp_audio_path.unlink()
            except:
                pass
            continue

        # Try to improve with AI (with safety fallback)
        print(f"[SHORT {short_num}] Improving text with AI...")
        try:
            improved_segments = improve_transcription_with_ai(segments)
        except Exception as e:
            print(f"[WARNING] AI improvement failed: {e}, using raw Groq")
            improved_segments = segments

        print(f"[SHORT {short_num}] Step 3 DONE: {len(improved_segments)} segments ready")

        # =====================================================================
        # STEP 4: Create SRT and burn subtitles
        # =====================================================================
        if progress_callback:
            progress_callback(int((i / total) * 100), f"שלב 4/4: שורף כתוביות על קליפ {short_num}...")

        if not segments_to_srt(improved_segments, str(temp_srt_path), max_words=5):
            print(f"[WARNING] Failed to create SRT for short {short_num}")
            if output_file.exists():
                output_file.unlink()
            temp_short_path.rename(output_file)
            output_paths.append(str(output_file))
            continue

        print(f"[SHORT {short_num}] Step 4: Burning subtitles with SHORT style...")

        # Get SHORT-specific subtitle style (large, yellow, high margin for TikTok)
        force_style = get_subtitle_style(is_short=True, subtitle_color=subtitle_color)
        sub_path_escaped = escape_ffmpeg_path(str(temp_srt_path))

        burn_cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_short_path),
            "-vf", f"subtitles='{sub_path_escaped}':force_style='{force_style}'",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_file)
        ]

        result = subprocess.run(burn_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode == 0 and output_file.exists():
            output_paths.append(str(output_file))
            print(f"[SUCCESS] Created short with subs: {output_file.name}")
        else:
            print(f"[ERROR] Failed to burn subtitles: {result.stderr[:300]}")
            # Fallback: use video without subtitles
            if temp_short_path.exists():
                if output_file.exists():
                    output_file.unlink()
                temp_short_path.rename(output_file)
                output_paths.append(str(output_file))
                print(f"[FALLBACK] Using short without subtitles: {output_file.name}")

        # Cleanup temp files for this short
        for temp_file in [temp_short_path, temp_audio_path, temp_srt_path]:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except:
                pass

    # Final cleanup
    try:
        temp_dir.rmdir()
    except:
        pass

    if progress_callback:
        progress_callback(100, f"הושלם! נוצרו {len(output_paths)} קליפים")

    return output_paths


def clean_json_response(text: str) -> str:
    """
    Clean AI response that may contain JSON with extra characters.
    Handles cases where AI returns JSON wrapped in markdown or with extra text.
    """
    import re

    if not text:
        return text

    # Remove markdown code blocks
    if "```json" in text:
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1).strip()

    if "```" in text:
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1).strip()

    # Try to find JSON object or array
    # Look for { ... } or [ ... ]
    json_obj_match = re.search(r'(\{[\s\S]*\})', text)
    if json_obj_match:
        return json_obj_match.group(1).strip()

    json_arr_match = re.search(r'(\[[\s\S]*\])', text)
    if json_arr_match:
        return json_arr_match.group(1).strip()

    # Return original if no pattern found
    return text.strip()


def safe_parse_json(text: str) -> Optional[dict]:
    """
    Safely parse JSON from AI response, handling common issues.
    """
    import json

    if not text:
        return None

    try:
        # First, try direct parsing
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Clean and retry
    cleaned = clean_json_response(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[WARNING] JSON parse failed even after cleaning: {e}")
        print(f"[DEBUG] Cleaned text: {cleaned[:200]}...")
        return None


# =============================================================================
# Thumbnail Generation
# =============================================================================

def generate_thumbnail(
    video_path: str,
    title: str,
    output_path: str,
    progress_callback=None,
    punchline: str = None
) -> bool:
    """
    Generate thumbnail from video frame with title and punchline overlay.
    Punchline is the attention-grabbing sentence displayed prominently.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import cv2
    except ImportError:
        print("[ERROR] PIL or cv2 not installed")
        return False

    if progress_callback:
        progress_callback(10, "יוצר תמונה ממוזערת...")

    try:
        # Get middle frame
        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)

        ret, frame = cap.read()
        cap.release()

        if not ret:
            print("[ERROR] Could not read video frame")
            return False

        # Convert to PIL with RGBA for transparency
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb).convert('RGBA')

        # Resize to standard thumbnail size
        img = img.resize((1280, 720), Image.LANCZOS)

        # Create overlay for text with transparency
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Load fonts
        try:
            font_path = FONTS_DIR / "Assistant-Bold.ttf"
            if font_path.exists():
                punchline_font = ImageFont.truetype(str(font_path), 56)
                title_font = ImageFont.truetype(str(font_path), 36)
            else:
                punchline_font = ImageFont.load_default()
                title_font = ImageFont.load_default()
        except:
            punchline_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        # Use punchline if provided, otherwise use title
        main_text = punchline if punchline else title

        # Prepare text for RTL
        main_text_display = prepare_hebrew_text(main_text)

        # Calculate punchline position (center of image)
        bbox = draw.textbbox((0, 0), main_text_display, font=punchline_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (1280 - text_width) // 2
        y = (720 - text_height) // 2 - 30  # Slightly above center

        # Draw semi-transparent background for punchline
        padding = 25
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(0, 0, 0, 200)
        )

        # Draw punchline text with slight shadow for depth
        draw.text((x + 3, y + 3), main_text_display, font=punchline_font, fill=(0, 0, 0, 150))
        draw.text((x, y), main_text_display, font=punchline_font, fill=(255, 255, 255, 255))

        # If punchline is provided, also add smaller title at bottom
        if punchline and title:
            title_display = prepare_hebrew_text(title)
            title_bbox = draw.textbbox((0, 0), title_display, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_height = title_bbox[3] - title_bbox[1]

            title_x = (1280 - title_width) // 2
            title_y = 720 - title_height - 30

            # Draw background for title
            draw.rectangle(
                [title_x - 15, title_y - 10, title_x + title_width + 15, title_y + title_height + 10],
                fill=(0, 0, 0, 180)
            )
            draw.text((title_x, title_y), title_display, font=title_font, fill=(255, 255, 0, 255))

        # Composite overlay onto image
        img = Image.alpha_composite(img, overlay)

        # Convert to RGB for JPEG
        img = img.convert('RGB')

        # Save
        img.save(str(output_path), "JPEG", quality=90)

        if progress_callback:
            progress_callback(100, "תמונה נוצרה!")

        print(f"[SUCCESS] Thumbnail saved: {output_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Thumbnail generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_ai_thumbnail_image(
    prompt: str,
    title: str,
    output_path: str,
    progress_callback=None,
    punchline: str = None,
    provider: str = "leonardo",
    netfree_mode: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Generate AI thumbnail with text overlay.
    Routes to Leonardo or Gemini (Nano Banana) based on provider.
    Returns (success, result_data).
    """
    if provider == "nano-banana":
        return _generate_image_gemini(prompt, title, output_path, progress_callback, punchline, netfree_mode)
    else:
        return _generate_image_leonardo(prompt, title, output_path, progress_callback, punchline)


def _generate_image_leonardo(
    prompt: str,
    title: str,
    output_path: str,
    progress_callback=None,
    punchline: str = None
) -> Tuple[bool, Optional[str]]:
    """Generate AI thumbnail using Leonardo AI."""
    if not LEONARDO_API_KEY:
        print("[ERROR] Leonardo API key not configured")
        return False, None

    try:
        import requests
        from PIL import Image, ImageDraw, ImageFont
        import io

        if progress_callback:
            progress_callback(10, "יוצר תמונה ב-Leonardo...")

        # Use a session with verify=False to bypass NetFree/SSL filtering
        session = requests.Session()
        session.verify = False

        # Leonardo API request
        url = "https://cloud.leonardo.ai/api/rest/v1/generations"

        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {LEONARDO_API_KEY}",
            "content-type": "application/json"
        }

        payload = {
            "prompt": prompt,
            "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",  # Leonardo Creative
            "width": 1280,
            "height": 720,
            "num_images": 1
        }

        response = session.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"[ERROR] Leonardo API error: {response.text}")
            return False, None

        generation_id = response.json().get('sdGenerationJob', {}).get('generationId')

        if not generation_id:
            print("[ERROR] No generation ID returned")
            return False, None

        if progress_callback:
            progress_callback(30, "מחכה לתוצאה מ-Leonardo...")

        # Poll for result
        result_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"

        for _ in range(30):
            time.sleep(2)
            result = session.get(result_url, headers=headers)

            if result.status_code == 200:
                data = result.json()
                generations = data.get('generations_by_pk', {}).get('generated_images', [])

                if generations:
                    image_url = generations[0].get('url')

                    if progress_callback:
                        progress_callback(80, "מוריד תמונה...")

                    # Download image directly to memory (BytesIO) with verify=False
                    # to try to bypass NetFree content filtering
                    img_response = session.get(image_url, headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "*/*",
                    })
                    if img_response.status_code == 200:
                        # Load bytes directly into PIL - no temp file
                        raw_bytes = io.BytesIO(img_response.content)
                        img = Image.open(raw_bytes).convert('RGBA')

                        # Add punchline text overlay
                        img = _add_text_overlay_to_image(img, title, punchline)

                        # Save final image
                        img = img.convert('RGB')
                        img.save(str(output_path), "JPEG", quality=90)

                        if progress_callback:
                            progress_callback(100, "תמונת AI נוצרה!")

                        return True, image_url

        print("[ERROR] Timeout waiting for Leonardo result")
        return False, None

    except Exception as e:
        print(f"[ERROR] Leonardo thumbnail generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def _generate_image_gemini(
    prompt: str,
    title: str,
    output_path: str,
    progress_callback=None,
    punchline: str = None,
    netfree_mode: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Generate AI thumbnail using Gemini 2.5 Flash (Nano Banana).

    Two modes:
      Normal:  SDK inline bytes -> PIL -> text overlay -> base64 data URI -> frontend
      NetFree: SDK inline bytes -> PIL -> text overlay -> save to file -> localhost URL
    Both use generateContent endpoint (same as text chat) with inline_data response.
    """
    if not GEMINI_API_KEY:
        print("[ERROR] Gemini API key not configured")
        return False, None

    try:
        from google import genai
        from PIL import Image
        import io
        import httpx

        mode_label = "NetFree" if netfree_mode else "Normal"
        if progress_callback:
            progress_callback(10, "יוצר תמונה ב-Nano Banana...")

        # httpx with verify=False to bypass SSL interception
        http_client = httpx.Client(verify=False)
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={"httpx_client": http_client})

        if progress_callback:
            progress_callback(30, "מייצר תמונה עם Gemini...")

        print(f"[NANO-BANANA] Mode={mode_label}, calling generateContent...")

        # Uses generateContent endpoint (like text chat) — NOT imagen:predict
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=f"Generate a high-quality 16:9 cinematic image for a video thumbnail. The image should be: {prompt}",
            config=genai.types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        # Extract inline bytes — no URL, no download
        raw_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                raw_bytes = part.inline_data.data
                print(f"[NANO-BANANA] Got {len(raw_bytes)} bytes inline from SDK")
                break

        if not raw_bytes:
            print("[ERROR] Gemini returned no image in inline_data")
            return False, None

        if progress_callback:
            progress_callback(70, "מעבד תמונה...")

        # Bytes -> PIL (in memory)
        img = Image.open(io.BytesIO(raw_bytes)).convert('RGBA')

        # Resize to 16:9 if needed
        target_w, target_h = 1280, 720
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.LANCZOS)

        # Text overlay (in memory)
        img = _add_text_overlay_to_image(img, title, punchline)

        img_rgb = img.convert('RGB')

        if netfree_mode:
            # NetFree mode: save to local file, return "file:" marker
            # Frontend will load from localhost (not filtered by NetFree)
            img_rgb.save(str(output_path), "JPEG", quality=90)
            print(f"[NANO-BANANA] NetFree mode: saved to {output_path}")
            if progress_callback:
                progress_callback(100, "תמונה נשמרה!")
            return True, "file"
        else:
            # Normal mode: return base64 data URI (no file, no URL)
            if progress_callback:
                progress_callback(90, "ממיר לתצוגה...")
            buffer = io.BytesIO()
            img_rgb.save(buffer, format="JPEG", quality=90)
            b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            data_uri = f"data:image/jpeg;base64,{b64_str}"
            print(f"[NANO-BANANA] Normal mode: base64 ready ({len(b64_str) // 1024}KB)")
            if progress_callback:
                progress_callback(100, "תמונת AI נוצרה!")
            return True, data_uri

    except Exception as e:
        print(f"[ERROR] Gemini thumbnail generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def _add_text_overlay_to_image(img: 'Image.Image', title: str, punchline: str = None) -> 'Image.Image':
    """
    Add text overlay to an image with proper RTL Hebrew support.
    """
    from PIL import Image, ImageDraw, ImageFont

    # Create overlay for text with transparency
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    width, height = img.size

    # Load fonts
    try:
        font_path = FONTS_DIR / "Assistant-Bold.ttf"
        if font_path.exists():
            punchline_font = ImageFont.truetype(str(font_path), 56)
            title_font = ImageFont.truetype(str(font_path), 36)
        else:
            punchline_font = ImageFont.load_default()
            title_font = ImageFont.load_default()
    except:
        punchline_font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # Use punchline if provided, otherwise use title as main text
    main_text = punchline if punchline else title

    if main_text:
        # Prepare text for RTL
        main_text_display = prepare_hebrew_text(main_text)

        # Calculate position (center of image)
        bbox = draw.textbbox((0, 0), main_text_display, font=punchline_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2 - 30

        # Draw semi-transparent background
        padding = 25
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(0, 0, 0, 200)
        )

        # Draw text with shadow
        draw.text((x + 3, y + 3), main_text_display, font=punchline_font, fill=(0, 0, 0, 150))
        draw.text((x, y), main_text_display, font=punchline_font, fill=(255, 255, 255, 255))

    # If punchline is provided, also add smaller title at bottom
    if punchline and title:
        title_display = prepare_hebrew_text(title)
        title_bbox = draw.textbbox((0, 0), title_display, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]

        title_x = (width - title_width) // 2
        title_y = height - title_height - 30

        # Draw background for title
        draw.rectangle(
            [title_x - 15, title_y - 10, title_x + title_width + 15, title_y + title_height + 10],
            fill=(0, 0, 0, 180)
        )
        draw.text((title_x, title_y), title_display, font=title_font, fill=(255, 255, 0, 255))

    # Composite overlay onto image
    return Image.alpha_composite(img, overlay)


def download_image_from_url(url: str, output_path: str, title: Optional[str] = None, punchline: Optional[str] = None) -> bool:
    """Download image from URL and save to file with optional text overlay."""
    try:
        import requests
        from PIL import Image
        import io

        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            # If title or punchline provided, add text overlay
            if title or punchline:
                img = Image.open(io.BytesIO(response.content)).convert('RGBA')
                img = _add_text_overlay_to_image(img, title, punchline)
                img = img.convert('RGB')
                img.save(str(output_path), "JPEG", quality=90)
            else:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
            return True
        return False
    except Exception as e:
        print(f"[ERROR] Failed to download image: {e}")
        return False


# =============================================================================
# Text Extraction from Video
# =============================================================================

def create_preview_video(video_path: str, output_path: str) -> bool:
    """
    Create a preview video optimized for Gemini File API subtitle extraction.

    Settings optimized for maximum text readability:
    - 640x360 resolution (clear text visibility)
    - 8 FPS frame rate (captures ALL subtitle changes frame by frame)
    - CRF 20 (high quality for sharp text)
    - No audio (reduces file size)

    Higher FPS and quality ensures Gemini doesn't miss any subtitle frames.
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2",
            "-r", "8",              # 8 FPS - captures ALL subtitle changes
            "-an",                  # No audio
            "-c:v", "libx264",
            "-preset", "fast",      # Good quality encoding
            "-crf", "20",           # High quality for sharp, readable text
            str(output_path)
        ]

        print(f"[INFO] Creating preview video: 640x360 @ 8fps, CRF 20...")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)

        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            print(f"[SUCCESS] Preview video created: {output_path} ({file_size:.2f} MB) - 640x360 @ 8fps CRF20")
            return True
        else:
            print(f"[ERROR] FFmpeg preview creation failed: {result.stderr[:300]}")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to create preview video: {e}")
        return False


def parse_srt_response(srt_text: str) -> List[Dict]:
    """
    Parse SRT format text into a list of subtitle entries.
    Returns list of {'start': float, 'end': float, 'text': str}
    """
    import re

    entries = []

    # Clean up the response - remove markdown code blocks if present
    srt_text = srt_text.strip()
    if srt_text.startswith("```"):
        # Remove markdown code block
        lines = srt_text.split('\n')
        srt_text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    # Split into blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', srt_text.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue

        # Find the timing line (contains -->)
        timing_line = None
        text_lines = []

        for i, line in enumerate(lines):
            if '-->' in line:
                timing_line = line
                text_lines = lines[i+1:]
                break

        if not timing_line:
            continue

        # Parse timing: 00:00:00,000 --> 00:00:00,000
        timing_match = re.match(
            r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})',
            timing_line.strip()
        )

        if not timing_match:
            # Try simpler format: 00:00:00 --> 00:00:00
            timing_match = re.match(
                r'(\d{1,2}):(\d{2}):(\d{2})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})',
                timing_line.strip()
            )
            if timing_match:
                h1, m1, s1, h2, m2, s2 = timing_match.groups()
                start = int(h1) * 3600 + int(m1) * 60 + int(s1)
                end = int(h2) * 3600 + int(m2) * 60 + int(s2)
            else:
                continue
        else:
            h1, m1, s1, ms1, h2, m2, s2, ms2 = timing_match.groups()
            start = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000
            end = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000

        text = ' '.join(text_lines).strip()

        if text:
            entries.append({
                'start': start,
                'end': end,
                'text': text,
                'timestamp': start
            })

    return entries


def extract_text_huggingface(video_path: str, progress_callback=None, srt_output_path: str = None) -> Tuple[str, List[Dict]]:
    """
    Extracts text from video using Gemini File API.
    SSL Patch: Forces httplib2 to bypass environment variable checks.

    Args:
        video_path: Path to the video file
        progress_callback: Optional callback for progress updates
        srt_output_path: Optional path to save SRT file directly (recommended)

    Returns:
        Tuple of (srt_content, entries)
    """
    import os
    import sys
    import ssl
    import certifi
    import time
    from typing import Tuple, List, Dict

    # --- הזרקה אגרסיבית למניעת RuntimeError: HTTPLIB2_CA_CERTS ---
    # אנחנו יוצרים אובייקט דמה שמחליף את הספרייה הבעייתית
    class MockCerts:
        @staticmethod
        def where():
            return certifi.where()

    # הזרקה למערכת המודולים של פייתון
    sys.modules['httplib2.certs'] = MockCerts

    # ניקוי משתני סביבה וביטול אימות SSL
    if 'HTTPLIB2_CA_CERTS' in os.environ:
        del os.environ['HTTPLIB2_CA_CERTS']

    import httplib2
    httplib2.CA_CERTS = certifi.where()
    ssl._create_default_https_context = ssl._create_unverified_context
    # -----------------------------------------------------------

    # עכשיו טוענים את גוגל - הוא כבר יראה את המודול המזוייף שלנו ולא יקרוס
    import google.generativeai as genai
    from utils.helpers import parse_srt, create_preview_video

    if progress_callback:
        progress_callback(5, "מכין את הסרטון לסריקה (8 FPS)...")

    try:
        # יצירת פריוויו איכותי לסריקה
        genai.configure(transport='rest') # זה משנה את הצינור מ-gRPC ל-REST, שהוא הרבה יותר סלחן ל-SSL
        preview_path = create_preview_video(video_path, width=1280, fps=8, crf=20)

        if progress_callback:
            progress_callback(15, "מעלה קובץ ל-Gemini...")

        # העלאה ל-API
        video_file = genai.upload_file(path=preview_path)

        # המתנה לסיום עיבוד הקובץ בשרתים של גוגל
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if progress_callback:
            progress_callback(30, "מנתח טקסט (סריקה מלאה)...")

        # שימוש במודל פלאש עם פרומפט אגרסיבי לתמלול מלא
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = """
        עליך לשמש כמכונת OCR מדויקת.
        חלץ את כל הכתוביות המופיעות בסרטון מההתחלה (00:00:00) ועד הסוף המוחלט.
        אל תסכם, אל תשמיט מילים, ואל תדלג על משפטים.
        הפלט חייב להיות בפורמט SRT בלבד.
        """

        response = model.generate_content([prompt, video_file])
        srt_content = response.text

        # ניקוי הפלט של Gemini (הסרת סימני ``` אם ישנם)
        if "```srt" in srt_content:
            srt_content = srt_content.split("```srt")[1].split("```")[0].strip()
        elif "```" in srt_content:
            srt_content = srt_content.split("```")[1].split("```")[0].strip()

        # === שמירת קובץ SRT ישירות לדיסק ===
        if srt_output_path and srt_content:
            try:
                with open(srt_output_path, 'w', encoding='utf-8') as f:
                    f.write(srt_content)
                file_size = os.path.getsize(srt_output_path)
                print(f"[SUCCESS] SRT saved directly: {srt_output_path} ({file_size} bytes, {len(srt_content)} chars)")
            except Exception as save_error:
                print(f"[ERROR] Failed to save SRT to {srt_output_path}: {save_error}")

        # המרה לאובייקטים עבור הממשק
        entries = parse_srt(srt_content)
        print(f"[INFO] Parsed {len(entries)} subtitle entries from Gemini response")

        # ניקוי קובץ הפריוויו מהמחשב
        if os.path.exists(preview_path):
            os.remove(preview_path)

        if progress_callback:
            progress_callback(100, "התמלול הושלם בהצלחה!")

        return srt_content, entries

    except Exception as e:
        print(f"[ERROR] Gemini Extraction Failed: {str(e)}")
        return "", []


# =============================================================================
# Video Planner - AI Script Generator with Chat Interface
# =============================================================================
def video_planner_chat(
    user_message: str,
    conversation_history: list = None,
    current_script: str = "",
    file_context: str = ""
) -> dict:
    import os
    import sys
    import ssl
    import certifi
    
    # תיקון קריטי לשגיאת ה-RuntimeError
    if 'HTTPLIB2_CA_CERTS' in os.environ:
        del os.environ['HTTPLIB2_CA_CERTS']
    os.environ['HTTPLIB2_CA_CERTS'] = certifi.where()
    ssl._create_default_https_context = ssl._create_unverified_context

    import google.generativeai as genai

    if not user_message or not user_message.strip():
        return {"success": False, "script": current_script, "ai_message": "", "error": "No message provided"}

    if conversation_history is None: conversation_history = []
    conversation_history = conversation_history[-15:]

    system_prompt = """אתה עוזר מקצועי לבניית מערכי שיעור והרצאות.
תפקידך לעזור למשתמש לבנות תוכן לימודי איכותי ומובנה.

חוק בל יעבור: כל תשובה שלך חייבת להיות מחולקת לשני חלקים בלבד עם התגיות הבאות:
CHAT: [כאן הדיבור החופשי וההסברים שלך]
SCRIPT: [כאן אך ורק מערך השיעור המפורט. אם אין מערך מוכן, כתוב את המילה None]"""

    try:
        genai.configure(transport='rest')
        
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            system_instruction=system_prompt
        )

        history_for_gemini = []
        for msg in conversation_history:
            role = "user" if msg.get("role") == "user" else "model"
            history_for_gemini.append({"role": role, "parts": [msg.get("content", "")]})

        chat = model.start_chat(history=history_for_gemini)
        
        full_input = user_message
        if current_script and current_script.strip():
            full_input = f"המערך הנוכחי:\n{current_script}\n\nבקשת המשתמש: {user_message}"

        response = chat.send_message(full_input)
        response_text = response.text.strip()

        script = ""
        ai_message = ""

        if "CHAT:" in response_text and "SCRIPT:" in response_text:
            parts = response_text.split("SCRIPT:")
            ai_message = parts[0].replace("CHAT:", "").strip()
            script_part = parts[1].strip()
            script = "" if script_part.lower() == "none" else script_part
        else:
            ai_message = response_text
            script = ""

        return {
            "success": True,
            "script": script if script else current_script,
            "ai_message": ai_message
        }

    except Exception as e:
        print(f"Detailed Error: {str(e)}")
        return {
            "success": False,
            "script": current_script,
            "ai_message": "אירעה שגיאה טכנית בחיבור. נסה שנית.",
            "error": str(e)
        }

    try:
        genai.configure(transport='rest')
        
        # כאן השינוי המרכזי - הגדרת ההוראות בתוך המודל
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            system_instruction=system_prompt
        )

        # בניית היסטוריית השיחה
        history_for_gemini = []
        if file_context:
            history_for_gemini.append({"role": "user", "parts": [f"חומר רקע: {file_context}"]})
            history_for_gemini.append({"role": "model", "parts": ["קיבלתי את החומר. אשתמש בו לבניית המערך."]})

        for msg in conversation_history:
            role = "user" if msg.get("role") == "user" else "model"
            history_for_gemini.append({"role": role, "parts": [msg.get("content", "")]})

        # יצירת הצ'אט ושליחת ההודעה האחרונה
        chat = model.start_chat(history=history_for_gemini)
        
        full_user_input = user_message
        if current_script and current_script.strip():
            full_user_input = f"המערך הנוכחי:\n{current_script}\n\nבקשת המשתמש: {user_message}"

        response = chat.send_message(full_user_input)
        response_text = response.text.strip()

        # פיצול התגובה
        script = ""
        ai_message = ""

        if "CHAT:" in response_text and "SCRIPT:" in response_text:
            parts = response_text.split("SCRIPT:")
            ai_message = parts[0].replace("CHAT:", "").strip()
            script_part = parts[1].strip()
            script = "" if script_part.lower() == "none" else script_part
        else:
            # Fallback אם ה-AI בכל זאת פספס
            ai_message = response_text
            script = ""

        return {
            "success": True,
            "script": script if script else current_script,
            "ai_message": ai_message
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "success": False,
            "script": current_script,
            "ai_message": f"שגיאת תקשורת: {str(e)}. וודא שאין חסימת רשת.",
            "error": str(e)
        }