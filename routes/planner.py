"""
Video Planner routes — AI script creation and file extraction.
"""
import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from services.video_service import video_planner_chat
from services.text_service import extract_text_from_file
from utils.config import INPUTS_DIR

router = APIRouter()


class VideoPlannerChatRequest(BaseModel):
    user_input: str
    history: list = []
    current_script: str = ""


@router.post("/video-planner/chat")
async def video_planner_chat_endpoint(request: VideoPlannerChatRequest):
    """Chat with AI to create and refine a video script."""
    try:
        history = request.history[-10:] if request.history else []

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: video_planner_chat(
                user_message=request.user_input,
                conversation_history=history,
                current_script=request.current_script,
                file_context=""
            )
        )

        if result["success"]:
            return {"status": "success", "ai_message": result["ai_message"], "script": result["script"]}
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Video planner chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/video-planner/extract-file")
async def video_planner_extract_file(file: UploadFile = File(...)):
    """Extract text from uploaded file for use as context."""
    try:
        file_id = str(uuid.uuid4())[:8]
        suffix = Path(file.filename).suffix.lower()

        if suffix not in ['.txt', '.docx']:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {suffix}")

        temp_path = INPUTS_DIR / f"{file_id}_extract{suffix}"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        extracted_text = extract_text_from_file(str(temp_path))

        try:
            temp_path.unlink()
        except Exception:
            pass

        return {
            "status": "success", "text": extracted_text,
            "filename": file.filename, "char_count": len(extracted_text)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
