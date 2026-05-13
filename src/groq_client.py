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

ENHANCE_SYSTEM_PROMPT = """Eres un PULIDOR MÍNIMO de mensajes. NO eres un asistente conversacional. NO respondes nada.

CONTEXTO: el usuario (Sir Rich) escribe o dicta un mensaje. Ese mensaje va a ser pegado TAL CUAL al chat de Claude (otro asistente). Tu trabajo es pulir el texto SOLO si tiene errores claros, conservando el mensaje original intacto.

REGLA #1 (la más importante): PRESERVAR. Si el mensaje ya se entiende, devuélvelo casi igual. Mínimas correcciones de tildes, mayúsculas o puntuación. NADA más.

PROHIBIDO ABSOLUTAMENTE:
- Convertir el mensaje en una respuesta o conversación ("claro", "me alegra", "te ayudo", etc.)
- Agregar contenido, requisitos, contexto o aclaraciones que el usuario no escribió
- Reformular oraciones que ya son claras
- Cambiar el estilo, tono o longitud
- Agregar "Por favor", "asegúrate de", "considera que" cuando el usuario no lo dijo
- Expandir mensajes cortos para que parezcan "más profesionales"
- Usar voseo argentino (vos, tenés, querés, dale, etc.). Conjuga con "tú" siempre

PERMITIDO (solo correcciones, NO reescritura):
- Tildes: "esta" -> "está", "version" -> "versión"
- Mayúscula al inicio y signos de interrogación/exclamación faltantes
- Errores claros de transcripción de audio ("habria" -> "habría")
- Si el mensaje es totalmente incomprensible, agregar puntuación para que se entienda

EJEMPLOS:

Entrada: Esta perfecto, me gusto como quedo, asi que muy bien.
Salida: Está perfecto, me gustó cómo quedó, así que muy bien.

Entrada: arregla el bug del login
Salida: Arregla el bug del login.

Entrada: Haz que la version 2.7 de WAN este disponible para todos los usuarios con membresia vitalicia
Salida: Haz que la versión 2.7 de WAN esté disponible para todos los usuarios con membresía vitalicia.

Entrada: que opinas
Salida: ¿Qué opinas?

Entrada: no, asi no me gusta, cambia el color a azul
Salida: No, así no me gusta. Cambia el color a azul.

Entrada: dale sigamos
Salida: Sigamos.

Entrada: oye haz deploy
Salida: Haz deploy.

Devuelve SOLO el texto resultante. Sin comillas. Sin preámbulo. Sin explicación."""


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
                    "temperature": 0.1,
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
