"""
Audio Service - Handles voiceover generation, audio processing, and music management.
Supports Edge-TTS (free) and ElevenLabs (premium) for voice synthesis.
"""
import os
import subprocess
import asyncio
import random
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from utils.config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_ID,
    ELEVENLABS_MODEL,
    ELEVENLABS_EMOTION_SETTINGS,
    EDGE_TTS_VOICE,
    EDGE_TTS_RATE,
    MUSIC_STYLE_KEYWORDS,
    GROQ_API_KEY
)
from utils.helpers import clean_text_for_voiceover
from services.text_service import parse_srt_file, clean_and_merge_srt, write_srt_from_entries, clean_srt_text_with_ai


# =============================================================================
# ElevenLabs Voiceover (Premium)
# =============================================================================

def generate_voiceover_elevenlabs(
    text: str,
    output_path: str,
    emotion: str = 'neutral',
    voice_id: str = None,
    progress_callback=None
) -> bool:
    """
    Generate voiceover using ElevenLabs API.

    Args:
        text: Text to convert to speech
        output_path: Path to save the audio file
        emotion: Emotion preset ('emotional', 'pastoral', 'happy', 'neutral')
        voice_id: Optional custom voice ID (defaults to config)
        progress_callback: Optional progress callback

    Returns:
        bool: True if successful, False otherwise
    """
    if not ELEVENLABS_API_KEY:
        print("[ERROR] ElevenLabs API key not configured")
        return False

    if not text or not text.strip():
        print("[ERROR] No text provided for voiceover")
        return False

    try:
        import requests

        if progress_callback:
            progress_callback(10, "מתחיל יצירת קריינות עם ElevenLabs...")

        # Get voice settings based on emotion
        emotion_lower = emotion.lower()
        settings = ELEVENLABS_EMOTION_SETTINGS.get(emotion_lower, ELEVENLABS_EMOTION_SETTINGS['neutral'])

        # Use provided voice_id or default
        vid = voice_id or ELEVENLABS_VOICE_ID

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }

        # payload = {
        #     "text": text,
        #     "model_id": ELEVENLABS_MODEL,
        #     "voice_settings": {
        #         "stability": settings['stability'],
        #         "similarity_boost": settings['similarity_boost'],
        #         "style": settings['style'],
        #         "use_speaker_boost": settings['use_speaker_boost']
        #     }
        # }
        print(f"--- DEBUG ELEVENLABS ---")
        print(f"Original text: {text}")
        print(f"Voice ID: {vid}")
        print(f"------------------------")

        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",  # זה מה שהופך את זה מג'יבריש לעברית
            "voice_settings": {
                "stability": 0.4,           # יציבות הקול
                "similarity_boost": 0.8,    # דמיון לקול המקור
                "style": 0.5,               # הגזמת סגנון (רגש)
                "use_speaker_boost": True
            }
        }

        if progress_callback:
            progress_callback(30, "שולח בקשה ל-ElevenLabs...")

        response = requests.post(url, json=payload, headers=headers, timeout=120)

        if response.status_code == 200:
            if progress_callback:
                progress_callback(80, "שומר קובץ אודיו...")

            with open(output_path, 'wb') as f:
                f.write(response.content)

            if progress_callback:
                progress_callback(100, "קריינות נוצרה בהצלחה!")

            print(f"[SUCCESS] ElevenLabs voiceover saved to: {output_path}")
            return True
        else:
            error_msg = response.json().get('detail', {}).get('message', response.text)
            print(f"[ERROR] ElevenLabs API error: {response.status_code} - {error_msg}")
            return False

    except ImportError:
        print("[ERROR] requests library not installed")
        return False
    except Exception as e:
        print(f"[ERROR] ElevenLabs voiceover failed: {e}")
        return False


def generate_voiceover_elevenlabs_sync(
    text: str,
    output_path: str,
    emotion: str = 'neutral',
    voice_id: str = None,
    progress_callback=None
) -> bool:
    """Synchronous wrapper for ElevenLabs voiceover."""
    return generate_voiceover_elevenlabs(text, output_path, emotion, voice_id, progress_callback)


# =============================================================================
# Edge-TTS Voiceover (Free)
# =============================================================================

async def generate_voiceover_segment(
    text: str,
    output_path: str,
    voice: str = None,
    rate: str = None
) -> bool:
    """
    Generate a single voiceover segment using Edge-TTS.
    """
    try:
        import edge_tts

        voice = voice or EDGE_TTS_VOICE
        rate = rate or EDGE_TTS_RATE

        cleaned_text = clean_text_for_voiceover(text)
        communicate = edge_tts.Communicate(cleaned_text, voice, rate=rate)
        await communicate.save(str(output_path))
        return os.path.exists(output_path)

    except Exception as e:
        print(f"[ERROR] Segment generation failed: {e}")
        return False


