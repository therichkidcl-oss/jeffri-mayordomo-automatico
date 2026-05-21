"""Servidor FastAPI que sirve la UI Batcave."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def create_app(state) -> FastAPI:
    app = FastAPI(title="Jeffri Batcave")
    app.state.bot_state = state

    static_dir = Path(__file__).resolve().parent.parent / "static"
    static_dir.mkdir(exist_ok=True)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return HTMLResponse("<h1>Batcave under construction</h1>")
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/api/state")
    async def get_state():
        return {
            "paused": state.paused,
            "enhancer_enabled": state.enhancer_enabled,
            "groq_available": state.groq is not None,
        }

    from fastapi import WebSocket
    from src.ws_chat import handle_chat_ws

    @app.websocket("/ws/chat")
    async def ws_chat_endpoint(websocket: WebSocket):
        await handle_chat_ws(websocket, state)

    from src.ws_events import handle_events_ws

    @app.websocket("/ws/events")
    async def ws_events_endpoint(websocket: WebSocket):
        await handle_events_ws(websocket)

    from src.api_routes import create_router
    app.include_router(create_router(state))

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"FastAPI app creada, static dir: {static_dir}")
    return app
