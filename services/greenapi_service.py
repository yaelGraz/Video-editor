"""
Green API client for WhatsApp integration.
Sends/receives messages and media via the Green API REST interface.
"""
import os
import uuid
import requests
from pathlib import Path
from utils.config import GREEN_API_INSTANCE_ID, GREEN_API_TOKEN, INPUTS_DIR


def _api_url(method: str) -> str:
    """Build Green API endpoint URL."""
    return f"https://api.greenapi.com/waInstance{GREEN_API_INSTANCE_ID}/{method}/{GREEN_API_TOKEN}"


def is_configured() -> bool:
    """Check if Green API credentials are set."""
    return bool(GREEN_API_INSTANCE_ID) and bool(GREEN_API_TOKEN)


def check_connection() -> dict:
    """Ping Green API to verify the instance is active."""
    if not is_configured():
        return {"ok": False, "error": "Green API credentials not configured"}
    try:
        resp = requests.get(_api_url("getStateInstance"), timeout=10, verify=False)
        data = resp.json()
        return {"ok": data.get("stateInstance") == "authorized", "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_text_message(chat_id: str, text: str) -> dict:
    """
    Send a text message to a WhatsApp chat.
    chat_id: e.g. "972501234567@c.us"
    """
    if not is_configured():
        print("[GreenAPI] Not configured, skipping send")
        return {"error": "not configured"}

    try:
        resp = requests.post(
            _api_url("sendMessage"),
            json={"chatId": chat_id, "message": text},
            timeout=30,
            verify=False,
        )
        result = resp.json()
        print(f"[GreenAPI] sendMessage -> {result}")
        return result
    except Exception as e:
        print(f"[GreenAPI] sendMessage error: {e}")
        return {"error": str(e)}


def send_file_by_url(chat_id: str, file_url: str, filename: str, caption: str = "") -> dict:
    """
    Send a file (video/audio/image) to a WhatsApp chat by URL.
    The file_url must be publicly accessible (e.g. via ngrok).
    """
    if not is_configured():
        return {"error": "not configured"}

    try:
        payload = {
            "chatId": chat_id,
            "urlFile": file_url,
            "fileName": filename,
        }
        if caption:
            payload["caption"] = caption

        resp = requests.post(
            _api_url("sendFileByUrl"),
            json=payload,
            timeout=60,
            verify=False,
        )
        result = resp.json()
        print(f"[GreenAPI] sendFileByUrl -> {result}")
        return result
    except Exception as e:
        print(f"[GreenAPI] sendFileByUrl error: {e}")
        return {"error": str(e)}


def download_media(download_url: str) -> str | None:
    """
    Download incoming media (video) from Green API CDN to inputs/ folder.
    Returns the local file path, or None on failure.
    """
    if not download_url:
        return None

    try:
        file_id = uuid.uuid4().hex[:8]
        local_path = INPUTS_DIR / f"{file_id}.mp4"

        print(f"[GreenAPI] Downloading media: {download_url[:80]}...")
        resp = requests.get(download_url, timeout=120, verify=False, stream=True)
        resp.raise_for_status()

        with open(str(local_path), "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size = local_path.stat().st_size
        print(f"[GreenAPI] Downloaded {size} bytes -> {local_path}")
        return str(local_path)

    except Exception as e:
        print(f"[GreenAPI] download_media error: {e}")
        return None