async def generate_voiceover(text: str, output_path: str, progress_callback=None) -> bool:
    """
    Generate voiceover using Edge-TTS (free).
    """
    try:
        import edge_tts

        if progress_callback:
            progress_callback(10, "מייצר קריינות...")

        cleaned_text = clean_text_for_voiceover(text)
        communicate = edge_tts.Communicate(cleaned_text, EDGE_TTS_VOICE, rate=EDGE_TTS_RATE)
        await communicate.save(str(output_path))

        if progress_callback:
            progress_callback(100, "קריינות נוצרה!")

        return os.path.exists(output_path)

    except Exception as e:
        print(f"[ERROR] Voiceover generation failed: {e}")
        return False


async def generate_voiceover_from_srt(
    srt_path: str,
    output_path: str,
    video_duration: float,
    progress_callback=None
) -> bool:
    """
    Generate synchronized voiceover from SRT file.
    Creates audio segments for each subtitle entry and combines them.
    """
    if not os.path.exists(srt_path):
        print(f"[ERROR] SRT file not found: {srt_path}")
        return False

    if progress_callback:
        progress_callback(0, "מייצר קריינות מסונכרנת...")

    try:
        from pydub import AudioSegment
    except ImportError:
        print("[WARNING] pydub not available, falling back to simple voiceover")
        entries = parse_srt_file(srt_path)
        entries = clean_and_merge_srt(entries)
        full_text = ' '.join([clean_text_for_voiceover(e['text']) for e in entries])
        return await generate_voiceover(full_text, output_path, progress_callback)

    # Parse and clean SRT entries
    raw_entries = parse_srt_file(srt_path)
    if not raw_entries:
        return False

    if progress_callback:
        progress_callback(5, "מנקה כפילויות וחפיפות...")

    entries = clean_and_merge_srt(raw_entries)
    if not entries:
        return False

    # AI text cleaning
    if progress_callback:
        progress_callback(8, "מנקה טקסט עם AI...")
    entries = clean_srt_text_with_ai(entries, progress_callback)

    # Save cleaned SRT
    cleaned_srt_path = Path(srt_path).parent / f"{Path(srt_path).stem}_cleaned.srt"
    write_srt_from_entries(entries, str(cleaned_srt_path))

    temp_dir = Path(output_path).parent / "temp_voiceover"
    temp_dir.mkdir(exist_ok=True)

    try:
        total_duration_ms = int(video_duration * 1000)
        combined = AudioSegment.silent(duration=total_duration_ms)
        total_entries = len(entries)

        for i, entry in enumerate(entries):
            if progress_callback:
                pct = int(10 + (i / total_entries) * 70)
                progress_callback(pct, f"מייצר קריינות... ({i+1}/{total_entries})")

            temp_file = temp_dir / f"segment_{i:04d}.mp3"
            success = await generate_voiceover_segment(entry['text'], temp_file)

            if success and temp_file.exists():
                try:
                    segment = AudioSegment.from_mp3(str(temp_file))
                    start_ms = int(entry['start'] * 1000)
                    available_duration_ms = int((entry['end'] - entry['start']) * 1000)

                    # Speed up if needed
                    if len(segment) > available_duration_ms > 0:
                        speed_factor = len(segment) / available_duration_ms
                        if speed_factor < 1.5:
                            sped_up_file = temp_dir / f"segment_{i:04d}_fast.mp3"
                            speed_cmd = [
                                "ffmpeg", "-y", "-i", str(temp_file),
                                "-filter:a", f"atempo={min(speed_factor, 1.5)}",
                                str(sped_up_file)
                            ]
                            subprocess.run(speed_cmd, capture_output=True)
                            if sped_up_file.exists():
                                segment = AudioSegment.from_mp3(str(sped_up_file))

                    if start_ms < total_duration_ms:
                        combined = combined.overlay(segment, position=start_ms)

                except Exception as e:
                    print(f"[WARNING] Failed to process segment {i}: {e}")

        if progress_callback:
            progress_callback(90, "שומר קובץ קריינות...")

        combined.export(str(output_path), format="mp3")

        # Cleanup temp files
        for f in temp_dir.glob("*.mp3"):
            try:
                f.unlink()
            except:
                pass

        if progress_callback:
            progress_callback(100, "קריינות נוצרה!")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to generate voiceover from SRT: {e}")
        return False


def generate_voiceover_sync(text: str, output_path: str, progress_callback=None) -> bool:
    """Synchronous wrapper for generate_voiceover."""
    return asyncio.run(generate_voiceover(text, output_path, progress_callback))


