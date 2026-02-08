"""
Font Service - Downloads and manages fonts for subtitle rendering.
Ensures custom Google Fonts are available locally for FFmpeg's ASS filter.
"""
import os
import re
import requests
import zipfile
import io
from pathlib import Path
from typing import Optional, List

from utils.config import FONTS_DIR

# Known system fonts that don't need downloading
SYSTEM_FONTS = {
    "arial", "times new roman", "courier new", "verdana", "georgia",
    "tahoma", "trebuchet ms", "impact", "comic sans ms", "lucida console",
    "segoe ui", "calibri", "cambria", "consolas", "david", "miriam",
}


def is_system_font(font_name: str) -> bool:
    """Check if font is a common system font that doesn't need downloading."""
    return font_name.strip().lower() in SYSTEM_FONTS


def get_local_font_files(font_name: str) -> List[Path]:
    """
    Check if font files for the given font already exist in FONTS_DIR.
    Returns list of matching font file paths.
    """
    if not FONTS_DIR.exists():
        return []

    # Normalize font name for file matching
    # e.g., "Playpen Sans Hebrew" -> match files containing "PlaypenSansHebrew" or "Playpen Sans Hebrew"
    name_lower = font_name.lower().replace(" ", "")
    matches = []

    for font_file in FONTS_DIR.glob("*.ttf"):
        file_lower = font_file.stem.lower().replace(" ", "").replace("-", "")
        if name_lower in file_lower or file_lower.startswith(name_lower):
            matches.append(font_file)

    # Also check .otf files
    for font_file in FONTS_DIR.glob("*.otf"):
        file_lower = font_file.stem.lower().replace(" ", "").replace("-", "")
        if name_lower in file_lower or file_lower.startswith(name_lower):
            matches.append(font_file)

    return matches


def download_google_font(font_name: str) -> bool:
    """
    Download a font from Google Fonts API to the local FONTS_DIR.

    Uses the Google Fonts CSS API to get TTF download URLs,
    then downloads the font files.

    Args:
        font_name: Font family name (e.g., "Playpen Sans Hebrew")

    Returns:
        True if font was downloaded successfully
    """
    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    # Method 1: Try Google Fonts CSS API (returns TTF with appropriate User-Agent)
    family_param = font_name.replace(" ", "+")
    css_url = f"https://fonts.googleapis.com/css2?family={family_param}:wght@400;700"

    print(f"[FONT] Fetching CSS from: {css_url}")

    try:
        # Use a User-Agent that triggers TTF format
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(css_url, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"[FONT] CSS API returned {response.status_code}, trying zip download...")
            return _download_google_font_zip(font_name)

        css_content = response.text

        # Extract font file URLs from CSS
        # Pattern: url(https://fonts.gstatic.com/s/...)
        url_pattern = r'url\((https://fonts\.gstatic\.com/[^)]+)\)'
        font_urls = re.findall(url_pattern, css_content)

        if not font_urls:
            print(f"[FONT] No font URLs found in CSS, trying zip download...")
            return _download_google_font_zip(font_name)

        # Also extract weight info to name files properly
        # Pattern: font-weight: 400; ... url(...)
        block_pattern = r'font-weight:\s*(\d+);[^}]*?url\((https://fonts\.gstatic\.com/[^)]+)\)'
        blocks = re.findall(block_pattern, css_content, re.DOTALL)

        downloaded = 0
        safe_name = font_name.replace(" ", "")

        if blocks:
            for weight, url in blocks:
                weight_name = _weight_to_name(int(weight))
                ext = "ttf" if ".ttf" in url else "woff2"
                filename = f"{safe_name}-{weight_name}.{ext}"
                filepath = FONTS_DIR / filename

                if filepath.exists():
                    print(f"[FONT] Already exists: {filename}")
                    downloaded += 1
                    continue

                if _download_file(url, filepath, headers):
                    downloaded += 1
        else:
            # Fallback: download all URLs with incremental naming
            for i, url in enumerate(font_urls):
                ext = "ttf" if ".ttf" in url else "woff2"
                filename = f"{safe_name}-{i}.{ext}"
                filepath = FONTS_DIR / filename

                if filepath.exists():
                    downloaded += 1
                    continue

                if _download_file(url, filepath, headers):
                    downloaded += 1

        if downloaded > 0:
            print(f"[FONT] Downloaded {downloaded} font files for '{font_name}'")
            return True

        print(f"[FONT] No files downloaded from CSS, trying zip...")
        return _download_google_font_zip(font_name)

    except Exception as e:
        print(f"[FONT] CSS method failed: {e}, trying zip download...")
        return _download_google_font_zip(font_name)


