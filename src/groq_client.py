"""Cliente Groq con rotación de API keys.

Maneja:
- Mejora de prompts (chat completions con llama)
- Transcripción de audio (Whisper)

Si una key falla por rate limit (429) o auth (401), pasa a la siguiente
automáticamente. Si todas fallan, levanta GroqAllKeysFailed.
"""
import asyncio
import logging
from itertools import cycle
from typing import Iterator

import httpx

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CHAT_MODEL = "llama-3.3-70b-versatile"
WHISPER_MODEL = "whisper-large-v3-turbo"

ENHANCE_SYSTEM_PROMPT = (
    "Eres un asistente que reformula mensajes para que sean instrucciones más claras y "
    "específicas para Claude (un asistente de programación). Recibirás un mensaje en "
    "español del usuario. Tu tarea:\n"
    "- Mantén la intención original\n"
    "- Aclara ambigüedades sin agregar requisitos nuevos\n"
    "- Si el mensaje ya es claro y específico, devuélvelo casi igual\n"
    "- Responde SOLO con el prompt mejorado, sin preámbulo ni explicación\n"
    "- No agregues comillas alrededor del resultado\n"
    "- Mantén el tono casual chileno/neutro del usuario"
)


class GroqError(Exception):
    """Error general del cliente Groq."""


class GroqAllKeysFailed(GroqError):
    """Todas las API keys de Groq fallaron."""


class GroqClient:
    def __init__(self, api_keys: list[str]):
        if not api_keys:
            raise ValueError("Se requiere al menos una API key de Groq")
        self._keys = list(api_keys)
        self._cycle: Iterator[str] = cycle(self._keys)
        self._current = next(self._cycle)
        self._lock = asyncio.Lock()

    def _rotate(self) -> str:
        self._current = next(self._cycle)
        return self._current

    async def enhance_prompt(self, text: str) -> str:
        async with self._lock:
            return await self._enhance_with_rotation(text)

    async def _enhance_with_rotation(self, text: str) -> str:
        errors: list[str] = []
        for _ in range(len(self._keys)):
            try:
                return await self._call_chat(text, self._current)
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"Groq key falló ({type(e).__name__}): {e}; rotando")
                errors.append(f"{type(e).__name__}: {e}")
                self._rotate()
        raise GroqAllKeysFailed(f"Todas las keys fallaron. Últimos errores: {errors[-3:]}")

    async def _call_chat(self, text: str, api_key: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": CHAT_MODEL,
                    "messages": [
                        {"role": "system", "content": ENHANCE_SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.ogg") -> str:
        async with self._lock:
            return await self._transcribe_with_rotation(audio_bytes, filename)

    async def _transcribe_with_rotation(self, audio_bytes: bytes, filename: str) -> str:
        errors: list[str] = []
        for _ in range(len(self._keys)):
            try:
                return await self._call_whisper(audio_bytes, filename, self._current)
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"Groq Whisper falló ({type(e).__name__}): {e}; rotando")
                errors.append(f"{type(e).__name__}: {e}")
                self._rotate()
        raise GroqAllKeysFailed(f"Todas las keys fallaron. Últimos errores: {errors[-3:]}")

    async def _call_whisper(self, audio_bytes: bytes, filename: str, api_key: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (filename, audio_bytes, "application/octet-stream")}
            data = {"model": WHISPER_MODEL, "language": "es", "response_format": "text"}
            r = await client.post(
                f"{GROQ_BASE_URL}/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=data,
            )
            r.raise_for_status()
            return r.text.strip()
