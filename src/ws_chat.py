"""WebSocket handler para el chat de la Batcave."""
import asyncio
import json
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from src.config import WEB_AUTH_TOKEN
from src.security import is_destructive

logger = logging.getLogger(__name__)


async def handle_chat_ws(websocket: WebSocket, bot_state):
    await websocket.accept()
    logger.info("Cliente conectado a /ws/chat")

    if WEB_AUTH_TOKEN:
        try:
            auth = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
            if auth.get("token") != WEB_AUTH_TOKEN:
                await websocket.send_json({"type": "auth_failed"})
                await websocket.close(code=4001)
                return
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.close(code=4001)
            return

    await websocket.send_json({"type": "welcome", "message": f"Bienvenido, {bot_state.address()}"})

    try:
        while True:
            data = await websocket.receive_json()
            await _route_message(data, websocket, bot_state)
    except WebSocketDisconnect:
        logger.info("Cliente desconectado de /ws/chat")
    except Exception as e:
        logger.exception(f"Error en ws_chat: {e}")


async def _route_message(data: dict, websocket: WebSocket, bot_state):
    msg_type = data.get("type")
    if msg_type == "user_text":
        await _handle_user_text(data, websocket, bot_state)
    elif msg_type == "confirm_response":
        await _handle_confirm(data, websocket, bot_state)
    else:
        await websocket.send_json({"type": "error", "message": f"Tipo desconocido: {msg_type}"})


async def _handle_user_text(data: dict, websocket: WebSocket, bot_state):
    text = (data.get("text") or "").strip()
    if not text:
        return

    if is_destructive(text):
        token = uuid.uuid4().hex[:8]
        bot_state.pending_destructive[token] = text
        await websocket.send_json({
            "type": "confirm_destructive", "token": token, "text": text,
        })
        return

    if bot_state.enhancer is None or not bot_state.enhancer_enabled:
        await _do_send_to_claude(text, websocket, bot_state)
        return

    try:
        enhanced = await bot_state.enhancer.enhance(text, source="texto", user_title=bot_state.address())
    except Exception as e:
        logger.warning(f"DeepSeek fallo: {e}, mando original")
        await _do_send_to_claude(text, websocket, bot_state)
        return

    if enhanced.strip() == text.strip():
        await _do_send_to_claude(text, websocket, bot_state)
        return

    token = uuid.uuid4().hex[:8]
    bot_state.pending_enhanced[token] = {"original": text, "enhanced": enhanced}
    await websocket.send_json({
        "type": "confirm_enhanced", "token": token,
        "original": text, "enhanced": enhanced,
    })


async def _handle_confirm(data: dict, websocket: WebSocket, bot_state):
    token = data.get("token", "")
    choice = data.get("choice", "")

    if not bot_state.claim_token(f"web:{token}"):
        return

    payload = bot_state.pending_enhanced.pop(token, None)
    if payload:
        if choice == "send_enhanced":
            await _do_send_to_claude(payload["enhanced"], websocket, bot_state)
        elif choice == "send_original":
            await _do_send_to_claude(payload["original"], websocket, bot_state)
        else:
            await websocket.send_json({"type": "cancelled"})
        return

    text = bot_state.pending_destructive.pop(token, None)
    if text and choice == "send_enhanced":
        await _do_send_to_claude(text, websocket, bot_state)
    else:
        await websocket.send_json({"type": "cancelled"})


async def _do_send_to_claude(text: str, websocket: WebSocket, bot_state):
    try:
        async with bot_state.send_lock:
            await bot_state.controller.send(text)
        await websocket.send_json({"type": "sent", "text": text})
    except Exception as e:
        logger.exception("Error enviando a Claude desde web")
        await websocket.send_json({"type": "error", "message": str(e)})
