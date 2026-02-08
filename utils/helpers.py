"""
Helper utilities for Video AI Studio.
Includes SSL bypass configuration and common utility functions.
"""
import os
import sys
import ssl

# =============================================================================
# SSL CERTIFICATE BYPASS - Call this at startup
# =============================================================================
def setup_ssl_bypass():
    """
    Configure SSL for environments with certificate issues.
    Must be called before making any HTTPS requests.
    Uses certifi for valid certificate paths.
    Includes support for requests, httpx, urllib3, httplib2, and gRPC.
    """
    import certifi

    # Use certifi's certificate bundle for all SSL operations
    cert_path = certifi.where()

    # CRITICAL: Mock httplib2.certs module to prevent RuntimeError
    # Must be done before httplib2 is imported
    class MockCerts:
        @staticmethod
        def where():
            return cert_path

    sys.modules['httplib2.certs'] = MockCerts

    # Remove potentially invalid paths first
    for env_var in ['HTTPLIB2_CA_CERTS']:
        if env_var in os.environ:
            del os.environ[env_var]

    # Set certificate paths using certifi (valid certificate file)
    os.environ['REQUESTS_CA_BUNDLE'] = cert_path
    os.environ['SSL_CERT_FILE'] = cert_path
    os.environ['CURL_CA_BUNDLE'] = cert_path

    # gRPC SSL configuration (for Google Gemini API)
    os.environ["GRPC_SSL_CIPHER_SUITES"] = "HIGH+ECDSA"
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = cert_path

    # Patch httplib2 if already imported
    try:
        import httplib2
        httplib2.CA_CERTS = cert_path
    except ImportError:
        pass

    print(f"[SSL] Configured with certifi certificates: {cert_path}")

    # Override default SSL context creation
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except AttributeError:
        pass

    # Disable urllib3 SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Patch requests library
    import requests
    _original_request = requests.Session.request

    def _patched_request(self, method, url, **kwargs):
        if 'verify' not in kwargs:
            kwargs['verify'] = False
        return _original_request(self, method, url, **kwargs)

    requests.Session.request = _patched_request

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

    # Patch httpx library (used by google-generativeai)
    try:
        import httpx

        # Store original classes
        _original_httpx_client = httpx.Client
        _original_httpx_async_client = httpx.AsyncClient

        # Create patched Client class
        class PatchedHttpxClient(_original_httpx_client):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault('verify', False)
                super().__init__(*args, **kwargs)

        # Create patched AsyncClient class
        class PatchedHttpxAsyncClient(_original_httpx_async_client):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault('verify', False)
                super().__init__(*args, **kwargs)

        # Replace original classes
        httpx.Client = PatchedHttpxClient
        httpx.AsyncClient = PatchedHttpxAsyncClient

        print("[SSL] httpx patched for SSL bypass")

    except ImportError:
        pass  # httpx not installed
    except Exception as e:
        print(f"[SSL WARNING] Could not patch httpx: {e}")


