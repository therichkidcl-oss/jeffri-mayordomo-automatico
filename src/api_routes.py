"""Endpoints REST de la Batcave."""
import base64
import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from src.config import CLAUDE_PROJECTS_DIR, WEB_AUTH_TOKEN
from src.session_detector import list_projects

logger = logging.getLogger(__name__)


async def require_auth(x_auth_token: str = Header(default="")):
    if WEB_AUTH_TOKEN and x_auth_token != WEB_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="auth required")


class SwitchRequest(BaseModel):
    display_name: str


def create_router(bot_state) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

    @router.get("/projects")
    async def get_projects():
        projects = list_projects(CLAUDE_PROJECTS_DIR)
        return [
            {
                "folder_name": p.folder_name,
                "display_name": p.display_name,
                "session_count": p.session_count,
                "last_modified": p.last_modified.isoformat(),
            }
            for p in projects
        ]

    @router.post("/switch")
    async def switch_project(req: SwitchRequest):
        try:
            async with bot_state.send_lock:
                await bot_state.controller.switch_session(req.display_name)
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/capture")
    async def capture():
        try:
            png_bytes = await bot_state.controller.capture()
            return {"ok": True, "png_b64": base64.b64encode(png_bytes).decode()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/stop")
    async def stop():
        try:
            async with bot_state.send_lock:
                await bot_state.controller.interrupt()
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/upload-image")
    async def upload_image(
        image: UploadFile = File(...),
        caption: str = Form(default=""),
    ):
        try:
            data = await image.read()
            caption_clean = caption.strip() or None
            async with bot_state.send_lock:
                await bot_state.controller.send_image(data, caption=caption_clean)
            return {"ok": True, "size": len(data), "caption": caption_clean}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/send")
    async def send_unified(
        text: str = Form(default=""),
        images: List[UploadFile] = File(default=[]),
    ):
        text_clean = text.strip()
        try:
            if images:
                data_list = [await img.read() for img in images]
                caption_clean = text_clean or None
                async with bot_state.send_lock:
                    await bot_state.controller.send_images(data_list, caption=caption_clean)
                return {"ok": True, "image_count": len(images), "caption": caption_clean}
            elif text_clean:
                async with bot_state.send_lock:
                    await bot_state.controller.send(text_clean)
                return {"ok": True, "text": text_clean}
            else:
                raise HTTPException(status_code=400, detail="empty payload")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
