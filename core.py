"""
Shared application state and utilities.
Imported by route modules to access the WebSocket manager, pending tasks, and caches.
"""
from typing import Dict, Set, Optional
from pathlib import Path

from fastapi import WebSocket


# =============================================================================
# WebSocket Connection Manager
# =============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.progress_data: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, file_id: str):
        await websocket.accept()
        if file_id not in self.active_connections:
            self.active_connections[file_id] = set()
        self.active_connections[file_id].add(websocket)

        if file_id in self.progress_data:
            await websocket.send_json(self.progress_data[file_id])

    def disconnect(self, websocket: WebSocket, file_id: str):
        if file_id in self.active_connections:
            self.active_connections[file_id].discard(websocket)
            if not self.active_connections[file_id]:
                del self.active_connections[file_id]

    async def send_progress(self, file_id: str, progress: int, status: str, message: str = "", extra_data: dict = None):
        data = {"status": status, "progress": progress, "message": message}
        if extra_data:
            data.update(extra_data)

        self.progress_data[file_id] = data

        if file_id in self.active_connections:
            disconnected = set()
            for connection in list(self.active_connections[file_id]):
                try:
                    await connection.send_json(data)
                except Exception:
                    disconnected.add(connection)

            for ws in disconnected:
                self.active_connections[file_id].discard(ws)

            # Clean up empty connection sets to stop future attempts
            if file_id in self.active_connections and not self.active_connections[file_id]:
                del self.active_connections[file_id]

    def cleanup(self, file_id: str):
        if file_id in self.progress_data:
            del self.progress_data[file_id]
        if file_id in self.active_connections:
            del self.active_connections[file_id]


# Singleton instances — imported by all route modules
manager = ConnectionManager()

# Storage for paused tasks waiting for subtitle review confirmation
pending_tasks: Dict[str, dict] = {}

# Cache for storing marketing data per video (to avoid re-transcribing)
marketing_cache: Dict[str, dict] = {}

# In-memory storage for AI thumbnail original URLs
ai_thumbnail_original_urls: Dict[str, str] = {}

# Background task status trackers
youtube_upload_status: Dict[str, dict] = {}
facebook_upload_status: Dict[str, dict] = {}
effects_render_status: Dict[str, dict] = {}


# =============================================================================
# Shared Helpers
# =============================================================================

def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


def url_to_local_path(url_or_path: str) -> str:
    """
    Convert a URL like http://localhost:8000/outputs/file.mp4
    or /outputs/shorts/file.mp4 to a local file path.
    Returns the original string if it's already a local path.
    """
    import re
    from utils.config import OUTPUTS_DIR

    if not url_or_path:
        return ""
    s = url_or_path.strip()
    # Strip http://localhost:PORT/outputs/ prefix
    m = re.match(r'https?://[^/]+/outputs/(.+)', s)
    if m:
        return str(OUTPUTS_DIR / m.group(1))
    # Strip bare /outputs/ prefix
    if s.startswith("/outputs/"):
        return str(OUTPUTS_DIR / s[len("/outputs/"):])
    return s
