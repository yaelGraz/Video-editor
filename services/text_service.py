"""
Text Service - Handles text extraction, SRT processing, and subtitle management.
"""
import os
import sys
import ssl
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# SSL patch for httplib2 - must be before google.generativeai imports
import certifi

class _MockCerts:
    @staticmethod
    def where():
        return certifi.where()

sys.modules['httplib2.certs'] = _MockCerts
if 'HTTPLIB2_CA_CERTS' in os.environ:
    del os.environ['HTTPLIB2_CA_CERTS']
ssl._create_default_https_context = ssl._create_unverified_context

from utils.config import (
    GEMINI_API_KEY,
    SRT_MIN_GAP_SECONDS,
    SRT_SIMILARITY_THRESHOLD
)
from utils.helpers import format_srt_time, format_ass_time, text_similarity


# =============================================================================
# Text Extraction from Files
# =============================================================================

def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from a Word document (.docx).

    Args:
        file_path: Path to the .docx file

    Returns:
        Extracted text as a string
    """
    try:
        from docx import Document

        doc = Document(file_path)
        full_text = []

        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())

        return '\n'.join(full_text)

    except ImportError:
        raise ImportError("python-docx is required. Install with: pip install python-docx")
    except Exception as e:
        raise Exception(f"Failed to extract text from Word document: {e}")


def extract_text_from_txt(file_path: str, encoding: str = 'utf-8') -> str:
    """
    Extract text from a plain text file.

    Args:
        file_path: Path to the .txt file
        encoding: File encoding (default: utf-8)

    Returns:
        Extracted text as a string
    """
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except UnicodeDecodeError:
        # Try with different encodings
        for enc in ['utf-8-sig', 'cp1255', 'iso-8859-8', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        raise Exception(f"Could not decode file with any known encoding")
    except Exception as e:
        raise Exception(f"Failed to extract text from file: {e}")


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text from a file based on its extension.
    Supports .docx, .doc, .txt files.

    Args:
        file_path: Path to the file

    Returns:
        Extracted text as a string
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == '.docx':
        return extract_text_from_docx(file_path)
    elif extension == '.txt':
        return extract_text_from_txt(file_path)
    elif extension == '.doc':
        raise Exception("Old .doc format not supported. Please convert to .docx")
    else:
        raise Exception(f"Unsupported file format: {extension}")


# =============================================================================
# SRT File Processing
# =============================================================================

def parse_srt_file(srt_path: str) -> List[Dict]:
    """
    Parse SRT file and return list of subtitle entries.
    Each entry: {'index': int, 'start': float, 'end': float, 'text': str}
    """
    entries = []
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Normalize line endings (AI corrections may introduce \r\n or \r)
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        blocks = re.split(r'\n\n+', content.strip())

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                try:
                    index = int(lines[0])
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


def write_srt_from_entries(entries: List[Dict], output_path: str):
    """Write SRT file from entries."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries, 1):
            start_str = format_srt_time(entry['start'])
            end_str = format_srt_time(entry['end'])
            f.write(f"{i}\n{start_str} --> {end_str}\n{entry['text']}\n\n")
    print(f"[INFO] Written {len(entries)} entries to {output_path}")


def create_srt_from_ocr(ocr_entries: List[Dict], output_path: str, segment_duration: float = 3.0):
    """
    Create SRT file from OCR/Gemini extracted entries.

    Args:
        ocr_entries: List of entries with 'text', 'start', 'end' keys
                     (or 'timestamp' as fallback)
        output_path: Path to save the SRT file
        segment_duration: Default duration for each subtitle segment (used as fallback)
    """
    if not ocr_entries:
        print(f"[WARNING] No entries to write to SRT")
        return

    print(f"[INFO] Creating SRT with {len(ocr_entries)} entries...")

    with open(output_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(ocr_entries, 1):
            # Use start/end if available, otherwise fall back to timestamp
            start = entry.get('start', entry.get('timestamp', i * segment_duration))
            end = entry.get('end', start + segment_duration)
            text = entry.get('text', '').strip()

            if not text:
                continue

            # Ensure minimum duration
            if end <= start:
                end = start + 1.0

            start_str = format_srt_time(start)
            end_str = format_srt_time(end)
            f.write(f"{i}\n{start_str} --> {end_str}\n{text}\n\n")

    # Verify file was created and has content
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"[SUCCESS] Created SRT file: {output_path} ({file_size} bytes, {len(ocr_entries)} entries)")
    else:
        print(f"[ERROR] Failed to create SRT file at {output_path}")


