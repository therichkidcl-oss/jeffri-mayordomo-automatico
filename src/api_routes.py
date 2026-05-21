"""Endpoints REST de la Batcave."""
import base64
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
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

    return router
