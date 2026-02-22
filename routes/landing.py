"""
Landing Page Builder routes — AI-powered HTML landing page generation.
"""
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.landing_service import landing_page_chat

router = APIRouter()


class LandingPageChatRequest(BaseModel):
    user_input: str
    history: list = []
    current_html: str = ""


@router.post("/landing-page/chat")
async def landing_page_chat_endpoint(request: LandingPageChatRequest):
    """Chat with AI to create and refine a landing page."""
    try:
        history = request.history[-10:] if request.history else []

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: landing_page_chat(
                user_message=request.user_input,
                conversation_history=history,
                current_html=request.current_html
            )
        )

        if result["success"]:
            return {
                "status": "success",
                "ai_message": result["ai_message"],
                "html": result["html"]
            }
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Landing page chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