def _download_google_font_zip(font_name: str) -> bool:
    """
    Fallback: Download font as ZIP from Google Fonts download endpoint.
    URL format: https://fonts.google.com/download?family=Font+Name
    """
    try:
        family_param = font_name.replace(" ", "+")
        zip_url = f"https://fonts.google.com/download?family={family_param}"

        print(f"[FONT] Downloading ZIP from: {zip_url}")

        response = requests.get(zip_url, timeout=30)

        if response.status_code != 200:
            print(f"[FONT] ZIP download failed with status {response.status_code}")
            return False

        # Extract TTF files from ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            downloaded = 0
            for name in zf.namelist():
                if name.lower().endswith(('.ttf', '.otf')):
                    # Extract just the filename, flatten directory structure
                    basename = Path(name).name
                    target = FONTS_DIR / basename

                    if target.exists():
                        print(f"[FONT] Already exists: {basename}")
                        downloaded += 1
                        continue

                    with zf.open(name) as source:
                        target.write_bytes(source.read())
                    print(f"[FONT] Extracted: {basename}")
                    downloaded += 1

            if downloaded > 0:
                print(f"[FONT] Extracted {downloaded} font files from ZIP")
                return True

        print(f"[FONT] No TTF/OTF files found in ZIP")
        return False

    except Exception as e:
        print(f"[FONT] ZIP download failed: {e}")
        return False


def _download_file(url: str, filepath: Path, headers: dict = None) -> bool:
    """Download a single file."""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.content) > 100:
            filepath.write_bytes(response.content)
            size_kb = len(response.content) / 1024
            print(f"[FONT] Downloaded: {filepath.name} ({size_kb:.1f} KB)")
            return True
        return False
    except Exception as e:
        print(f"[FONT] Download failed for {filepath.name}: {e}")
        return False


def _weight_to_name(weight: int) -> str:
    """Convert numeric font weight to name."""
    weight_names = {
        100: "Thin",
        200: "ExtraLight",
        300: "Light",
        400: "Regular",
        500: "Medium",
        600: "SemiBold",
        700: "Bold",
        800: "ExtraBold",
        900: "Black",
    }
    return weight_names.get(weight, f"W{weight}")


def ensure_font_available(font_name: str) -> str:
    """
    Ensure the requested font is available for FFmpeg rendering.

    1. If it's a system font, return as-is
    2. If font files exist locally, return as-is
    3. Try to download from Google Fonts
    4. If download fails, log warning and return as-is (FFmpeg will use fallback)

    Args:
        font_name: The font family name

    Returns:
        The font name to use (same as input, or fallback if download failed)
    """
    if not font_name or not font_name.strip():
        print(f"[FONT] No font name provided, using Arial")
        return "Arial"

    font_name = font_name.strip()

    # System fonts don't need downloading
    if is_system_font(font_name):
        print(f"[FONT] '{font_name}' is a system font, no download needed")
        return font_name

    # Check if already available locally
    local_files = get_local_font_files(font_name)
    if local_files:
        print(f"[FONT] '{font_name}' found locally: {[f.name for f in local_files]}")
        return font_name

    # Try to download
    print(f"[FONT] '{font_name}' not found locally, attempting download from Google Fonts...")
    success = download_google_font(font_name)

    if success:
        local_files = get_local_font_files(font_name)
        print(f"[FONT] '{font_name}' downloaded successfully: {[f.name for f in local_files]}")
    else:
        print(f"[FONT] WARNING: Could not download '{font_name}'. FFmpeg will use system fallback.")

    return font_name


def get_fonts_dir_path() -> str:
    """Return the fonts directory path as a string."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    return str(FONTS_DIR)