def clean_and_merge_srt(entries: List[Dict], min_gap_seconds: float = None) -> List[Dict]:
    """
    Clean and merge SRT entries to fix synchronization issues.

    Features:
    1. Deduplication: Merge subtitles with >85% text similarity
    2. Overlap correction: Ensure start time is never before previous end time
    3. Filter short repeated sentences
    4. Ensure minimum gap between entries
    """
    if min_gap_seconds is None:
        min_gap_seconds = SRT_MIN_GAP_SECONDS

    if not entries:
        return entries

    print(f"[INFO] Cleaning SRT: {len(entries)} entries before processing")

    sorted_entries = sorted(entries, key=lambda x: x['start'])
    cleaned = []
    recent_texts = []

    for entry in sorted_entries:
        text = entry['text'].strip()
        start = entry['start']
        end = entry['end']

        if not text:
            continue

        # Filter short sentences that appeared recently
        word_count = len(text.split())
        if word_count < 3:
            cutoff_time = start - 10.0
            recent_in_window = [t for t, ts in recent_texts if ts >= cutoff_time]
            is_duplicate = False
            for recent_text in recent_in_window:
                if text_similarity(text, recent_text) > SRT_SIMILARITY_THRESHOLD:
                    is_duplicate = True
                    break
            if is_duplicate:
                continue

        recent_texts.append((text, start))
        recent_texts = [(t, ts) for t, ts in recent_texts if ts >= start - 15.0]

        if not cleaned:
            cleaned.append({
                'index': 1,
                'start': start,
                'end': end,
                'text': text
            })
            continue

        prev = cleaned[-1]
        similarity = text_similarity(prev['text'], text)

        if similarity > SRT_SIMILARITY_THRESHOLD:
            prev['end'] = max(prev['end'], end)
            if len(text) > len(prev['text']):
                prev['text'] = text
            continue

        if start < prev['end'] + min_gap_seconds:
            new_start = prev['end'] + min_gap_seconds
            duration = end - start
            start = new_start
            end = start + max(duration, 0.5)

        cleaned.append({
            'index': len(cleaned) + 1,
            'start': start,
            'end': end,
            'text': text
        })

    print(f"[INFO] Cleaning SRT: {len(cleaned)} entries after processing")
    return cleaned


def convert_srt_to_ass(
    srt_path: str,
    ass_path: str,
    video_width: int = 1920,
    video_height: int = 1080,
    font_name: str = "Arial",
    font_color: str = "#FFFFFF",
    font_size: int = 24
) -> bool:
    """
    Convert SRT to ASS format with styled subtitles.

    Args:
        srt_path: Path to input SRT file
        ass_path: Path to output ASS file
        video_width: Video width for resolution
        video_height: Video height for resolution
        font_name: Font family name (e.g., "Assistant", "Rubik Scribble")
        font_color: Hex color string (e.g., "#FFFFFF")
        font_size: Font size in pixels
    """
    try:
        entries = parse_srt_file(srt_path)
        if not entries:
            return False

        # Convert hex color to ASS BGR format
        # ASS uses BGR order: &HBBGGRR&
        hex_color = font_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            ass_primary_color = f"&H00{b}{g}{r}"
        else:
            ass_primary_color = "&H00FFFFFF"

        print(f"[ASS] Using font: {font_name}, size: {font_size}, color: {font_color} -> {ass_primary_color}")

        # ASS header with custom styling
        ass_content = f"""[Script Info]
Title: Styled Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{ass_primary_color},&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,50,50,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        for entry in entries:
            start = format_ass_time(entry['start'])
            end = format_ass_time(entry['end'])
            text = entry['text'].replace('\n', '\\N')
            ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        print(f"[SUCCESS] Converted SRT to ASS: {ass_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to convert SRT to ASS: {e}")
        return False


# =============================================================================
# AI-Powered Text Correction
# =============================================================================

def fix_subtitles_with_ai(srt_path: str, progress_callback=None) -> bool:
    """
    Fix and improve SRT subtitles using Gemini AI.
    Corrects spelling mistakes, grammar, and religious terms in Hebrew.
    """
    import google.generativeai as genai

    if not os.path.exists(srt_path):
        print(f"[ERROR] SRT file not found: {srt_path}")
        return False

    if not GEMINI_API_KEY:
        print("[WARNING] No Gemini API key, skipping AI correction")
        return False

    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            raw_srt_content = f.read()

        if not raw_srt_content.strip():
            return False

        genai.configure(api_key=GEMINI_API_KEY, transport='rest')
        model = genai.GenerativeModel('models/gemini-2.5-flash')

        prompt = """You are an expert Hebrew editor. Below is a raw SRT file transcribed from a video of a Rabbi speaking.