def generate_voiceover_from_srt_sync(
    srt_path: str,
    output_path: str,
    video_duration: float,
    progress_callback=None
) -> bool:
    """Synchronous wrapper for generate_voiceover_from_srt."""
    return asyncio.run(generate_voiceover_from_srt(srt_path, output_path, video_duration, progress_callback))


# =============================================================================
# Audio Utilities
# =============================================================================

def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print(f"[WARNING] Could not get audio duration: {e}")
    return 0


def extract_and_compress_audio(video_path: str, output_audio_path: str, progress_callback=None) -> bool:
    """
    Extract audio from video and compress it.
    """
    try:
        if progress_callback:
            progress_callback(5, "מחלץ אודיו מהסרטון...")

        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "libmp3lame", "-q:a", "4",
            "-ar", "16000", "-ac", "1",
            str(output_audio_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode == 0 and os.path.exists(output_audio_path):
            print(f"[SUCCESS] Audio extracted to: {output_audio_path}")
            return True
        else:
            print(f"[ERROR] FFmpeg audio extraction failed: {result.stderr[:200]}")
            return False

    except Exception as e:
        print(f"[ERROR] Audio extraction failed: {e}")
        return False


# =============================================================================
# Music Library Management
# =============================================================================

def get_random_music(style: str, music_dir: str) -> Optional[Path]:
    """
    Get a random music file matching the given style.
    """
    music_path = Path(music_dir)
    if not music_path.exists():
        print(f"[WARNING] Music directory not found: {music_dir}")
        return None

    keywords = MUSIC_STYLE_KEYWORDS.get(style.lower(), [style.lower()])

    all_music = list(music_path.glob("*.mp3"))
    matching_files = []

    for music_file in all_music:
        if 'temp' in str(music_file).lower():
            continue
        filename_lower = music_file.name.lower()
        for keyword in keywords:
            if keyword in filename_lower:
                matching_files.append(music_file)
                break

    if matching_files:
        selected = random.choice(matching_files)
        print(f"[INFO] Selected music for style '{style}': {selected.name}")
        return selected
    elif all_music:
        selected = random.choice([f for f in all_music if 'temp' not in str(f).lower()])
        print(f"[INFO] No music matches for style '{style}', using random: {selected.name}")
        return selected
    else:
        print(f"[WARNING] No music files found in {music_dir}")
        return None


def list_music_library(music_dir: str) -> List[Dict]:
    """
    List all music files in the library directory.
    """
    music_path = Path(music_dir)
    if not music_path.exists():
        return []

    music_files = []
    for ext in ['*.mp3', '*.wav', '*.m4a', '*.ogg']:
        for f in music_path.glob(ext):
            if 'temp' in str(f).lower():
                continue
            music_files.append({
                'name': f.stem,
                'filename': f.name,
                'path': str(f)
            })

    music_files.sort(key=lambda x: x['name'].lower())
    print(f"[INFO] Found {len(music_files)} music files in library")
    return music_files


def download_audio_from_url(url: str, output_dir: str, progress_callback=None) -> Optional[Path]:
    """
    Download audio from YouTube, Pixabay, or other supported URLs using yt-dlp.
    """
    try:
        import yt_dlp
    except ImportError:
        print("[ERROR] yt-dlp not installed. Install with: pip install yt-dlp")
        return None

    if not url or not url.strip():
        print("[ERROR] No URL provided for download")
        return None

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())[:8]
    output_template = str(output_path / f"downloaded_{file_id}.%(ext)s")

    if progress_callback:
        progress_callback(0, "מוריד מוזיקה מהקישור...")

    print(f"[INFO] Downloading audio from: {url}")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

            if progress_callback:
                progress_callback(50, "ממיר ל-MP3...")

            expected_file = output_path / f"downloaded_{file_id}.mp3"

            if expected_file.exists():
                print(f"[SUCCESS] Audio downloaded: {expected_file}")
                return expected_file

            for f in output_path.glob(f"downloaded_{file_id}.*"):
                if f.suffix.lower() in ['.mp3', '.m4a', '.wav', '.opus', '.webm']:
                    if f.suffix.lower() != '.mp3':
                        mp3_path = output_path / f"downloaded_{file_id}.mp3"
                        convert_cmd = [
                            'ffmpeg', '-y', '-i', str(f),
                            '-acodec', 'libmp3lame', '-q:a', '2',
                            str(mp3_path)
                        ]
                        subprocess.run(convert_cmd, capture_output=True)
                        if mp3_path.exists():
                            f.unlink()
                            return mp3_path
                    return f

        return None

    except Exception as e:
        print(f"[ERROR] Failed to download audio: {e}")
        return None


