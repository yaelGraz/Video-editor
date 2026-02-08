# =============================================================================
# SSL CERTIFICATE BYPASS - MUST BE AT THE VERY TOP BEFORE ANY OTHER IMPORTS
# =============================================================================
import os
import sys

# 1. Set environment variables FIRST (before any imports that might use them)
# gRPC SSL bypass (for Google Gemini API)
os.environ["GRPC_SSL_CIPHER_SUITES"] = "HIGH+ECDSA"
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = ""
os.environ["GRPC_VERIFY_METADATA_CA_CERTS"] = "0"

# General SSL bypass
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''

import ssl

# 2. Override default SSL context creation
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# 3. Patch ssl module to disable verification by default
ssl._create_default_https_context = ssl._create_unverified_context

# =============================================================================
# Now import other modules
# =============================================================================
import subprocess
import time
import re
import json
import asyncio
import random
import uuid

# 4. Disable urllib3 SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 5. Import requests and patch it to disable SSL verification by default
import requests
from requests.adapters import HTTPAdapter

# Monkey-patch requests to disable SSL verification by default
_original_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    if 'verify' not in kwargs:
        kwargs['verify'] = False
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _patched_request

# Also patch the module-level functions
_original_get = requests.get
_original_post = requests.post
def _patched_get(url, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_get(url, **kwargs)
def _patched_post(url, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_post(url, **kwargs)
requests.get = _patched_get
requests.post = _patched_post

# =============================================================================
# Continue with remaining imports
# =============================================================================
import cv2
import pytesseract

from deep_translator import GoogleTranslator
from pathlib import Path
from dotenv import load_dotenv
import edge_tts

# =============================================================================
# SSL PATCH: Fix HTTPLIB2_CA_CERTS error on Windows
# Must be applied BEFORE importing google.generativeai
# =============================================================================
import ssl
import certifi

# Create mock certs module to bypass httplib2 environment variable check
class MockCerts:
    @staticmethod
    def where():
        return certifi.where()

sys.modules['httplib2.certs'] = MockCerts

# Remove problematic environment variable if exists
if 'HTTPLIB2_CA_CERTS' in os.environ:
    del os.environ['HTTPLIB2_CA_CERTS']

# Set certifi certificates and disable strict SSL verification
try:
    import httplib2
    httplib2.CA_CERTS = certifi.where()
except ImportError:
    pass

ssl._create_default_https_context = ssl._create_unverified_context
# =============================================================================

import google.generativeai as genai

# 2. טעינת משתני סביבה
load_dotenv()

# קיבוע קידוד UTF-8 לווינדוס (למניעת שגיאות בעברית)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ["PYTHONIOENCODING"] = "utf-8"

# 3. הגדרות API וכלים חיצוניים
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# הגדרת Gemini (משתמש במפתח מה-.env)
# Using transport='rest' to bypass gRPC SSL certificate issues
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY, transport='rest')
else:
    # אם אין ב-env, אפשר לשים כאן זמנית לבדיקה:
    # genai.configure(api_key="AIzaSy...", transport='rest')
    print("[WARNING] GEMINI_API_KEY not found in environment variables!")

# --- כאן מתחילות הפונקציות של הקוד שלך ---



# Load environment variables from .env file
load_dotenv()

# Fix Windows console encoding for Hebrew/Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ["PYTHONIOENCODING"] = "utf-8"

# Set Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_huggingface(video_path):
    """
    Extract subtitles/text from video frames using Google Gemini 2.5 Flash.
    Optimized for quality over quantity - reduces subtitle count for better voiceover.

    Features:
    - Bottom 30% crop (subtitle area only) - focuses AI on text
    - 3-second sampling to reduce duplicates
    - Smart merging with 80% similarity detection (SequenceMatcher)
    - Minimum 2-second subtitle duration for natural narration
    - Duplicate word removal from final script
    """
    import base64
    from PIL import Image
    import io
    from difflib import SequenceMatcher

    print(f"[INFO] מתחיל חילוץ כתוביות עם Google Gemini 2.5 Flash...")

    video_path = Path(video_path)

    # Initialize Gemini model
    model = genai.GenerativeModel('models/gemini-2.5-flash')

    # Configuration - Optimized for quality (fewer, better subtitles)
    CROP_BOTTOM_PERCENT = 0.30  # Analyze bottom 30% of frame (subtitle area)
    SAMPLE_INTERVAL_SEC = 3.0   # Sample every 3 seconds (reduced from 1s to avoid duplicates)
    API_DELAY_SEC = 0.5         # 0.5 second delay (paid API can handle it)
    RETRY_DELAY_SEC = 2.0       # Quick retry on errors
    MAX_RETRIES = 5             # More retries since we're paying
    SIMILARITY_THRESHOLD = 0.80 # 80% similarity = consider as duplicate
    MIN_SUBTITLE_DURATION = 2.0 # Minimum 2 seconds per subtitle for natural narration

    def parse_time_to_seconds(time_str):
        """Convert time string (HH:MM:SS or MM:SS) to seconds."""
        if isinstance(time_str, (int, float)):
            return float(time_str)
        try:
            parts = str(time_str).split(':')
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            else:
                return float(time_str)
        except:
            return 0.0

    def clean_json_response(response_text):
        """Clean markdown tags and extract pure JSON from response."""
        text = response_text.strip()
        # Remove markdown code blocks
        if '```json' in text:
            text = text.split('```json')[1]
            if '```' in text:
                text = text.split('```')[0]
        elif '```' in text:
            parts = text.split('```')
            if len(parts) >= 2:
                text = parts[1]
        return text.strip()

    def text_similarity(text1, text2):
        """Calculate similarity ratio between two texts using SequenceMatcher."""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1.lower().strip(), text2.lower().strip()).ratio()

    def merge_consecutive_subtitles(entries):
        """
        Merge consecutive similar subtitles into single longer segments.
        Uses 80% similarity threshold to catch near-duplicates.

        Example: If frames have "שלום עולם" and "שלום עולם!" (80%+ similar),
        merge into one entry with the longer/better text.
        """
        if not entries:
            return []

        # Sort by start time first
        sorted_entries = sorted(entries, key=lambda x: x['start'])

        merged = []
        current = None

        for entry in sorted_entries:
            text_clean = entry['text'].strip()

            if not text_clean or len(text_clean) < 2:
                continue  # Skip empty or very short entries

            if current is None:
                # First entry
                current = {
                    'start': entry['start'],
                    'end': entry['end'],
                    'text': text_clean
                }
            else:
                # Check similarity (80% threshold)
                similarity = text_similarity(text_clean, current['text'])

                if similarity >= SIMILARITY_THRESHOLD:
                    # Similar text - extend the end time, keep the longer text
                    current['end'] = max(current['end'], entry['end'])
                    if len(text_clean) > len(current['text']):
                        current['text'] = text_clean
                else:
                    # Different text - save current and start new
                    merged.append({
                        'start': current['start'],
                        'end': current['end'],
                        'text': current['text']
                    })
                    current = {
                        'start': entry['start'],
                        'end': entry['end'],
                        'text': text_clean
                    }

        # Don't forget the last one
        if current:
            merged.append({
                'start': current['start'],
                'end': current['end'],
                'text': current['text']
            })

        print(f"[INFO] מיזוג כתוביות (סף דמיון {SIMILARITY_THRESHOLD*100:.0f}%): {len(entries)} -> {len(merged)} (הוסרו {len(entries) - len(merged)} כפילויות)")
        return merged

    def clean_duplicate_words(text):
        """
        Remove consecutive duplicate words/phrases from text.
        Example: "שלום שלום עולם עולם" -> "שלום עולם"
        """
        if not text:
            return text

        words = text.split()
        if len(words) <= 1:
            return text

        cleaned = [words[0]]
        for word in words[1:]:
            # Don't add if it's the same as the previous word
            if word.lower().strip() != cleaned[-1].lower().strip():
                cleaned.append(word)

        return ' '.join(cleaned)

    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"[ERROR] Cannot open video: {video_path}")
            return "שגיאה בפתיחת הסרטון", []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps if fps > 0 else 0

        sample_interval = max(int(fps * SAMPLE_INTERVAL_SEC), 1)

        print(f"[INFO] וידאו: {video_duration:.1f}s, {fps:.1f} FPS, דגימה כל {SAMPLE_INTERVAL_SEC} שניות")
        print(f"[INFO] מצב API בתשלום - עיכוב מינימלי ({API_DELAY_SEC}s)")

        # Storage for processing
        all_subtitle_entries = []  # All parsed subtitle entries from JSON

        frame_count = 0
        frames_analyzed = 0
        api_calls = 0

        def send_frame_to_gemini(cropped_frame, frame_timestamp):
            """Send a single cropped frame to Gemini and extract subtitles."""
            nonlocal frames_analyzed, api_calls

            # Convert OpenCV BGR to RGB for PIL
            cropped_rgb = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(cropped_rgb)

            # Focused prompt for subtitle extraction from cropped bottom area
            prompt = f"""Analyze this image fragment (bottom of a video frame at timestamp {frame_timestamp:.1f}s).
Extract the Hebrew text/subtitles visible.

Return ONLY a JSON array in this format:
[{{"text": "הטקסט כאן", "start": "{int(frame_timestamp // 60):02d}:{int(frame_timestamp % 60):02d}", "end": "{int((frame_timestamp + 1) // 60):02d}:{int((frame_timestamp + 1) % 60):02d}"}}]

IMPORTANT:
- Accuracy is critical
- If text is visible, extract it exactly as shown
- If no text is visible, return: []
- Return ONLY the JSON array, nothing else"""

            # Retry loop - retry on ANY error
            for attempt in range(MAX_RETRIES):
                try:
                    # Small delay between API calls
                    if api_calls > 0:
                        time.sleep(API_DELAY_SEC)

                    response = model.generate_content([prompt, pil_image])
                    api_calls += 1
                    frames_analyzed += 1

                    if response and response.text:
                        raw_response = response.text.strip()

                        # Try to parse as JSON
                        try:
                            cleaned_json = clean_json_response(raw_response)
                            subtitle_list = json.loads(cleaned_json)

                            if isinstance(subtitle_list, list) and len(subtitle_list) > 0:
                                parsed_entries = []
                                for item in subtitle_list:
                                    if isinstance(item, dict) and 'text' in item:
                                        text = item.get('text', '').strip()
                                        if text and len(text) > 1:
                                            entry = {
                                                'start': parse_time_to_seconds(item.get('start', frame_timestamp)),
                                                'end': parse_time_to_seconds(item.get('end', frame_timestamp + 1)),
                                                'text': text
                                            }
                                            parsed_entries.append(entry)
                                return parsed_entries
                            return []

                        except json.JSONDecodeError:
                            # Try to extract text directly if JSON fails
                            fallback_text = raw_response
                            for pattern in ['```json', '```', '[', ']', '{', '}', '"start"', '"end"', '"text"', ':', ',']:
                                fallback_text = fallback_text.replace(pattern, ' ')
                            fallback_text = ' '.join(fallback_text.split()).strip()

                            # Check if it looks like actual subtitle text (Hebrew or meaningful)
                            if fallback_text and len(fallback_text) > 2 and any('\u0590' <= c <= '\u05FF' for c in fallback_text):
                                return [{
                                    'start': frame_timestamp,
                                    'end': frame_timestamp + 1,
                                    'text': fallback_text
                                }]
                            return []
                    return []

                except Exception as e:
                    print(f"[WARNING] API error (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)[:50]}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY_SEC)
                        continue
                    else:
                        print(f"[ERROR] Failed after {MAX_RETRIES} attempts")
                        return []

            return []

        # Main frame processing loop - process EVERY sampled frame (no skipping)
        total_samples = int(video_duration / SAMPLE_INTERVAL_SEC) + 1
        sample_num = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % sample_interval == 0:
                current_time = frame_count / fps if fps > 0 else 0
                height, width = frame.shape[:2]

                # Crop bottom 30% of frame (subtitle area only)
                crop_start = int(height * (1 - CROP_BOTTOM_PERCENT))
                cropped = frame[crop_start:height, :]

                sample_num += 1
                if sample_num % 5 == 1:  # Log every 5 samples
                    print(f"[INFO] מעבד פריים {sample_num}/{total_samples} (זמן: {current_time:.1f}s)...")

                # Send to Gemini and get entries
                entries = send_frame_to_gemini(cropped, current_time)
                all_subtitle_entries.extend(entries)

            frame_count += 1

        cap.release()

        print(f"[INFO] סטטיסטיקה: {frames_analyzed} פריימים נותחו, {api_calls} קריאות API")
        print(f"[INFO] נמצאו {len(all_subtitle_entries)} רשומות כתוביות (לפני מיזוג)")

        if not all_subtitle_entries:
            print(f"[WARNING] לא זוהה טקסט בסרטון")
            return "לא זוהו כתוביות בסרטון", []

        # CRITICAL: Merge consecutive similar subtitles (80% similarity threshold)
        merged_entries = merge_consecutive_subtitles(all_subtitle_entries)

        # Ensure proper timing for each subtitle
        for entry in merged_entries:
            # Don't exceed video duration
            entry['end'] = min(entry['end'], video_duration)

            # Ensure minimum duration of 2 seconds for natural narration
            duration = entry['end'] - entry['start']
            if duration < MIN_SUBTITLE_DURATION:
                entry['end'] = min(entry['start'] + MIN_SUBTITLE_DURATION, video_duration)

            # Safety check: end must be after start
            if entry['end'] <= entry['start']:
                entry['end'] = entry['start'] + MIN_SUBTITLE_DURATION

        print(f"[SUCCESS] נמצאו {len(merged_entries)} כתוביות ייחודיות (אחרי מיזוג)")

        # Build final_script for Edge-TTS by concatenating all text in chronological order
        raw_script = " ".join([entry['text'] for entry in merged_entries])

        # Clean duplicate consecutive words from the script
        final_script = clean_duplicate_words(raw_script)

        print(f"[SUCCESS] נוצרו {len(merged_entries)} כתוביות לקריינות")
        print(f"[INFO] סקריפט לקריינות ({len(final_script)} תווים): {final_script[:100]}..." if len(final_script) > 100 else f"[INFO] סקריפט לקריינות: {final_script}")

        return final_script, merged_entries

    except Exception as e:
        print(f"[ERROR] Gemini Vision error: {e}")
        import traceback
        traceback.print_exc()
        return f"שגיאה: {str(e)}", []

def extract_text_from_video_vision(video_path):
    """מחלץ טקסט מהווידאו בעזרת בקשת HTTP ישירה - גרסה סופית וחסינה"""
    import cv2
    import base64
    import os
    import requests

    print(f"[INFO] דוגם תמונות מהסרטון: {video_path}")
    
    frames_to_send = []
    try:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        interval = max(int(fps), 1) 
        count = 0
        
        while cap.isOpened() and len(frames_to_send) < 10:
            ret, frame = cap.read()
            if not ret: break
            if count % interval == 0:
                _, buffer = cv2.imencode('.jpg', frame)
                frames_to_send.append(base64.b64encode(buffer).decode('utf-8'))
            count += 1
        cap.release()

        if not frames_to_send:
            raise Exception("לא הצלחתי לדגום תמונות מהסרטון.")

        api_key = os.getenv("GEMINI_API_KEY")
        
        # כתובת ה-API הרשמית בגרסה 1
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={api_key}"
        
        headers = {'Content-Type': 'application/json'}
        inline_data = [{"inline_data": {"mime_type": "image/jpeg", "data": f}} for f in frames_to_send]
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "תמלל את הטקסט שמופיע על המסך בעברית. אם אין טקסט, תאר במשפט אחד מה רואים."},
                    *inline_data
                ]
            }]
        }

        print(f"[INFO] שולח בקשה ל-Gemini API...")
        response = requests.post(url, headers=headers, json=payload, verify=False)
        
        if response.status_code == 200:
            response_data = response.json()
            transcript = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"[SUCCESS] טקסט שחולץ: {transcript[:50]}...")
            return transcript, [{"start": 0, "end": 10, "text": transcript}]
        
        # אם יש 404, ננסה להבין אילו מודלים כן קיימים
        if response.status_code == 404:
            diag_url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
            diag_res = requests.get(diag_url, verify=False)
            print(f"[DEBUG] רשימת מודלים זמינים: {diag_res.text}")
            
        raise Exception(f"Gemini API Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"[CRITICAL ERROR] {str(e)}")
        raise e

        print(f"[INFO] שולח {len(frames_to_send)} תמונות ל-Gemini...")
        
        headers = {'Content-Type': 'application/json'}
        inline_data = [{"inline_data": {"mime_type": "image/jpeg", "data": f}} for f in frames_to_send]
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": "תמלל את הטקסט שמופיע על המסך בעברית. אם אין טקסט, תאר במשפט אחד מה רואים."},
                    *inline_data
                ]
            }]
        }

        # שליחה ללא בדיקת SSL כדי לעקוף חסימות
        response = requests.post(url, headers=headers, json=payload, verify=False)
        
        if response.status_code == 200:
            response_data = response.json()
            if 'candidates' in response_data:
                transcript = response_data['candidates'][0]['content']['parts'][0]['text'].strip()
                print(f"[SUCCESS] טקסט שחולץ: {transcript[:50]}...")
                return transcript, [{"start": 0, "end": 10, "text": transcript}]
        
        # אם הגענו לכאן, ה-API נכשל - עוצרים הכל
        error_detail = response.text if response.text else "שגיאה לא ידועה"
        raise Exception(f"Gemini API Error (Status {response.status_code}): {error_detail}")

    except Exception as e:
        # מדפיס לטרמינל וזורק את השגיאה הלאה כדי ש-main.py יפסיק את התהליך
        print(f"[CRITICAL ERROR] {str(e)}")
        raise e