def format_srt_time(seconds):
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_ass_time(seconds):
    """Convert seconds to ASS time format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def text_similarity(text1, text2):
    """
    Calculate similarity ratio between two texts using SequenceMatcher.
    Returns a value between 0 and 1 (1 = identical).
    """
    from difflib import SequenceMatcher
    t1 = text1.strip().lower()
    t2 = text2.strip().lower()
    if not t1 or not t2:
        return 0.0
    return SequenceMatcher(None, t1, t2).ratio()


def prepare_hebrew_text(text):
    """
    Prepare Hebrew text for proper RTL rendering in images.
    Uses BiDi algorithm for correct character ordering.
    """
    if not text:
        return text

    # Check if text contains Hebrew characters
    has_hebrew = any('\u0590' <= char <= '\u05FF' for char in text)

    if not has_hebrew:
        return text

    try:
        from bidi.algorithm import get_display
        import arabic_reshaper

        # Reshape and apply BiDi algorithm for proper RTL display
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        return bidi_text
    except ImportError:
        # Fallback: simple reverse for Hebrew-only text
        return text[::-1]
    except Exception as e:
        print(f"[WARNING] BiDi processing failed: {e}")
        return text[::-1]


def clean_text_for_voiceover(text):
    """
    Clean text before sending to voiceover.
    Removes accidental word repetitions.
    """
    if not text:
        return text

    words = text.split()
    if len(words) < 2:
        return text

    cleaned_words = [words[0]]

    for i in range(1, len(words)):
        if words[i].lower() != words[i-1].lower():
            cleaned_words.append(words[i])

    result = ' '.join(cleaned_words)

    # Remove repeated 2-word phrases
    words = result.split()
    if len(words) >= 4:
        i = 0
        final_words = []
        while i < len(words):
            if i >= 2 and i + 1 < len(words):
                prev_phrase = ' '.join(words[i-2:i]).lower()
                curr_phrase = ' '.join(words[i:i+2]).lower()
                if prev_phrase == curr_phrase:
                    i += 2
                    continue
            final_words.append(words[i])
            i += 1
        result = ' '.join(final_words)

    return result


def escape_ffmpeg_path(path):
    """
    Escape path for FFmpeg filter usage on Windows.

    FFmpeg filter syntax requires special escaping:
    - Backslashes must be converted to forward slashes OR escaped
    - Colons must be escaped with backslash (C: -> C\\:)
    - Single quotes in path need escaping
    - Spaces and special chars need proper handling

    For Windows paths like: C:\\Users\\Name\\file.srt
    Result should be: C\\:/Users/Name/file.srt
    """
    if not path:
        return path

    path_str = str(path)

    # Convert all backslashes to forward slashes first
    path_str = path_str.replace('\\', '/')

    # Escape colons (important for Windows drive letters like C:)
    # Must use double backslash before colon for FFmpeg
    path_str = path_str.replace(':', '\\:')

    # Escape single quotes if any
    path_str = path_str.replace("'", "\\'")

    return path_str


def escape_ffmpeg_path_for_subtitles(path):
    """
    More aggressive escaping specifically for the subtitles filter.
    FFmpeg's subtitles filter is particularly sensitive on Windows.
    """
    if not path:
        return path

    path_str = str(path)

    # Use forward slashes
    path_str = path_str.replace('\\', '/')

    # For subtitles filter, we need to escape: \ ' :
    # The colon after drive letter needs escaping
    # First, handle drive letter specially
    if len(path_str) >= 2 and path_str[1] == ':':
        drive = path_str[0]
        rest = path_str[2:]
        path_str = f"{drive}\\:{rest}"

    # Escape any remaining colons
    # (but not the one we just escaped)
    parts = path_str.split('\\:')
    if len(parts) > 1:
        # Rejoin, escaping any other colons in the path
        first = parts[0]
        rest = '\\:'.join(parts[1:])
        rest = rest.replace(':', '\\:')
        path_str = f"{first}\\:{rest}"

    # Escape single quotes
    path_str = path_str.replace("'", "'\\''")

    return path_str

def parse_srt(srt_text):
    """
    Parses SRT format text into a list of dictionaries for the UI.
    Each entry contains index, time range, and content.
    """
    import re
    entries = []
    if not srt_text:
        return entries

    # Clean up common Gemini artifacts
    clean_text = srt_text.replace('```srt', '').replace('```', '').strip()
    
    # Split by double newlines to get individual subtitle blocks
    blocks = re.split(r'\n\s*\n', clean_text)
    
    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) >= 3:
            entries.append({
                "index": lines[0],
                "time": lines[1],
                "content": " ".join(lines[2:])
            })
            
    return entries

def create_preview_video(video_path, width=1280, fps=8, crf=20):
    """
    Creates a temporary preview video for Gemini OCR.
    """
    import subprocess
    from pathlib import Path
    
    output_path = Path(video_path).parent / f"preview_{Path(video_path).name}"
    
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vf', f'scale={width}:-2,fps={fps}',
        '-c:v', 'libx264', '-crf', str(crf),
        '-preset', 'veryfast', '-an',
        str(output_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return str(output_path)
