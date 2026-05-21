"""Broadcast de eventos del transcript watcher hacia clientes web."""
import asyncio
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

from src.config import WEB_AUTH_TOKEN

logger = logging.getLogger(__name__)


class EventBroadcaster:
    def __init__(self):
        self.clients: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def add(self, ws: WebSocket):
        async with self.lock:
            self.clients.add(ws)

    async def remove(self, ws: WebSocket):
        async with self.lock:
            self.clients.discard(ws)

    async def broadcast(self, payload: dict):
        async with self.lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                await self.remove(ws)


broadcaster = EventBroadcaster()


async def handle_events_ws(websocket: WebSocket):
    if WEB_AUTH_TOKEN:
        token = websocket.query_params.get("token", "")
        if token != WEB_AUTH_TOKEN:
            await websocket.close(code=4001)
            return
    await websocket.accept()
    await broadcaster.add(websocket)
    logger.info("Cliente conectado a /ws/events")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Cliente desconectado de /ws/events")
    except Exception as e:
        logger.exception(f"Error en ws_events: {e}")
    finally:
        await broadcaster.remove(websocket)
