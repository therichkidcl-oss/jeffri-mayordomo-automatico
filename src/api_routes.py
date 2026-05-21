"""Endpoints REST de la Batcave."""
import base64
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import CLAUDE_PROJECTS_DIR
from src.session_detector import list_projects

logger = logging.getLogger(__name__)


class SwitchRequest(BaseModel):
    display_name: str


def create_router(bot_state) -> APIRouter:
    router = APIRouter(prefix="/api")

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

    return router
