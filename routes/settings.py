"""
Settings routes — frontend settings sync and health check.
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class UpdateSettingsRequest(BaseModel):
    font: Optional[str] = None
    fontUrl: Optional[str] = None
    fontColor: Optional[str] = None
    fontSize: Optional[int] = None
    subtitleText: Optional[str] = None
    timestamp: Optional[int] = None


@router.post("/update-settings")
async def update_settings(request: UpdateSettingsRequest):
    """Receive font/style settings from frontend."""
    settings_dict = request.model_dump(exclude_none=True)
    print(f"[SETTINGS] Received: {settings_dict}")
    return {"status": "success", "message": "Settings received", "received": settings_dict}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}
