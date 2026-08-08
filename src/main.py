"""Entrypoint de Jeffri: corre Telegram + Voz en UN proceso.

Comparten el mismo ClaudeController y send_lock (via el `state` global de bot.py)
para no pisarse al escribirle a Claude. La voz es opcional: solo arranca si
VOICE_ENABLED=true y hay DEEPSEEK_API_KEY.

Uso: `.venv/Scripts/python.exe -m src.main`
"""
import asyncio
import json
import logging
import os
import time

from src.bot import build_app, state
from src.config import (
    CLAUDE_PROJECTS_DIR,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    PIPER_VOICE,
    VOICE_ENABLED,
    VOICE_HOTKEY,
)

logger = logging.getLogger(__name__)


async def _read_claude_response(idle_timeout: float = 5.0, max_wait: float = 240.0) -> str | None:
    """Tras un dispatch, lee la salida de Claude del .jsonl de la sesion activa:
    acumula el texto nuevo del asistente hasta que pasan `idle_timeout` segundos
    sin novedades (Claude termino) o se agota `max_wait`. Devuelve el texto o None.
    """
    from src.formatters import TextMessage, format_event
    from src.session_detector import detect_active_session

    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active is None:
        return None
    try:
        pos = active.stat().st_size  # arrancar desde el final actual
    except OSError:
        return None

    collected: list[str] = []
    last_new = time.monotonic()
    deadline = time.monotonic() + max_wait

    while time.monotonic() < deadline:
        await asyncio.sleep(1.0)
        try:
            size = active.stat().st_size
            if size > pos:
                with open(active, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = size
                for line in chunk.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    for m in format_event(event):
                        if isinstance(m, TextMessage):
                            collected.append(m.text)
                            last_new = time.monotonic()
        except OSError:
            pass
        if collected and (time.monotonic() - last_new) > idle_timeout:
            break

    return "\n".join(collected).strip() or None


async def run_voice() -> None:
    # Todo aislado en try/except: si la voz falla al arrancar (mic, Piper, etc.)
    # NO debe tumbar el proceso — Telegram sigue funcionando igual.
    try:
        from src.stt import transcribe_bytes
        from src.voice.app import VoiceLoop
        from src.voice.audio_io import record_while_held
        from src.voice.brain import Brain
        from src.voice.deepseek_client import DeepSeekClient
        from src.voice.search import web_search
        from src.voice.tts import PiperTTS

        voice_path = os.path.join("voice_models", f"{PIPER_VOICE}.onnx")
        tts = PiperTTS(voice_path)
        client = DeepSeekClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
        brain = Brain(client, search_fn=web_search)

        loop = VoiceLoop(
            transcriber=transcribe_bytes,
            brain=brain,
            tts_speak=tts.speak,
            controller=state.controller,   # COMPARTIDO con Telegram
            send_lock=state.send_lock,     # COMPARTIDO con Telegram
            get_claude_response=_read_claude_response,
            record_fn=record_while_held,
            hotkey=VOICE_HOTKEY,
        )
        await loop.run()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Jeffri Voz fallo al arrancar; Telegram sigue funcionando")


async def amain() -> None:
    app = build_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("Telegram polling iniciado.")

    voice_task = None
    if VOICE_ENABLED and DEEPSEEK_API_KEY:
        logger.info("Jeffri Voz habilitado (manten F9 para hablar).")
        voice_task = asyncio.create_task(run_voice())
    else:
        logger.info("Jeffri Voz deshabilitado (VOICE_ENABLED o DEEPSEEK_API_KEY faltan).")

    try:
        await asyncio.Event().wait()  # corre para siempre
    finally:
        if voice_task is not None:
            voice_task.cancel()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(amain())
