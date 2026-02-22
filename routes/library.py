"""
User Music Library routes — CRUD for personal 3-slot music storage.
"""
import json
import shutil
import uuid
import re
import hashlib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from utils.config import BASE_DIR, MUSIC_DIR, SERVER_BASE_URL

router = APIRouter()

# Paths
USER_LIBRARY_FILE = BASE_DIR / "user_library.json"
USER_LIBRARY_DIR = MUSIC_DIR / "user_library"
USER_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Persistence Helpers
# =============================================================================

def load_user_library() -> dict:
    """Load user library from JSON file."""
    default_library = {
        "slots": [
            {"id": 0, "filename": None, "filepath": None, "displayName": None},
            {"id": 1, "filename": None, "filepath": None, "displayName": None},
            {"id": 2, "filename": None, "filepath": None, "displayName": None}
        ]
    }

    if USER_LIBRARY_FILE.exists():
        try:
            with open(USER_LIBRARY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "slots" in data and len(data["slots"]) == 3:
                    return data
        except Exception as e:
            print(f"[LIBRARY] Error loading library: {e}")

    return default_library


def save_user_library(library: dict):
    """Save user library to JSON file."""
    try:
        with open(USER_LIBRARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(library, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LIBRARY] Error saving library: {e}")


# =============================================================================
# Request Models
# =============================================================================

class LibrarySlotUpdate(BaseModel):
    slot_id: int
    filename: Optional[str] = None
    displayName: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/user-library")
async def get_user_library():
    """Get the user's 3-slot music library."""
    library = load_user_library()

    for slot in library["slots"]:
        if slot["filepath"]:
            filepath = Path(slot["filepath"])
            if filepath.exists():
                slot["url"] = f"{SERVER_BASE_URL}/assets/music/user_library/{filepath.name}"
            else:
                slot["filename"] = None
                slot["filepath"] = None
                slot["displayName"] = None
                slot["url"] = None
        else:
            slot["url"] = None

    return {"status": "success", "library": library}


@router.put("/user-library/{slot_id}")
async def update_library_slot(slot_id: int, update: LibrarySlotUpdate):
    """Update metadata for a library slot (e.g., displayName)."""
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        library = load_user_library()
        slot = library["slots"][slot_id]

        if not slot.get("filepath"):
            raise HTTPException(status_code=400, detail="Slot is empty. Upload a file first.")

        if update.displayName:
            slot["displayName"] = update.displayName[:30]

        save_user_library(library)

        url = None
        if slot.get("filepath"):
            filepath = Path(slot["filepath"])
            if filepath.exists():
                url = f"{SERVER_BASE_URL}/assets/music/user_library/{filepath.name}"

        return {
            "status": "success",
            "slot": {"id": slot_id, "filename": slot.get("filename"), "displayName": slot.get("displayName"), "url": url}
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-library/save-from-library/{slot_id}")
async def save_from_main_library(slot_id: int, filename: str = Form(...)):
    """Copy a music file from the main library to a user library slot."""
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        source_path = MUSIC_DIR / filename
        if not source_path.exists():
            raise HTTPException(status_code=404, detail=f"Music file not found: {filename}")

        file_ext = source_path.suffix.lower()
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = f"slot{slot_id}_{unique_id}{file_ext}"
        dest_path = USER_LIBRARY_DIR / safe_filename

        library = load_user_library()

        old_filepath = library["slots"][slot_id].get("filepath")
        if old_filepath:
            old_path = Path(old_filepath)
            if old_path.exists():
                try:
                    old_path.unlink()
                except Exception:
                    pass

        shutil.copy2(source_path, dest_path)

        display_name = source_path.stem[:30]
        library["slots"][slot_id] = {
            "id": slot_id, "filename": safe_filename, "filepath": str(dest_path),
            "displayName": display_name, "originalName": filename
        }
        save_user_library(library)

        return {
            "status": "success",
            "slot": {"id": slot_id, "filename": safe_filename, "displayName": display_name,
                     "url": f"{SERVER_BASE_URL}/assets/music/user_library/{safe_filename}"}
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-library/upload/{slot_id}")
async def upload_to_library_slot(slot_id: int, file: UploadFile = File(...)):
    """Upload an audio file to a specific library slot."""
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ['.mp3', '.wav', '.ogg', '.m4a', '.aac']:
            raise HTTPException(status_code=400, detail="Invalid audio format")

        unique_id = str(uuid.uuid4())[:8]
        safe_filename = f"slot{slot_id}_{unique_id}{file_ext}"
        filepath = USER_LIBRARY_DIR / safe_filename

        library = load_user_library()

        old_filepath = library["slots"][slot_id].get("filepath")
        if old_filepath:
            old_path = Path(old_filepath)
            if old_path.exists():
                try:
                    old_path.unlink()
                except Exception:
                    pass

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        original_name = file.filename
        display_name = Path(original_name).stem[:30]

        library["slots"][slot_id] = {
            "id": slot_id, "filename": safe_filename, "filepath": str(filepath),
            "displayName": display_name, "originalName": original_name
        }
        save_user_library(library)

        return {
            "status": "success",
            "slot": {"id": slot_id, "filename": safe_filename, "displayName": display_name,
                     "url": f"{SERVER_BASE_URL}/assets/music/user_library/{safe_filename}"}
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user-library/{slot_id}")
async def clear_library_slot(slot_id: int):
    """Clear a specific library slot."""
    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id")

    try:
        library = load_user_library()

        filepath = library["slots"][slot_id].get("filepath")
        if filepath:
            path = Path(filepath)
            if path.exists():
                path.unlink()

        library["slots"][slot_id] = {"id": slot_id, "filename": None, "filepath": None, "displayName": None}
        save_user_library(library)

        return {"status": "success", "message": f"Slot {slot_id} cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-library/save-from-url/{slot_id}")
async def save_from_url_to_library(
    slot_id: int,
    url: str = Form(...),
    displayName: str = Form("")
):
    """Download audio from YouTube URL and save directly to a library slot."""
    import yt_dlp

    if slot_id < 0 or slot_id > 2:
        raise HTTPException(status_code=400, detail="Invalid slot_id. Must be 0, 1, or 2.")

    try:
        youtube_regex = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+(?:&\S*)?)'
        match = re.search(youtube_regex, url)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        clean_url = match.group(0)
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:8]

        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"slot{slot_id}_{url_hash}_{unique_id}"
        output_template = str(USER_LIBRARY_DIR / output_filename)

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'quiet': True
        }

        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            video_title = info.get('title', 'YouTube Audio')[:30]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([clean_url])

        final_filename = f"{output_filename}.mp3"
        final_path = USER_LIBRARY_DIR / final_filename

        if not final_path.exists():
            raise HTTPException(status_code=500, detail="Download failed - file not created")

        library = load_user_library()

        old_filepath = library["slots"][slot_id].get("filepath")
        if old_filepath:
            old_path = Path(old_filepath)
            if old_path.exists():
                try:
                    old_path.unlink()
                except Exception:
                    pass

        final_display_name = displayName[:30] if displayName else video_title

        library["slots"][slot_id] = {
            "id": slot_id, "filename": final_filename, "filepath": str(final_path),
            "displayName": final_display_name, "originalName": video_title, "sourceUrl": clean_url
        }
        save_user_library(library)

        return {
            "status": "success",
            "slot": {"id": slot_id, "filename": final_filename, "displayName": final_display_name,
                     "url": f"{SERVER_BASE_URL}/assets/music/user_library/{final_filename}"}
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