# =============================================================================
# Audio Transcription
# =============================================================================

def transcribe_with_groq(video_path: str, srt_path: str, progress_callback=None) -> Tuple[bool, str]:
    """
    Transcribe video using Groq API with whisper-large-v3 model.
    Returns (success, transcript_text).
    """
    if not GROQ_API_KEY:
        print("[ERROR] Groq API key not configured")
        return False, ""

    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)

        audio_path = Path(video_path).parent / f"{Path(video_path).stem}_temp_audio.mp3"

        if not extract_and_compress_audio(video_path, str(audio_path), progress_callback):
            return False, ""

        if progress_callback:
            progress_callback(10, "שולח לתמלול Groq...")

        print(f"[INFO] Sending audio to Groq API...")

        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(audio_path.name, audio_file.read()),
                model="whisper-large-v3",
                language="he",
                response_format="verbose_json",
                temperature=0.0
            )

        if progress_callback:
            progress_callback(18, "מעבד תוצאות תמלול...")

        transcript_text = transcription.text if hasattr(transcription, 'text') else ""
        segments = transcription.segments if hasattr(transcription, 'segments') else []

        # Write SRT with max 5 words per subtitle
        MAX_WORDS_PER_SUBTITLE = 5

        with open(srt_path, "w", encoding="utf-8", newline='\n') as f:
            if not segments:
                from services.video_service import get_video_duration
                duration = get_video_duration(video_path)
                # Split even the single segment if needed
                chunks = split_text_to_chunks(transcript_text.strip(), MAX_WORDS_PER_SUBTITLE)
                chunk_duration = duration / len(chunks) if chunks else duration
                for i, chunk in enumerate(chunks, 1):
                    start_time = (i - 1) * chunk_duration
                    end_time = i * chunk_duration
                    f.write(f"{i}\n{format_srt_time_internal(start_time)} --> {format_srt_time_internal(end_time)}\n{chunk}\n\n")
            else:
                # Split each segment into max 5 words chunks
                subtitle_index = 1
                for seg in segments:
                    split_subs = split_segment_to_subtitles(seg, MAX_WORDS_PER_SUBTITLE)
                    for sub in split_subs:
                        f.write(f"{subtitle_index}\n{format_srt_time_internal(sub['start'])} --> {format_srt_time_internal(sub['end'])}\n{sub['text'].strip()}\n\n")
                        subtitle_index += 1

        print(f"[INFO] SRT created with max {MAX_WORDS_PER_SUBTITLE} words per subtitle")

        # Cleanup temp audio
        try:
            audio_path.unlink()
        except:
            pass

        print(f"[SUCCESS] Transcription complete: {len(transcript_text)} chars")
        return True, transcript_text

    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        import traceback
        traceback.print_exc()
        return False, ""


def format_srt_time_internal(seconds):
    """Internal SRT time formatter."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def split_text_to_chunks(text: str, max_words: int = 5) -> List[str]:
    """
    Split text into chunks of maximum `max_words` words each.
    Tries to split at natural breakpoints (punctuation) when possible.
    """
    if not text or not text.strip():
        return []

    words = text.strip().split()
    if len(words) <= max_words:
        return [text.strip()]

    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)

        # Check if we've reached max words or hit a natural break
        if len(current_chunk) >= max_words:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
        elif len(current_chunk) >= 3 and any(word.endswith(p) for p in ['.', '!', '?', ',', ':', ';']):
            # Natural break at punctuation (if we have at least 3 words)
            chunks.append(' '.join(current_chunk))
            current_chunk = []

    # Don't forget remaining words
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


def split_segment_to_subtitles(segment: dict, max_words: int = 5) -> List[dict]:
    """
    Split a single segment into multiple subtitle entries, each with max_words words.
    Distributes timing proportionally across the chunks.
    """
    start = segment.get('start', getattr(segment, 'start', 0))
    end = segment.get('end', getattr(segment, 'end', start + 2))
    text = segment.get('text', getattr(segment, 'text', ''))

    chunks = split_text_to_chunks(text, max_words)

    if not chunks:
        return []

    if len(chunks) == 1:
        return [{'start': start, 'end': end, 'text': chunks[0]}]

    # Calculate duration per chunk (proportional to word count)
    total_duration = end - start
    total_words = sum(len(chunk.split()) for chunk in chunks)

    subtitles = []
    current_start = start

    for chunk in chunks:
        chunk_words = len(chunk.split())
        # Proportional duration based on word count
        chunk_duration = (chunk_words / total_words) * total_duration
        chunk_end = min(current_start + chunk_duration, end)

        subtitles.append({
            'start': current_start,
            'end': chunk_end,
            'text': chunk
        })

        current_start = chunk_end

    return subtitles