async def generate_voiceover_free(text, output_path):
    """
    יצירת קריינות איכותית בחינם לגמרי באמצעות Microsoft Edge
    """
    print(f"[INFO] מייצר קריינות בחינם לטקסט: {text[:30]}...")
    # he-IL-AvriNeural הוא קול גברי מעולה, he-IL-HilaNeural הוא נשי
    communicate = edge_tts.Communicate(text, "he-IL-AvriNeural")
    await communicate.save(output_path)
    return True

# פונקציה עוטפת שתואמת ל-Main.py הסינכרוני שלך
def generate_voiceover_sync(text, output_path):
    try:
        asyncio.run(generate_voiceover_free(text, output_path))
        return True
    except Exception as e:
        print(f"[ERROR] Voiceover failed: {e}")
        return False

# פונקציה לבדיקה האם יש אודיו בסרטון
def check_video_has_audio(v_path):
    cmd = [
        'ffprobe', '-i', str(v_path), '-show_streams', 
        '-select_streams', 'a', '-loglevel', 'error'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return len(result.stdout.strip()) > 0

# פונקציית המיזוג המתוקנת
def merge_final_video(v_input, srt_input, v_output, music_path, voice_path):
    """
    Merge video with voiceover, music, and subtitles.
    Fixed: subtitles are now integrated into filter_complex when audio mixing is used.
    FFmpeg doesn't allow both -filter_complex and -vf simultaneously.
    """
    has_orig_audio = check_video_has_audio(v_input)

    cmd = ['ffmpeg', '-y', '-i', str(v_input)]
    inputs = 1
    audio_filter_parts = []
    audio_nodes = []

    # טיפול באודיו מקורי
    if has_orig_audio:
        audio_filter_parts.append("[0:a]volume=0.4[main_a]")
        audio_nodes.append("[main_a]")

    # הוספת קריינות
    if voice_path and os.path.exists(voice_path):
        cmd.extend(['-i', str(voice_path)])
        audio_filter_parts.append(f"[{inputs}:a]volume=2.5[v]")
        audio_nodes.append("[v]")
        inputs += 1

    # הוספת מוזיקה
    if music_path and os.path.exists(music_path):
        cmd.extend(['-i', str(music_path)])
        audio_filter_parts.append(f"[{inputs}:a]volume=0.2[m]")
        audio_nodes.append("[m]")
        inputs += 1

    # בדיקה אם יש כתוביות
    has_subtitles = srt_input and os.path.exists(srt_input)
    if has_subtitles:
        subtitle_path = str(srt_input).replace("\\", "/").replace(":", "\\:")

    # בניית filter_complex משולב (אודיו + וידאו)
    if audio_nodes:
        filter_complex_parts = []

        # הוספת פילטר וידאו (כתוביות) אם יש
        if has_subtitles:
            filter_complex_parts.append(f"[0:v]subtitles='{subtitle_path}'[vout]")

        # הוספת פילטרי אודיו
        filter_complex_parts.extend(audio_filter_parts)

        # מיזוג אודיו
        amix_inputs = ''.join(audio_nodes)
        filter_complex_parts.append(f"{amix_inputs}amix=inputs={len(audio_nodes)}:duration=first[aout]")

        full_filter = ';'.join(filter_complex_parts)
        print(f"[DEBUG] FFmpeg filter_complex: {full_filter}")

        if has_subtitles:
            cmd.extend(['-filter_complex', full_filter, '-map', '[vout]', '-map', '[aout]'])
        else:
            cmd.extend(['-filter_complex', full_filter, '-map', '0:v', '-map', '[aout]'])
    else:
        # אין מיקס אודיו - אפשר להשתמש ב-vf רגיל
        cmd.extend(['-map', '0:v'])
        if has_subtitles:
            cmd.extend(['-vf', f"subtitles='{subtitle_path}'"])

    cmd.extend(['-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', str(v_output)])

    print(f"[INFO] Running FFmpeg merge command...")
    print(f"[DEBUG] Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        print(f"[ERROR] FFmpeg failed: {result.stderr[:500]}")
        raise Exception(f"FFmpeg merge failed: {result.stderr[:200]}")

    print(f"[SUCCESS] Video merged: {v_output}")

# עדכון ה-Workflow
async def process_video_complete_workflow(
    video_path,
    output_dir,
    do_subtitles,
    do_voiceover,
    do_music,
    music_style,
    music_dir,
    progress_callback
):
    has_audio = check_video_has_audio(video_path)
    
    # אם המשתמש רוצה קריינות ואין אודיו - נפעיל OCR אוטומטית
    if do_voiceover and not has_audio:
        progress_callback(10, "לא זוהה אודיו, מחלץ טקסט מהמסך...")
        transcript, entries = extract_text_from_video_ocr(video_path)
    elif has_audio:
        # כאן אפשר להוסיף תמלול רגיל (Whisper) אם יש אודיו
        pass


def get_random_music(style, music_dir):
    """
    Get a random music file matching the given style.
    Scans the music folder for files containing the style keyword.

    Args:
        style: One of 'calm', 'dramatic', 'uplifting', 'spiritual'
        music_dir: Path to the music directory

    Returns:
        Path to a random matching music file, or None if not found
    """
    music_path = Path(music_dir)
    if not music_path.exists():
        print(f"[WARNING] Music directory not found: {music_dir}")
        return None

    # Map styles to keywords that might appear in filenames
    style_keywords = {
        'calm': ['calm', 'peaceful', 'ambient', 'soft', 'quiet', 'chill', 'relaxing', 'smooth'],
        'dramatic': ['dramatic', 'epic', 'cinematic', 'intense', 'powerful', 'orchestral'],
        'uplifting': ['uplifting', 'inspiring', 'happy', 'upbeat', 'positive', 'bright', 'energetic'],
        'spiritual': ['spiritual', 'emotional', 'gentle', 'piano', 'nature', 'meditation']
    }

    # Get keywords for the requested style
    keywords = style_keywords.get(style.lower(), [style.lower()])

    # Find all matching files
    all_music = list(music_path.glob("*.mp3"))
    matching_files = []

    for music_file in all_music:
        filename_lower = music_file.name.lower()
        for keyword in keywords:
            if keyword in filename_lower:
                matching_files.append(music_file)
                break

    if matching_files:
        selected = random.choice(matching_files)
        print(f"[INFO] Selected music for style '{style}': {selected.name} (from {len(matching_files)} matches)")
        return selected
    elif all_music:
        # Fallback to random if no matches
        selected = random.choice(all_music)
        print(f"[INFO] No music matches for style '{style}', using random: {selected.name}")
        return selected
    else:
        print(f"[WARNING] No music files found in {music_dir}")
        return None


def download_audio_from_url(url, output_dir, progress_callback=None):
    """
    Download audio from YouTube, Pixabay, or other supported URLs using yt-dlp.
    Converts to MP3 format.

    Args:
        url: URL to download from (YouTube, Pixabay, etc.)
        output_dir: Directory to save the downloaded file
        progress_callback: Optional progress callback

    Returns:
        Path to the downloaded MP3 file, or None if failed
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

    # Generate unique filename
    file_id = str(uuid.uuid4())[:8]
    output_template = str(output_path / f"downloaded_{file_id}.%(ext)s")

    if progress_callback:
        progress_callback(0, "מוריד מוזיקה מהקישור...")

    print(f"[INFO] Downloading audio from: {url}")

    # yt-dlp options for audio extraction
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
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Download and extract audio
            info = ydl.extract_info(url, download=True)

            if progress_callback:
                progress_callback(50, "ממיר ל-MP3...")

            # Find the downloaded file
            if info:
                # The output file should be the template with .mp3 extension
                expected_file = output_path / f"downloaded_{file_id}.mp3"

                if expected_file.exists():
                    print(f"[SUCCESS] Audio downloaded: {expected_file}")
                    if progress_callback:
                        progress_callback(100, "הורדה הושלמה!")
                    return expected_file

                # Search for any file matching the pattern
                for f in output_path.glob(f"downloaded_{file_id}.*"):
                    if f.suffix.lower() in ['.mp3', '.m4a', '.wav', '.opus', '.webm']:
                        # If not MP3, convert it
                        if f.suffix.lower() != '.mp3':
                            mp3_path = output_path / f"downloaded_{file_id}.mp3"
                            convert_cmd = [
                                'ffmpeg', '-y', '-i', str(f),
                                '-acodec', 'libmp3lame', '-q:a', '2',
                                str(mp3_path)
                            ]
                            result = subprocess.run(convert_cmd, capture_output=True)
                            if result.returncode == 0 and mp3_path.exists():
                                f.unlink()  # Remove original
                                print(f"[SUCCESS] Audio converted to MP3: {mp3_path}")
                                return mp3_path
                        else:
                            return f

        print("[ERROR] Could not find downloaded audio file")
        return None

    except Exception as e:
        print(f"[ERROR] Failed to download audio: {e}")
        import traceback
        traceback.print_exc()
        return None


def list_music_library(music_dir):
    """
    List all music files in the library directory.

    Args:
        music_dir: Path to the music directory

    Returns:
        List of dictionaries with file info: [{'name': 'file.mp3', 'path': '/path/to/file.mp3'}, ...]
    """
    music_path = Path(music_dir)
    if not music_path.exists():
        return []

    music_files = []
    for ext in ['*.mp3', '*.wav', '*.m4a', '*.ogg']:
        for f in music_path.glob(ext):
            # Skip temp folder
            if 'temp' in str(f).lower():
                continue
            music_files.append({
                'name': f.stem,  # Filename without extension
                'filename': f.name,  # Full filename
                'path': str(f)
            })

    # Sort by name
    music_files.sort(key=lambda x: x['name'].lower())
    print(f"[INFO] Found {len(music_files)} music files in library")
    return music_files


def prepare_hebrew_text(text):
    """
    Prepare Hebrew text for proper RTL rendering in images.
    Reverses the text so it displays correctly when rendered LTR.
    """
    if not text:
        return text

    # Check if text contains Hebrew characters
    has_hebrew = any('\u0590' <= char <= '\u05FF' for char in text)

    if has_hebrew:
        # Reverse the entire string for RTL display
        return text[::-1]

    return text


def extract_text_from_video_ocr(video_path, progress_callback=None):
    """
    Extract text from video frames using Tesseract OCR (for videos without audio).
    Samples the bottom portion of frames every 2 seconds where subtitles typically appear.

    Args:
        video_path: Path to video file
        progress_callback: Optional callback for progress updates

    Returns:
        tuple: (extracted_text, list of dict entries with 'start', 'end', 'text' keys)
    """
    if progress_callback:
        progress_callback(0, "סורק כתוביות מהמסך (OCR)...")

    print(f"[INFO] Starting OCR extraction from video: {video_path}")

    try:
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            print(f"[ERROR] Could not open video: {video_path}")
            return "", []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        print(f"[INFO] Video: {duration:.1f}s, {fps:.1f} FPS, {total_frames} frames")

        # Sample every 2 seconds
        sample_interval = 2.0
        segment_duration = 3.0  # Default subtitle duration
        frame_interval = int(fps * sample_interval)

        extracted_entries = []  # List of dicts with start, end, text
        seen_texts = set()  # To avoid duplicates

        frame_num = 0
        samples_taken = 0
        total_samples = int(duration / sample_interval) + 1

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Only process every frame_interval frames
            if frame_num % frame_interval == 0:
                current_time = frame_num / fps

                if progress_callback:
                    pct = int((samples_taken / max(total_samples, 1)) * 80)
                    progress_callback(pct, f"סורק פריים {samples_taken + 1}/{total_samples}...")

                # Get frame dimensions
                height, width = frame.shape[:2]

                # Crop to bottom 25% where subtitles usually appear
                subtitle_region = frame[int(height * 0.75):height, :]

                # Convert to grayscale for better OCR
                gray = cv2.cvtColor(subtitle_region, cv2.COLOR_BGR2GRAY)

                # Apply threshold to get black text on white background
                # Try both normal and inverted for different subtitle colors
                _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
                _, thresh_inv = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

                # Try OCR on both versions
                text1 = pytesseract.image_to_string(thresh, lang='heb+eng', config='--psm 6')
                text2 = pytesseract.image_to_string(thresh_inv, lang='heb+eng', config='--psm 6')

                # Use the one with more content
                text = text1 if len(text1.strip()) > len(text2.strip()) else text2

                # Clean the text
                text = text.strip()
                text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                text = re.sub(r'[^\w\s\u0590-\u05FF.,!?\'\"()-]', '', text)  # Keep Hebrew, English, punctuation

                # Only add if text is meaningful (at least 3 chars) and not a duplicate
                if len(text) >= 3:
                    # Create a normalized version for duplicate detection
                    normalized = text.lower().strip()
                    if normalized not in seen_texts:
                        seen_texts.add(normalized)
                        # Use new dict format (same as Gemini function)
                        extracted_entries.append({
                            'start': current_time,
                            'end': min(current_time + segment_duration, duration),
                            'text': text
                        })
                        print(f"[OCR] {current_time:.1f}s: {text[:50]}...")

                samples_taken += 1

            frame_num += 1

        cap.release()

        if progress_callback:
            progress_callback(85, "מעבד טקסט שחולץ...")

        # Combine all unique texts into one string (using dict format)
        all_text = ' '.join([entry['text'] for entry in extracted_entries])

        print(f"[SUCCESS] OCR extracted {len(extracted_entries)} unique text segments")
        print(f"[INFO] Total text length: {len(all_text)} chars")

        return all_text, extracted_entries

    except Exception as e:
        print(f"[ERROR] OCR extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return "", []


def fix_subtitles_with_ai(srt_path, progress_callback=None):
    """
    Fix and improve SRT subtitles using Gemini AI.
    Corrects spelling mistakes, grammar, and religious terms in Hebrew.

    Args:
        srt_path: Path to the SRT file to fix
        progress_callback: Optional progress callback

    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(srt_path):
        print(f"[ERROR] SRT file not found: {srt_path}")
        return False

    if progress_callback:
        progress_callback(0, "מתקן כתוביות עם AI...")

    try:
        # Read the raw SRT content
        with open(srt_path, 'r', encoding='utf-8') as f:
            raw_srt_content = f.read()

        if not raw_srt_content.strip():
            print("[WARNING] SRT file is empty, nothing to fix")
            return False

        print(f"[INFO] מתקן כתוביות עם Gemini AI...")
        print(f"[INFO] גודל קובץ מקורי: {len(raw_srt_content)} תווים")

        # Initialize Gemini model
        model = genai.GenerativeModel('models/gemini-2.5-flash')

        # The correction prompt
        prompt = """You are an expert Hebrew editor. Below is a raw SRT file transcribed from a video of a Rabbi speaking.

Your task:
1. Correct spelling mistakes (especially religious terms like תורה, מצוות, הקב"ה, etc.)
2. Fix grammatical errors while keeping the natural flow of speech
3. IMPORTANT: Remove accidentally repeated words or phrases (like "גיד הנשה גיד הנשה" → "גיד הנשה")
4. Remove stuttering or duplicate phrases that appear consecutively
5. DO NOT change the timestamps (00:00:00,000 --> 00:00:00,000)
6. Keep the output in the EXACT same SRT format (number, timestamp, text, blank line)
7. The speaker is Rabbi Meir Or Shraga - ensure titles and names are spelled correctly
8. Keep Hebrew religious terms accurate (ברוך השם, אמן, הלכה, etc.)
9. Make the text flow naturally and smoothly for voiceover narration

IMPORTANT: Return ONLY the corrected SRT content. No explanations, no markdown.

Here is the SRT file to correct:

"""

        # Send to Gemini for correction
        full_prompt = prompt + raw_srt_content

        # Retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if progress_callback:
                    progress_callback(30, f"שולח לתיקון AI (ניסיון {attempt + 1})...")

                response = model.generate_content(full_prompt)

                if response and response.text:
                    corrected_srt = response.text.strip()

                    # Clean up any markdown that might have been added
                    if '```srt' in corrected_srt:
                        corrected_srt = corrected_srt.split('```srt')[1]
                        if '```' in corrected_srt:
                            corrected_srt = corrected_srt.split('```')[0]
                    elif '```' in corrected_srt:
                        parts = corrected_srt.split('```')
                        if len(parts) >= 2:
                            corrected_srt = parts[1]
                            if '```' in corrected_srt:
                                corrected_srt = corrected_srt.split('```')[0]

                    corrected_srt = corrected_srt.strip()

                    # Validate the corrected SRT has the right format
                    if '-->' in corrected_srt and corrected_srt[0].isdigit():
                        # Backup original file
                        backup_path = str(srt_path) + '.backup'
                        with open(backup_path, 'w', encoding='utf-8') as f:
                            f.write(raw_srt_content)

                        # Write corrected content
                        with open(srt_path, 'w', encoding='utf-8') as f:
                            f.write(corrected_srt)

                        print(f"[SUCCESS] כתוביות תוקנו בהצלחה!")
                        print(f"[INFO] גודל קובץ מתוקן: {len(corrected_srt)} תווים")
                        print(f"[INFO] גיבוי נשמר ב: {backup_path}")

                        # Show preview of corrections
                        original_lines = raw_srt_content.split('\n')[:10]
                        corrected_lines = corrected_srt.split('\n')[:10]
                        print(f"[INFO] תצוגה מקדימה (10 שורות ראשונות):")
                        print(f"  מקור: {' | '.join(original_lines[:3])}")
                        print(f"  מתוקן: {' | '.join(corrected_lines[:3])}")

                        if progress_callback:
                            progress_callback(100, "כתוביות תוקנו בהצלחה!")

                        return True
                    else:
                        print(f"[WARNING] התגובה מ-Gemini אינה בפורמט SRT תקין, מנסה שוב...")
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            continue
                else:
                    print(f"[WARNING] תגובה ריקה מ-Gemini")

            except Exception as e:
                print(f"[WARNING] שגיאה בניסיון {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue

        print(f"[ERROR] נכשל לתקן כתוביות אחרי {max_retries} ניסיונות")
        return False

    except Exception as e:
        print(f"[ERROR] Failed to fix subtitles: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_srt_from_ocr(ocr_entries, output_path, segment_duration=3.0):
    """
    Create an SRT file from subtitle entries.

    Args:
        ocr_entries: List of dictionaries with 'start', 'end', 'text' keys
                     Example: [{"start": 2.0, "end": 5.0, "text": "Hello"}]
                     Or: [{"start": "00:02", "end": "00:05", "text": "Hello"}]
        output_path: Path for output SRT file
        segment_duration: Default duration if 'end' is missing (seconds)

    Returns:
        bool: Success status
    """
    if not ocr_entries:
        print("[WARNING] No entries to create SRT from")
        return False

    def parse_time_value(time_val):
        """Convert time value to seconds (handles both float and string formats)."""
        if isinstance(time_val, (int, float)):
            return float(time_val)
        if isinstance(time_val, str):
            # Handle "MM:SS" or "HH:MM:SS" format
            parts = time_val.split(':')
            try:
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    return int(parts[0]) * 60 + float(parts[1])
                else:
                    return float(time_val)
            except:
                return 0.0
        return 0.0

    try:
        entries_written = 0
        srt_content_preview = []

        with open(output_path, 'w', encoding='utf-8') as f:
            for i, entry in enumerate(ocr_entries, 1):
                # Handle both dict format and legacy tuple format
                if isinstance(entry, dict):
                    start_time = parse_time_value(entry.get('start', 0))
                    end_time = parse_time_value(entry.get('end', start_time + segment_duration))
                    text = entry.get('text', '').strip()
                elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    # Legacy tuple format: (timestamp, text)
                    start_time = parse_time_value(entry[0])
                    end_time = start_time + segment_duration
                    text = str(entry[1]).strip()
                else:
                    print(f"[WARNING] Skipping invalid entry: {entry}")
                    continue

                # Skip empty text
                if not text:
                    continue

                # Ensure end > start
                if end_time <= start_time:
                    end_time = start_time + segment_duration

                # Format times to SRT format (HH:MM:SS,mmm)
                start_str = format_srt_time(start_time)
                end_str = format_srt_time(end_time)

                # Write SRT entry
                srt_entry = f"{i}\n{start_str} --> {end_str}\n{text}\n\n"
                f.write(srt_entry)
                entries_written += 1

                # Save preview of first 3 entries
                if entries_written <= 3:
                    srt_content_preview.append(f"  [{i}] {start_str} -> {end_str}: {text[:40]}...")

        # Validate the SRT file was created correctly
        if entries_written > 0:
            file_size = os.path.getsize(output_path)
            print(f"[SRT OK] קובץ כתוביות נוצר בהצלחה!")
            print(f"[SRT OK] נתיב: {output_path}")
            print(f"[SRT OK] {entries_written} כתוביות, {file_size} bytes")
            print(f"[SRT OK] תצוגה מקדימה:")
            for preview_line in srt_content_preview:
                print(preview_line)

            # Verify file is readable
            with open(output_path, 'r', encoding='utf-8') as verify_f:
                first_lines = verify_f.read(500)
                if first_lines and '-->' in first_lines:
                    print(f"[SRT OK] אימות: קובץ SRT תקין ✓")
                    return True
                else:
                    print(f"[ERROR] אימות נכשל: קובץ SRT לא תקין")
                    return False
        else:
            print(f"[ERROR] No entries written to SRT file")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to create SRT: {e}")
        import traceback
        traceback.print_exc()
        return False


def format_srt_time(seconds):
    """Format seconds to SRT timestamp format."""
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d},{ms:03d}"


def format_ass_time(seconds):
    """Format seconds to ASS timestamp format (H:MM:SS.cc)."""
    cs = int((seconds - int(seconds)) * 100)
    s = int(seconds)
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}.{cs:02d}"


def get_video_frame_count(video_path):
    """Get total frame count using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-count_packets",
            "-show_entries", "stream=nb_read_packets",
            "-of", "csv=p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            return int(result.stdout.strip())
    except Exception as e:
        print(f"[WARNING] Could not get frame count: {e}")

    # Fallback: estimate from duration and fps
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration,r_frame_rate",
            "-of", "csv=p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        parts = result.stdout.strip().split(',')
        if len(parts) >= 2:
            fps_parts = parts[0].split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
            duration = float(parts[1])
            return int(fps * duration)
    except Exception:
        pass

    return 0


def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        print(f"[WARNING] Could not get duration: {e}")
    return 0


def get_video_resolution(video_path):
    """Get video width and height using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            parts = result.stdout.strip().split(',')
            return int(parts[0]), int(parts[1])
    except Exception as e:
        print(f"[WARNING] Could not get resolution: {e}")
    return 1920, 1080


def extract_and_compress_audio(video_path, output_audio_path, progress_callback=None):
    """
    Extract audio from video and compress to MP3 (64kbps mono) for Groq API.
    Aims for under 25MB file size.
    """
    if progress_callback:
        progress_callback(0, "מחלץ אודיו מהסרטון...")

    v_abs = str(Path(video_path).absolute())
    audio_abs = str(Path(output_audio_path).absolute())

    cmd = [
        "ffmpeg", "-y",
        "-i", v_abs,
        "-vn",  # No video
        "-acodec", "libmp3lame",
        "-ab", "64k",  # 64kbps bitrate
        "-ac", "1",  # Mono channel
        "-ar", "16000",  # 16kHz sample rate (good for speech)
        audio_abs
    ]

    print(f"[INFO] Extracting audio: {' '.join(cmd)}")

    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        if process.returncode != 0:
            print(f"[ERROR] Audio extraction failed: {process.stderr}")
            return False

        if os.path.exists(audio_abs):
            size_mb = os.path.getsize(audio_abs) / (1024 * 1024)
            print(f"[INFO] Compressed audio size: {size_mb:.2f} MB")

            if size_mb > 25:
                print(f"[WARNING] Audio file exceeds 25MB limit ({size_mb:.2f} MB)")

            if progress_callback:
                progress_callback(5, f"אודיו נחלץ ({size_mb:.1f} MB)")

            return True
        else:
            print(f"[ERROR] Audio file not created")
            return False

    except Exception as e:
        print(f"[ERROR] Audio extraction error: {e}")
        return False


def transcribe_with_groq(v_path, s_path, progress_callback=None):
    """
    Transcribe video using Groq API with whisper-large-v3 model.
    Returns transcript text for marketing analysis.
    """
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)

        # Step 1: Extract and compress audio
        audio_path = Path(v_path).parent / f"{Path(v_path).stem}_temp_audio.mp3"

        if not extract_and_compress_audio(v_path, audio_path, progress_callback):
            print("[ERROR] Failed to extract audio")
            if progress_callback:
                progress_callback(20, "שגיאה בחילוץ אודיו")
            return False, ""

        if progress_callback:
            progress_callback(10, "שולח לתמלול Groq...")

        print(f"[INFO] Sending audio to Groq API for transcription...")

        # Step 2: Transcribe with Groq API
        transcript_text = ""
        try:
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

            print(f"[INFO] Transcription received from Groq")

            # Get full transcript text
            transcript_text = transcription.text if hasattr(transcription, 'text') else ""

            # Step 3: Format as SRT
            segments = transcription.segments if hasattr(transcription, 'segments') else []

            if not segments:
                print("[WARNING] No segments returned, using full text")
                duration = get_video_duration(v_path)
                with open(s_path, "w", encoding="utf-8", newline='\n') as f:
                    f.write(f"1\n{format_srt_time(0)} --> {format_srt_time(duration)}\n{transcript_text.strip()}\n\n")
            else:
                with open(s_path, "w", encoding="utf-8", newline='\n') as f:
                    for i, seg in enumerate(segments, 1):
                        start = seg.get('start', seg.start if hasattr(seg, 'start') else 0)
                        end = seg.get('end', seg.end if hasattr(seg, 'end') else start + 2)
                        text = seg.get('text', seg.text if hasattr(seg, 'text') else '')
                        f.write(f"{i}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text.strip()}\n\n")

                print(f"[INFO] SRT file created with {len(segments)} segments")

            if progress_callback:
                progress_callback(20, "תמלול הושלם")

            return True, transcript_text

        except Exception as api_error:
            print(f"[ERROR] Groq API error: {api_error}")
            if progress_callback:
                progress_callback(20, f"שגיאת Groq: {str(api_error)[:40]}")
            return False, ""

        finally:
            try:
                if audio_path.exists():
                    audio_path.unlink()
                    print(f"[CLEANUP] Deleted temp audio: {audio_path}")
            except Exception as e:
                print(f"[WARNING] Could not delete temp audio: {e}")

    except ImportError:
        print("[ERROR] groq library not installed. Run: pip install groq")
        if progress_callback:
            progress_callback(20, "חסרה ספריית groq")
        return False, ""
    except Exception as e:
        print(f"[ERROR] Transcription error: {e}")
        import traceback
        traceback.print_exc()
        if progress_callback:
            progress_callback(20, f"שגיאה: {str(e)[:40]}")
        return False, ""


def generate_marketing_kit(transcript_text, video_duration, progress_callback=None):
    """
    Use Groq LLM (llama-3.3-70b-versatile) to generate marketing content.
    Returns: titles, post, keywords, viral_moments
    """
    if not transcript_text:
        print("[WARNING] No transcript for marketing kit")
        return None

    try:
        from groq import Groq

        if progress_callback:
            progress_callback(22, "יוצר ערכת שיווק...")

        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""אתה מומחה שיווק דיגיטלי. נתח את התמליל הבא של סרטון וצור חומרי שיווק.

תמליל הסרטון:
{transcript_text[:4000]}

אורך הסרטון: {int(video_duration)} שניות

החזר JSON בפורמט הבא בלבד (ללא טקסט נוסף):
{{
    "titles": ["כותרת 1", "כותרת 2", "כותרת 3"],
    "facebook_post": "פוסט מושך לפייסבוק עם אימוג'ים",
    "keywords": ["מילת מפתח 1", "מילת מפתח 2", "מילת מפתח 3"],
    "hashtags": ["#האשטאג1", "#האשטאג2", "#האשטאג3", "#האשטאג4", "#האשטאג5"],
    "viral_moments": [
        {{"start": 10, "end": 40, "reason": "ציטוט חזק"}},
        {{"start": 60, "end": 90, "reason": "רגע מרגש"}},
        {{"start": 120, "end": 150, "reason": "תובנה חשובה"}}
    ],
    "image_prompt": "English prompt for AI image generation",
    "music_style": "calm"
}}

הנחיות:
- הכותרות צריכות להיות קליטות ומושכות
- הפוסט צריך לעורר עניין ולהזמין צפייה
- מילות המפתח לקידום אורגני
- viral_moments: 3 קטעים של 20-40 שניות שמתאימים לסרטונים קצרים (Shorts/Reels)
- ודא שה-timestamps לא חורגים מאורך הסרטון ({int(video_duration)} שניות)
- image_prompt: כתוב פרומפט באנגלית ליצירת תמונה ב-AI. התמונה צריכה להיות קולנועית ומרשימה. תאר סצנה ויזואלית שמתאימה לתוכן הסרטון. הפרומפט חייב להיות באנגלית בלבד!
- music_style: בחר אחד מהערכים הבאים בהתאם לאווירת הסרטון: "calm" (רגוע), "dramatic" (דרמטי), "uplifting" (מעורר השראה), "spiritual" (רוחני)
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500
        )

        response_text = response.choices[0].message.content.strip()
        print(f"[DEBUG] LLM Response: {response_text[:500]}...")

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            marketing_data = json.loads(json_match.group())

            # Validate viral moments timestamps
            if 'viral_moments' in marketing_data:
                valid_moments = []
                for moment in marketing_data['viral_moments']:
                    if moment.get('start', 0) < video_duration and moment.get('end', 0) <= video_duration:
                        valid_moments.append(moment)
                marketing_data['viral_moments'] = valid_moments[:3]

            if progress_callback:
                progress_callback(28, "ערכת שיווק נוצרה")

            print(f"[INFO] Marketing kit generated successfully")
            return marketing_data
        else:
            print(f"[ERROR] Could not parse JSON from LLM response")
            return None

    except Exception as e:
        print(f"[ERROR] Marketing kit generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def convert_srt_to_ass(srt_path, ass_path, video_width=1920, video_height=1080):
    """
    Convert SRT to ASS format with TikTok-style subtitles.
    Bold, Yellow, centered, with outline for readability.
    Uses Arial font (Windows-safe).
    """
    print(f"[INFO] Converting SRT to styled ASS format...")

    # ASS header with TikTok-style formatting
    ass_header = f"""[Script Info]
Title: TikTok Style Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFF00,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    try:
        # Read SRT file
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_content = f.read()

        # Parse SRT segments
        segments = []
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)'
        matches = re.findall(pattern, srt_content, re.DOTALL)

        for match in matches:
            idx, start, end, text = match
            # Convert SRT time to ASS time
            start_ass = start.replace(',', '.')[:-1]  # Remove last digit, change comma to dot
            end_ass = end.replace(',', '.')[:-1]

            # Convert HH:MM:SS.cc format
            start_parts = start.replace(',', '.').split(':')
            end_parts = end.replace(',', '.').split(':')

            start_ass = f"{int(start_parts[0])}:{start_parts[1]}:{start_parts[2][:5]}"
            end_ass = f"{int(end_parts[0])}:{end_parts[1]}:{end_parts[2][:5]}"

            # Clean text (remove newlines, add ASS formatting)
            clean_text = text.strip().replace('\n', '\\N')

            segments.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{clean_text}")

        # Write ASS file
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header)
            f.write('\n'.join(segments))

        print(f"[INFO] ASS file created with {len(segments)} segments")
        return True

    except Exception as e:
        print(f"[ERROR] ASS conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def cut_viral_shorts(video_path, viral_moments, output_dir, subtitle_path=None, use_ass=False, progress_callback=None):
    """
    Cut viral shorts from the video based on timestamps.
    Optionally burns in subtitles if subtitle_path is provided.
    Returns list of output paths.
    """
    if not viral_moments:
        print("[WARNING] No viral moments to cut")
        return []

    shorts_dir = Path(output_dir) / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    output_paths = []
    v_abs = str(Path(video_path).absolute())

    # Check if we have subtitles to burn in
    has_subtitles = subtitle_path is not None and os.path.exists(str(subtitle_path))
    if has_subtitles:
        s_escaped = escape_ffmpeg_path(subtitle_path)
        print(f"[INFO] Will burn subtitles into shorts: {subtitle_path} (ASS={use_ass})")

    for i, moment in enumerate(viral_moments[:3], 1):
        if progress_callback:
            progress_callback(30 + (i * 3), f"חותך קליפ {i}/3...")

        start = moment.get('start', 0)
        end = moment.get('end', start + 30)
        duration = end - start

        output_path = shorts_dir / f"short_{i}.mp4"

        # Build FFmpeg command
        # Use -ss AFTER -i for accurate subtitle timing (subtitles use original timestamps)
        cmd = [
            "ffmpeg", "-y",
            "-i", v_abs,
            "-ss", str(start),
            "-t", str(duration),
        ]

        # Add subtitle filter if we have subtitles
        if has_subtitles:
            if use_ass:
                cmd.extend(["-vf", f"ass='{s_escaped}'"])
            else:
                cmd.extend(["-vf", f"subtitles='{s_escaped}'"])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_path)
        ])

        print(f"[INFO] Cutting short {i}: {start}s - {end}s (with_subtitles={has_subtitles})")
        print(f"[DEBUG] Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.returncode == 0 and output_path.exists():
                output_paths.append(str(output_path))
                print(f"[SUCCESS] Short {i} created: {output_path}")
            else:
                print(f"[ERROR] Failed to create short {i}: {result.stderr[:200]}")

        except Exception as e:
            print(f"[ERROR] Short cutting failed: {e}")

    return output_paths


def generate_thumbnail(video_path, title, output_path, progress_callback=None):
    """
    Generate thumbnail with title overlay using FFmpeg and Pillow.
    Extracts a frame and overlays the title text.
    """
    if progress_callback:
        progress_callback(42, "יוצר תמונה ממוזערת...")

    try:
        from PIL import Image, ImageDraw, ImageFont

        v_abs = str(Path(video_path).absolute())
        temp_frame = Path(output_path).parent / "temp_frame.jpg"

        # Get video duration and extract frame from 1/3 of the video
        duration = get_video_duration(video_path)
        frame_time = duration / 3 if duration > 0 else 5

        # Extract high-quality frame
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(frame_time),
            "-i", v_abs,
            "-vframes", "1",
            "-q:v", "2",
            str(temp_frame)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode != 0 or not temp_frame.exists():
            print(f"[ERROR] Failed to extract frame: {result.stderr[:200]}")
            return False

        # Open image and add title overlay
        img = Image.open(temp_frame)
        draw = ImageDraw.Draw(img)

        # Try to use a nice font, fallback to default
        font_size = int(img.height / 12)
        try:
            # Try Windows fonts
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except:
                font = ImageFont.load_default()

        # Text settings - prepare for RTL Hebrew
        text = title[:50] if len(title) > 50 else title
        display_text = prepare_hebrew_text(text)

        # Calculate text position (centered, bottom third)
        bbox = draw.textbbox((0, 0), display_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (img.width - text_width) / 2
        y = img.height - text_height - (img.height / 6)

        # Draw text shadow/outline
        shadow_offset = 3
        for dx in [-shadow_offset, 0, shadow_offset]:
            for dy in [-shadow_offset, 0, shadow_offset]:
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), display_text, font=font, fill=(0, 0, 0))

        # Draw main text (yellow)
        draw.text((x, y), display_text, font=font, fill=(255, 255, 0))

        # Save thumbnail
        img.save(output_path, "JPEG", quality=95)

        # Cleanup temp frame
        if temp_frame.exists():
            temp_frame.unlink()

        if progress_callback:
            progress_callback(45, "תמונה ממוזערת נוצרה")

        print(f"[SUCCESS] Thumbnail created: {output_path}")
        return True

    except ImportError:
        print("[ERROR] Pillow not installed. Run: pip install Pillow")
        return False
    except Exception as e:
        print(f"[ERROR] Thumbnail generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def escape_ffmpeg_path(path):
    """Escape file path for FFmpeg filter on Windows."""
    abs_path = str(Path(path).absolute())
    escaped = abs_path.replace("\\", "/")
    if len(escaped) >= 2 and escaped[1] == ':':
        escaped = escaped[0] + "\\:" + escaped[2:]
    escaped = escaped.replace("'", "'\\''")
    return escaped


def check_video_has_audio(video_path):
    """Check if video file has an audio stream."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return "audio" in result.stdout.lower()
    except Exception as e:
        print(f"[WARNING] Could not check audio stream: {e}")
        return True


def merge_video_assets(v_path, s_path, out_path, m_path=None, use_ass=False, progress_callback=None):
    """
    Merge video with optional subtitles and background music (with ducking).
    Supports both SRT and ASS subtitle formats.
    """
    v_abs = str(Path(v_path).absolute())
    out_abs = str(Path(out_path).absolute())

    has_music = m_path is not None and os.path.exists(str(m_path))
    has_subtitles = s_path is not None and os.path.exists(str(s_path))
    has_audio = check_video_has_audio(v_abs)

    total_frames = get_video_frame_count(v_abs)

    print(f"[DEBUG] Video path: {v_abs}")
    print(f"[DEBUG] Video has audio: {has_audio}")
    print(f"[DEBUG] Total frames: {total_frames}")
    print(f"[DEBUG] Music path: {m_path} (exists: {has_music})")
    print(f"[DEBUG] Subtitle path: {s_path} (exists: {has_subtitles})")
    print(f"[DEBUG] Using ASS format: {use_ass}")

    if progress_callback:
        progress_callback(50, "מתחיל עיבוד וידאו...")

    cmd = ["ffmpeg", "-y", "-i", v_abs]

    if has_music:
        m_abs = str(Path(m_path).absolute())
        print(f"[DEBUG] Adding music: {m_abs}")
        cmd.extend(["-stream_loop", "-1", "-i", m_abs])

    filter_parts = []

    if has_music and has_audio:
        ducking = (
            "[1:a]volume=0.6[music_vol];"
            "[music_vol][0:a]sidechaincompress="
            "threshold=0.1:"
            "ratio=4:"
            "attack=100:"
            "release=800:"
            "level_sc=0.5"
            "[music_ducked];"
            "[0:a][music_ducked]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        filter_parts.append(ducking)
    elif has_music and not has_audio:
        print(f"[INFO] Video has no audio, using music only at 60% volume")
        filter_parts.append("[1:a]volume=0.6[aout]")

    if has_subtitles:
        s_escaped = escape_ffmpeg_path(s_path)
        if use_ass:
            # Use ASS subtitles - specify fontsdir for Windows
            filter_parts.append(f"[0:v]ass='{s_escaped}'[vout]")
        else:
            # Use SRT subtitles
            filter_parts.append(f"[0:v]subtitles='{s_escaped}'[vout]")

    if filter_parts:
        filter_complex = ";".join(filter_parts)
        print(f"[DEBUG] Filter complex: {filter_complex}")
        cmd.extend(["-filter_complex", filter_complex])

        if has_subtitles:
            cmd.extend(["-map", "[vout]"])
        else:
            cmd.extend(["-map", "0:v"])

        if has_music:
            cmd.extend(["-map", "[aout]"])
        elif has_audio:
            cmd.extend(["-map", "0:a"])
    else:
        cmd.extend(["-map", "0:v"])
        if has_audio:
            cmd.extend(["-map", "0:a"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-progress", "pipe:1",
        out_abs
    ])

    print(f"[DEBUG] Full command:")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))

    print(f"[INFO] Running FFmpeg...")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        output_lines = []
        current_frame = 0

        for line in process.stdout:
            line = line.strip()
            if line:
                output_lines.append(line)

                if line.startswith("frame="):
                    try:
                        current_frame = int(line.split("=")[1])
                    except (ValueError, IndexError):
                        pass

                frame_match = re.search(r'frame=\s*(\d+)', line)
                if frame_match:
                    current_frame = int(frame_match.group(1))

                if progress_callback and total_frames > 0 and current_frame > 0:
                    render_progress = min(95, 50 + int((current_frame / total_frames) * 45))
                    progress_callback(render_progress, f"מעבד פריים {current_frame}/{total_frames}")

                if "frame=" in line or "time=" in line:
                    print(f"\r[FFmpeg] {line[:80]}", end="", flush=True)
                elif "error" in line.lower() or "Error" in line:
                    print(f"\n[FFmpeg ERROR] {line}")
                elif "Stream" in line or "Input" in line or "Output" in line:
                    print(f"[FFmpeg] {line}")

        process.wait()
        print()

        if process.returncode != 0:
            print(f"[ERROR] FFmpeg exited with code {process.returncode}")
            print("[DEBUG] Last FFmpeg output:")
            for line in output_lines[-20:]:
                print(f"  {line}")
            if progress_callback:
                progress_callback(95, "שגיאה בעיבוד")
            return False

        print(f"[SUCCESS] FFmpeg completed successfully")
        if progress_callback:
            progress_callback(95, "עיבוד וידאו הושלם")

    except Exception as e:
        print(f"[ERROR] FFmpeg execution failed: {e}")
        import traceback
        traceback.print_exc()
        if progress_callback:
            progress_callback(95, f"שגיאה: {str(e)[:30]}")
        return False

    time.sleep(1)
    return os.path.exists(out_abs)


