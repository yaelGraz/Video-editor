"""
Configuration and constants for Video AI Studio.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fix Windows console encoding for Hebrew/Unicode output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ["PYTHONIOENCODING"] = "utf-8"

# =============================================================================
# Directory Configuration
# =============================================================================
BASE_DIR = Path(__file__).parent.parent.absolute()
INPUTS_DIR = BASE_DIR / "inputs"
OUTPUTS_DIR = BASE_DIR / "outputs"
MUSIC_DIR = BASE_DIR / "assets" / "music"
MUSIC_TEMP_DIR = MUSIC_DIR / "temp"
SHORTS_DIR = OUTPUTS_DIR / "shorts"
FONTS_DIR = BASE_DIR / "assets" / "fonts"

# Create directories if they don't exist
for folder in [INPUTS_DIR, OUTPUTS_DIR, MUSIC_DIR, MUSIC_TEMP_DIR, SHORTS_DIR, FONTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# =============================================================================
# API Keys
# =============================================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY") or os.getenv("LEVENLABS_API_KEY")

# =============================================================================
# ElevenLabs Configuration
# =============================================================================
ELEVENLABS_VOICE_ID = os.getenv("DEFAULT_VOICE_ID", "1sl7XMHkUEezwYy9NbJU")
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# Emotion presets for ElevenLabs voice settings
ELEVENLABS_EMOTION_SETTINGS = {
    'emotional': {
        'stability': 0.3,
        'similarity_boost': 0.75,
        'style': 0.45,
        'use_speaker_boost': True
    },
    'pastoral': {
        'stability': 0.5,
        'similarity_boost': 0.75,
        'style': 0.0,
        'use_speaker_boost': True
    },
    'happy': {
        'stability': 0.4,
        'similarity_boost': 0.75,
        'style': 0.2,
        'use_speaker_boost': True
    },
    'neutral': {
        'stability': 0.5,
        'similarity_boost': 0.75,
        'style': 0.0,
        'use_speaker_boost': False
    }
}

# =============================================================================
# Edge-TTS Configuration
# =============================================================================
EDGE_TTS_VOICE = "he-IL-AvriNeural"
EDGE_TTS_RATE = "-5%"

# =============================================================================
# Video Processing Configuration
# =============================================================================
DEFAULT_VIDEO_WIDTH = 1920
DEFAULT_VIDEO_HEIGHT = 1080

# Music style keywords for auto-selection
MUSIC_STYLE_KEYWORDS = {
    'calm': ['calm', 'peaceful', 'ambient', 'soft', 'quiet', 'chill', 'relaxing', 'smooth'],
    'dramatic': ['dramatic', 'epic', 'cinematic', 'intense', 'powerful', 'orchestral'],
    'uplifting': ['uplifting', 'inspiring', 'happy', 'upbeat', 'positive', 'bright', 'energetic'],
    'spiritual': ['spiritual', 'emotional', 'gentle', 'piano', 'nature', 'meditation']
}

# =============================================================================
# Tesseract OCR Configuration
# =============================================================================
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# =============================================================================
# Subtitle Configuration
# =============================================================================
SRT_MIN_GAP_SECONDS = 0.3  # Minimum gap between subtitles
SRT_SIMILARITY_THRESHOLD = 0.85  # Threshold for merging similar subtitles