Your task:
1. Correct spelling mistakes (especially religious terms like תורה, מצוות, הקב"ה, etc.)
2. Fix grammatical errors while keeping the natural flow of speech
3. IMPORTANT: Remove accidentally repeated words or phrases
4. DO NOT change the timestamps
5. Keep the output in the EXACT same SRT format
6. Keep Hebrew religious terms accurate

IMPORTANT: Return ONLY the corrected SRT content. No explanations.

Here is the SRT file to correct:

"""

        response = model.generate_content(prompt + raw_srt_content)

        if response and response.text:
            corrected_srt = response.text.strip()

            # Normalize line endings from AI response
            corrected_srt = corrected_srt.replace('\r\n', '\n').replace('\r', '\n')

            # Clean markdown if present
            if '```' in corrected_srt:
                parts = corrected_srt.split('```')
                for part in parts:
                    if '-->' in part:
                        corrected_srt = part.strip()
                        if corrected_srt.startswith('srt'):
                            corrected_srt = corrected_srt[3:].strip()
                        break

            if '-->' in corrected_srt:
                # Backup original
                backup_path = str(srt_path) + '.backup'
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(raw_srt_content)

                with open(srt_path, 'w', encoding='utf-8') as f:
                    f.write(corrected_srt)

                print(f"[SUCCESS] Subtitles corrected with AI")
                return True

        return False

    except Exception as e:
        print(f"[ERROR] AI subtitle correction failed: {e}")
        return False


def clean_srt_text_with_ai(entries: List[Dict], progress_callback=None) -> List[Dict]:
    """
    Use Gemini AI to clean and improve SRT entries text before voiceover.
    """
    import google.generativeai as genai

    if not entries or not GEMINI_API_KEY:
        return entries

    try:
        genai.configure(api_key=GEMINI_API_KEY, transport='rest')

        all_texts = [e['text'] for e in entries]
        combined_text = '\n'.join([f"{i+1}. {t}" for i, t in enumerate(all_texts)])

        model = genai.GenerativeModel('models/gemini-2.5-flash')

        prompt = """אתה עורך טקסט מקצועי. קיבלת רשימה של כתוביות מסרטון.

המשימה שלך:
1. הסר מילים שחוזרות בטעות
2. הסר ביטויים כפולים
3. הפוך את הטקסט לזורם וטבעי
4. שמור על המשמעות המקורית

החזר את הרשימה באותו פורמט בדיוק (מספר. טקסט):

"""

        response = model.generate_content(prompt + combined_text)

        if response and response.text:
            lines = response.text.strip().split('\n')
            cleaned_texts = {}

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r'^(\d+)\.\s*(.+)$', line)
                if match:
                    idx = int(match.group(1)) - 1
                    text = match.group(2).strip()
                    if 0 <= idx < len(entries) and text:
                        cleaned_texts[idx] = text

            for idx, text in cleaned_texts.items():
                entries[idx]['text'] = text

            print(f"[INFO] AI cleaned {len(cleaned_texts)} text entries")

    except Exception as e:
        print(f"[WARNING] AI text cleaning failed: {e}")

    return entries