def generate_ai_thumbnail_image(prompt, title, output_path, progress_callback=None):
    """
    Generate AI thumbnail using Leonardo.ai API.
    Downloads the image and overlays the title text using Pillow.
    """
    if not LEONARDO_API_KEY:
        print("[ERROR] Leonardo API key not found in environment")
        return False

    if progress_callback:
        progress_callback(0, "מייצר תמונה ב-AI...")

    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # Step 1: Create generation request
        print(f"[INFO] Sending prompt to Leonardo.ai: {prompt[:100]}...")

        generation_url = "https://cloud.leonardo.ai/api/rest/v1/generations"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {LEONARDO_API_KEY}",
            "content-type": "application/json"
        }

        payload = {
            "height": 720,
            "width": 1280,
            "modelId": "1e60896f-3c26-4296-8ecc-53e2afecc132",  # Leonardo Diffusion XL
            "prompt": prompt,
            "num_images": 1,
            "promptMagic": True,
            "public": False
        }

        response = requests.post(generation_url, json=payload, headers=headers)
        print(f"[DEBUG] Leonardo API response status: {response.status_code}")

        if response.status_code != 200:
            print(f"[ERROR] Leonardo API error: {response.text}")
            return False

        generation_data = response.json()
        generation_id = generation_data.get("sdGenerationJob", {}).get("generationId")

        if not generation_id:
            print(f"[ERROR] No generation ID returned: {generation_data}")
            return False

        print(f"[INFO] Generation started with ID: {generation_id}")

        if progress_callback:
            progress_callback(20, "ממתין ליצירת התמונה...")

        # Step 2: Poll for completion
        status_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
        max_attempts = 60  # 2 minutes max
        attempt = 0

        while attempt < max_attempts:
            time.sleep(2)
            attempt += 1

            status_response = requests.get(status_url, headers=headers)
            if status_response.status_code != 200:
                print(f"[WARNING] Status check failed: {status_response.text}")
                continue

            status_data = status_response.json()
            generation_status = status_data.get("generations_by_pk", {}).get("status")

            if progress_callback:
                progress_callback(20 + int(attempt * 0.8), f"יוצר תמונה... ({attempt}/{max_attempts})")

            print(f"[DEBUG] Generation status: {generation_status}")

            if generation_status == "COMPLETE":
                generated_images = status_data.get("generations_by_pk", {}).get("generated_images", [])
                if generated_images:
                    image_url = generated_images[0].get("url")
                    print(f"[INFO] Image generated: {image_url}")
                    break
            elif generation_status == "FAILED":
                print(f"[ERROR] Generation failed")
                return False
        else:
            print(f"[ERROR] Generation timed out")
            return False

        if progress_callback:
            progress_callback(70, "מוריד את התמונה...")

        # Step 3: Download the image
        img_response = requests.get(image_url)
        if img_response.status_code != 200:
            print(f"[ERROR] Failed to download image")
            return False

        img = Image.open(io.BytesIO(img_response.content))

        if progress_callback:
            progress_callback(80, "מוסיף כותרת לתמונה...")

        # Step 4: Add title overlay (YouTube style)
        draw = ImageDraw.Draw(img)

        # Try to use a nice font
        font_size = int(img.height / 10)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
                except:
                    font = ImageFont.load_default()

        # Prepare text - handle RTL Hebrew
        text = title[:40] if len(title) > 40 else title
        display_text = prepare_hebrew_text(text)

        # Calculate text position (centered, bottom third)
        bbox = draw.textbbox((0, 0), display_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (img.width - text_width) / 2
        y = img.height - text_height - (img.height / 8)

        # Draw text shadow/outline (thick black outline for YouTube style)
        outline_width = 4
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), display_text, font=font, fill=(0, 0, 0))

        # Draw main text (bold yellow)
        draw.text((x, y), display_text, font=font, fill=(255, 255, 0))

        # Save the final image
        img.save(output_path, "JPEG", quality=95)

        if progress_callback:
            progress_callback(100, "התמונה נוצרה בהצלחה!")

        print(f"[SUCCESS] AI thumbnail saved: {output_path}")

        # NetFree warning - print in yellow
        print(f"\033[93m[NETFREE] התמונה עלולה להיות בבדיקת NetFree. לחץ על הקישור הבא לאישור: {image_url}\033[0m")

        # Return success and original URL for NetFree retry
        return True, image_url

    except Exception as e:
        print(f"[ERROR] AI thumbnail generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def download_image_from_url(url, output_path, title=None):
    """
    Download image from URL and optionally add title overlay.
    Used for NetFree retry downloads.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        print(f"[INFO] Downloading image from: {url[:80]}...")

        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"[ERROR] Failed to download image: HTTP {response.status_code}")
            return False

        img = Image.open(io.BytesIO(response.content))

        # Add title overlay if provided
        if title:
            draw = ImageDraw.Draw(img)

            font_size = int(img.height / 10)
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()

            # Prepare text - handle RTL Hebrew
            text = title[:40] if len(title) > 40 else title
            display_text = prepare_hebrew_text(text)

            # Calculate text position
            bbox = draw.textbbox((0, 0), display_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (img.width - text_width) / 2
            y = img.height - text_height - (img.height / 8)

            # Draw text shadow/outline
            outline_width = 4
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), display_text, font=font, fill=(0, 0, 0))

            # Draw main text (yellow)
            draw.text((x, y), display_text, font=font, fill=(255, 255, 0))

        # Save
        img.save(output_path, "JPEG", quality=95)
        print(f"[SUCCESS] Image saved: {output_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Image download failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def parse_srt_file(srt_path):
    """
    Parse SRT file and return list of subtitle entries.
    Each entry: {'index': int, 'start': float, 'end': float, 'text': str}
    """
    entries = []
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by double newlines (subtitle blocks)
        blocks = re.split(r'\n\n+', content.strip())

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                try:
                    index = int(lines[0])
                    # Parse timing line: 00:00:01,000 --> 00:00:04,500
                    timing_match = re.match(
                        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})',
                        lines[1]
                    )
                    if timing_match:
                        g = timing_match.groups()
                        start = int(g[0])*3600 + int(g[1])*60 + int(g[2]) + int(g[3])/1000
                        end = int(g[4])*3600 + int(g[5])*60 + int(g[6]) + int(g[7])/1000
                        text = ' '.join(lines[2:]).strip()
                        entries.append({
                            'index': index,
                            'start': start,
                            'end': end,
                            'text': text
                        })
                except (ValueError, IndexError):
                    continue

        print(f"[INFO] Parsed {len(entries)} subtitle entries from SRT")
        return entries

    except Exception as e:
        print(f"[ERROR] Failed to parse SRT: {e}")
        return []


def text_similarity(text1, text2):
    """
    Calculate similarity ratio between two texts using SequenceMatcher.
    Returns a value between 0 and 1 (1 = identical).
    """
    from difflib import SequenceMatcher
    # Normalize texts
    t1 = text1.strip().lower()
    t2 = text2.strip().lower()
    if not t1 or not t2:
        return 0.0
    return SequenceMatcher(None, t1, t2).ratio()


def clean_and_merge_srt(entries, min_gap_seconds=0.3):
    """
    Clean and merge SRT entries to fix synchronization issues.

    Features:
    1. Deduplication: Merge subtitles with >85% text similarity
    2. Overlap correction: Ensure start time is never before previous end time
    3. Filter short repeated sentences: Skip <3 word sentences that appeared in last 10 seconds
    4. Ensure minimum gap between entries (default 300ms)

    Args:
        entries: List of subtitle entries from parse_srt_file
        min_gap_seconds: Minimum gap between subtitles (default 0.3 = 300ms)

    Returns:
        List of cleaned and merged entries
    """
    if not entries:
        return entries

    print(f"[INFO] Cleaning SRT: {len(entries)} entries before processing")

    # Sort by start time first
    sorted_entries = sorted(entries, key=lambda x: x['start'])

    cleaned = []
    recent_texts = []  # Track texts from last 10 seconds: [(text, timestamp)]

    for entry in sorted_entries:
        text = entry['text'].strip()
        start = entry['start']
        end = entry['end']

        # Skip empty entries
        if not text:
            continue

        # Filter: Skip short sentences (<3 words) that appeared in last 10 seconds
        word_count = len(text.split())
        if word_count < 3:
            # Check if similar text appeared in last 10 seconds
            cutoff_time = start - 10.0
            recent_in_window = [t for t, ts in recent_texts if ts >= cutoff_time]

            is_duplicate = False
            for recent_text in recent_in_window:
                if text_similarity(text, recent_text) > 0.85:
                    print(f"[DEBUG] Skipping short duplicate: '{text[:30]}...'")
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

        # Track this text for future duplicate detection
        recent_texts.append((text, start))
        # Keep only texts from last 15 seconds for memory efficiency
        recent_texts = [(t, ts) for t, ts in recent_texts if ts >= start - 15.0]

        if not cleaned:
            # First entry
            cleaned.append({
                'index': 1,
                'start': start,
                'end': end,
                'text': text
            })
            continue

        prev = cleaned[-1]

        # Check for text similarity with previous entry (deduplication)
        similarity = text_similarity(prev['text'], text)

        if similarity > 0.85:
            # Merge: Extend previous entry's end time, keep the longer/combined text
            print(f"[DEBUG] Merging similar entries (similarity={similarity:.2f})")
            prev['end'] = max(prev['end'], end)
            # Keep the longer text or combine if both are substantial
            if len(text) > len(prev['text']):
                prev['text'] = text
            continue

        # Overlap correction: Ensure start is after previous end + minimum gap
        if start < prev['end'] + min_gap_seconds:
            # Push start time forward
            new_start = prev['end'] + min_gap_seconds
            # Also need to push end time forward proportionally
            duration = end - start
            start = new_start
            end = start + max(duration, 0.5)  # Minimum 0.5 second duration
            print(f"[DEBUG] Fixed overlap: adjusted start to {start:.2f}")

        cleaned.append({
            'index': len(cleaned) + 1,
            'start': start,
            'end': end,
            'text': text
        })

    print(f"[INFO] Cleaning SRT: {len(cleaned)} entries after processing (removed {len(entries) - len(cleaned)})")
    return cleaned


def write_srt_from_entries(entries, output_path):
    """
    Write SRT file from cleaned entries.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries, 1):
            start_str = format_srt_time(entry['start'])
            end_str = format_srt_time(entry['end'])
            f.write(f"{i}\n{start_str} --> {end_str}\n{entry['text']}\n\n")
    print(f"[INFO] Written {len(entries)} entries to {output_path}")


def clean_text_for_voiceover(text):
    """
    Clean text before sending to voiceover.
    Removes accidental word repetitions like 'word word' or 'גיד הנשה גיד הנשה'.
    """
    if not text:
        return text

    words = text.split()
    if len(words) < 2:
        return text

    cleaned_words = [words[0]]

    for i in range(1, len(words)):
        # Check for immediate repetition
        if words[i].lower() != words[i-1].lower():
            cleaned_words.append(words[i])
        else:
            print(f"[DEBUG] Removed repeated word: '{words[i]}'")

    # Also check for phrase repetitions (2-3 word patterns)
    result = ' '.join(cleaned_words)

    # Remove repeated 2-word phrases
    words = result.split()
    if len(words) >= 4:
        i = 0
        final_words = []
        while i < len(words):
            # Check if next 2 words repeat the previous 2
            if i >= 2 and i + 1 < len(words):
                prev_phrase = ' '.join(words[i-2:i]).lower()
                curr_phrase = ' '.join(words[i:i+2]).lower()
                if prev_phrase == curr_phrase:
                    print(f"[DEBUG] Removed repeated phrase: '{curr_phrase}'")
                    i += 2
                    continue
            final_words.append(words[i])
            i += 1
        result = ' '.join(final_words)

    return result


def clean_srt_text_with_ai(entries, progress_callback=None):
    """
    Use Gemini AI to clean and improve SRT entries text before voiceover.
    Removes repeated words/phrases and creates flowing, natural text.

    Args:
        entries: List of SRT entries (each with 'text' key)
        progress_callback: Optional progress callback

    Returns:
        List of entries with cleaned text
    """
    if not entries or not GEMINI_API_KEY:
        print("[WARNING] No entries or no Gemini API key, skipping AI text cleaning")
        return entries

    try:
        # Combine all texts for context
        all_texts = [e['text'] for e in entries]
        combined_text = '\n'.join([f"{i+1}. {t}" for i, t in enumerate(all_texts)])

        if progress_callback:
            progress_callback(0, "מנקה טקסט עם AI...")

        model = genai.GenerativeModel('models/gemini-2.5-flash')

        prompt = """אתה עורך טקסט מקצועי. קיבלת רשימה של כתוביות מסרטון.

המשימה שלך:
1. הסר מילים שחוזרות בטעות (כמו "גיד הנשה גיד הנשה" → "גיד הנשה")
2. הסר ביטויים כפולים
3. הפוך את הטקסט לזורם וטבעי
4. שמור על המשמעות המקורית
5. אל תשנה מונחים דתיים או שמות

החזר את הרשימה באותו פורמט בדיוק (מספר. טקסט), רק עם הטקסט המתוקן.

הרשימה:
"""
        full_prompt = prompt + combined_text

        try:
            response = model.generate_content(full_prompt)

            if response and response.text:
                cleaned_response = response.text.strip()

                # Parse the response back into entries
                lines = cleaned_response.split('\n')
                cleaned_texts = {}

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # Parse "1. text" format
                    match = re.match(r'^(\d+)\.\s*(.+)$', line)
                    if match:
                        idx = int(match.group(1)) - 1
                        text = match.group(2).strip()
                        if 0 <= idx < len(entries):
                            cleaned_texts[idx] = text

                # Update entries with cleaned texts
                for idx, text in cleaned_texts.items():
                    if text and len(text) >= 2:  # Only update if we got meaningful text
                        entries[idx]['text'] = text

                print(f"[INFO] AI cleaned {len(cleaned_texts)} text entries")

        except Exception as e:
            print(f"[WARNING] AI text cleaning failed: {e}")

    except Exception as e:
        print(f"[ERROR] Failed to clean text with AI: {e}")

    return entries


async def generate_voiceover_segment(text, output_path, voice="he-IL-AvriNeural", rate="-5%"):
    """
    Generate a single voiceover segment using edge-tts.
    Rate is set to -5% for slightly slower, more natural speech.
    """
    try:
        import edge_tts

        # Clean text before generating voiceover
        cleaned_text = clean_text_for_voiceover(text)

        # Create communicate with rate parameter
        communicate = edge_tts.Communicate(cleaned_text, voice, rate=rate)
        await communicate.save(str(output_path))
        return os.path.exists(output_path)
    except Exception as e:
        print(f"[ERROR] Segment generation failed: {e}")
        return False


def get_audio_duration(audio_path):
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


async def generate_voiceover_from_srt(srt_path, output_path, video_duration, progress_callback=None):
    """
    Generate synchronized voiceover from SRT file.
    Creates audio segments for each subtitle entry and combines them with proper timing.

    Features:
    - Cleans and merges duplicate/overlapping subtitles
    - Uses -5% speech rate for more natural pacing
    - Ensures minimum 300ms gap between segments
    - Removes accidentally repeated words
    """
    if not os.path.exists(srt_path):
        print(f"[ERROR] SRT file not found: {srt_path}")
        return False

    if progress_callback:
        progress_callback(0, "מייצר קריינות מסונכרנת...")

    try:
        import edge_tts
        from pydub import AudioSegment
    except ImportError:
        print("[WARNING] pydub not available, falling back to simple voiceover")
        # Fallback: just read SRT text and generate simple voiceover
        entries = parse_srt_file(srt_path)
        entries = clean_and_merge_srt(entries, min_gap_seconds=0.3)
        full_text = ' '.join([clean_text_for_voiceover(e['text']) for e in entries])
        return await generate_voiceover(full_text, output_path, progress_callback)

    # Parse and clean the SRT entries
    raw_entries = parse_srt_file(srt_path)
    if not raw_entries:
        print("[ERROR] No subtitle entries found in SRT")
        return False

    # Clean and merge entries (deduplication, overlap fix, 300ms minimum gap)
    if progress_callback:
        progress_callback(5, "מנקה כפילויות וחפיפות בכתוביות...")

    entries = clean_and_merge_srt(raw_entries, min_gap_seconds=0.3)

    if not entries:
        print("[ERROR] No entries left after cleaning")
        return False

    # Use AI to clean up repeated words and create flowing text
    if progress_callback:
        progress_callback(8, "מנקה טקסט עם AI...")

    entries = clean_srt_text_with_ai(entries, progress_callback)

    # Write the cleaned SRT back for consistency
    cleaned_srt_path = Path(srt_path).parent / f"{Path(srt_path).stem}_cleaned.srt"
    write_srt_from_entries(entries, cleaned_srt_path)

    temp_dir = Path(output_path).parent / "temp_voiceover"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create a silent audio base matching video duration
        total_duration_ms = int(video_duration * 1000)
        combined = AudioSegment.silent(duration=total_duration_ms)

        total_entries = len(entries)
        print(f"[INFO] Generating voiceover for {total_entries} cleaned entries")

        for i, entry in enumerate(entries):
            if progress_callback:
                pct = int(10 + (i / total_entries) * 70)
                progress_callback(pct, f"מייצר קריינות... ({i+1}/{total_entries})")

            temp_file = temp_dir / f"segment_{i:04d}.mp3"

            # Generate audio for this segment (text is cleaned inside the function)
            success = await generate_voiceover_segment(entry['text'], temp_file)

            if success and temp_file.exists():
                try:
                    segment = AudioSegment.from_mp3(str(temp_file))

                    # Calculate position in milliseconds
                    start_ms = int(entry['start'] * 1000)

                    # Calculate available duration for this subtitle
                    available_duration_ms = int((entry['end'] - entry['start']) * 1000)

                    # If segment is longer than available time, speed it up slightly
                    if len(segment) > available_duration_ms and available_duration_ms > 0:
                        speed_factor = len(segment) / available_duration_ms
                        if speed_factor < 1.5:  # Don't speed up too much
                            # Use FFmpeg to change speed
                            sped_up_file = temp_dir / f"segment_{i:04d}_fast.mp3"
                            speed_cmd = [
                                "ffmpeg", "-y", "-i", str(temp_file),
                                "-filter:a", f"atempo={min(speed_factor, 1.5)}",
                                str(sped_up_file)
                            ]
                            subprocess.run(speed_cmd, capture_output=True)
                            if sped_up_file.exists():
                                segment = AudioSegment.from_mp3(str(sped_up_file))

                    # Overlay segment at the correct position
                    if start_ms < total_duration_ms:
                        combined = combined.overlay(segment, position=start_ms)

                except Exception as e:
                    print(f"[WARNING] Failed to process segment {i}: {e}")

        if progress_callback:
            progress_callback(90, "שומר קובץ קריינות...")

        # Export final audio
        combined.export(str(output_path), format="mp3", bitrate="192k")

        # Cleanup temp files
        for f in temp_dir.glob("*"):
            try:
                f.unlink()
            except:
                pass
        try:
            temp_dir.rmdir()
        except:
            pass

        if os.path.exists(output_path):
            print(f"[SUCCESS] Synchronized voiceover saved: {output_path}")
            if progress_callback:
                progress_callback(100, "קריינות מסונכרנת נוצרה!")
            return True
        else:
            print(f"[ERROR] Voiceover file not created")
            return False

    except Exception as e:
        print(f"[ERROR] Synchronized voiceover generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def generate_voiceover(text, output_path, progress_callback=None):
    """
    Generate Hebrew voiceover using edge-tts (free Microsoft TTS).
    Uses the 'he-IL-AvriNeural' voice for Hebrew male narration.
    """
    if not text or not text.strip():
        print("[WARNING] No text provided for voiceover")
        return False

    if progress_callback:
        progress_callback(0, "מייצר קריינות...")

    try:
        import edge_tts

        print(f"[INFO] Generating voiceover for text: {text[:100]}...")

        # Use Hebrew male voice
        voice = "he-IL-AvriNeural"

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(output_path))

        if os.path.exists(output_path):
            print(f"[SUCCESS] Voiceover saved: {output_path}")
            if progress_callback:
                progress_callback(100, "קריינות נוצרה בהצלחה!")
            return True
        else:
            print(f"[ERROR] Voiceover file not created")
            return False

    except Exception as e:
        print(f"[ERROR] Voiceover generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_voiceover_from_srt_sync(srt_path, output_path, video_duration, progress_callback=None):
    """
    Synchronous wrapper for generate_voiceover_from_srt.
    """
    return asyncio.run(generate_voiceover_from_srt(srt_path, output_path, video_duration, progress_callback))


def generate_voiceover_sync(text, output_path, progress_callback=None):
    """
    Synchronous wrapper for generate_voiceover.
    """
    return asyncio.run(generate_voiceover(text, output_path, progress_callback))


def merge_voiceover_with_video(video_path, voiceover_path, music_path, output_path,
                               replace_audio=True, mix_original_volume=0.2, progress_callback=None):
    """
    Merge voiceover audio with video and optional background music.

    Args:
        video_path: Path to input video
        voiceover_path: Path to voiceover audio file
        music_path: Path to background music (optional)
        output_path: Path for output video
        replace_audio: If True, replace original audio. If False, mix voiceover with original audio.
        mix_original_volume: Volume level for original audio when mixing (0.0-1.0)
        progress_callback: Progress callback function
    """
    if progress_callback:
        progress_callback(0, "ממזג קריינות עם הסרטון...")

    v_abs = str(Path(video_path).absolute())
    vo_abs = str(Path(voiceover_path).absolute())
    out_abs = str(Path(output_path).absolute())

    has_music = music_path is not None and os.path.exists(str(music_path))
    has_original_audio = check_video_has_audio(video_path)

    cmd = ["ffmpeg", "-y", "-i", v_abs, "-i", vo_abs]

    input_index = 2  # Next input index

    if has_music:
        m_abs = str(Path(music_path).absolute())
        cmd.extend(["-stream_loop", "-1", "-i", m_abs])
        music_index = input_index
        input_index += 1

    # Build filter complex based on options
    filter_parts = []

    if has_music and not replace_audio and has_original_audio:
        # Mix voiceover + original audio (ducked) + music (ducked)
        filter_parts.append(f"[0:a]volume={mix_original_volume}[orig_vol]")
        filter_parts.append(f"[{music_index}:a]volume=0.25[music_vol]")
        filter_parts.append(
            "[orig_vol][1:a]sidechaincompress="
            "threshold=0.03:ratio=8:attack=30:release=400:level_sc=0.5[orig_ducked]"
        )
        filter_parts.append(
            "[music_vol][1:a]sidechaincompress="
            "threshold=0.05:ratio=6:attack=50:release=500:level_sc=0.5[music_ducked]"
        )
        filter_parts.append("[1:a][orig_ducked][music_ducked]amix=inputs=3:duration=first:normalize=0[aout]")

    elif has_music and (replace_audio or not has_original_audio):
        # Voiceover + music (ducked), no original audio
        filter_parts.append(f"[{music_index}:a]volume=0.3[music_vol]")
        filter_parts.append(
            "[music_vol][1:a]sidechaincompress="
            "threshold=0.05:ratio=6:attack=50:release=500:level_sc=0.5[music_ducked]"
        )
        filter_parts.append("[1:a][music_ducked]amix=inputs=2:duration=first:normalize=0[aout]")

    elif not replace_audio and has_original_audio:
        # Mix voiceover + original audio (ducked), no music
        filter_parts.append(f"[0:a]volume={mix_original_volume}[orig_vol]")
        filter_parts.append(
            "[orig_vol][1:a]sidechaincompress="
            "threshold=0.03:ratio=8:attack=30:release=400:level_sc=0.5[orig_ducked]"
        )
        filter_parts.append("[1:a][orig_ducked]amix=inputs=2:duration=first:normalize=0[aout]")
    else:
        # Just voiceover, replace everything
        filter_parts = []

    if filter_parts:
        filter_complex = ";".join(filter_parts)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "0:v", "-map", "[aout]"])
    else:
        # Simple replacement - just use voiceover
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    cmd.extend([
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_abs
    ])

    mode_str = "מחליף" if replace_audio else "ממזג"
    print(f"[INFO] {mode_str} קריינות עם הסרטון...")
    print(f"[DEBUG] Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        if result.returncode == 0 and os.path.exists(out_abs):
            print(f"[SUCCESS] Voiceover merged: {out_abs}")
            if progress_callback:
                progress_callback(100, "קריינות מוזגה בהצלחה!")
            return True
        else:
            print(f"[ERROR] Voiceover merge failed: {result.stderr[:300]}")
            return False

    except Exception as e:
        print(f"[ERROR] Voiceover merge failed: {e}")
        import traceback
        traceback.print_exc()
        return False
