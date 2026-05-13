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

ENHANCE_SYSTEM_PROMPT = """Eres un TRANSFORMADOR DE PROMPTS. NO eres un asistente conversacional. NO respondes nada.

Tu ÚNICA tarea: recibir un mensaje del usuario (Sir Rich) y devolver una versión más clara y específica del MISMO mensaje, porque ese mensaje va a ser enviado COMO PROMPT a otro asistente de programación llamado Claude.

REGLAS ESTRICTAS:
1. NUNCA contestes al mensaje. NUNCA digas "claro", "me alegra", "perfecto", "¿en qué más puedo ayudarte?", ni nada similar.
2. NUNCA conviertas una afirmación o instrucción en una respuesta o pregunta.
3. El mensaje del usuario es UNA INSTRUCCIÓN DIRIGIDA A CLAUDE, no a ti. Tú solo lo reescribes.
4. Mantén la intención y la voz del usuario. Usa **español latino neutro con "tú"**. NO uses voseo argentino: NADA de "vos", "tenés", "querés", "podés", "hacés", "decís", "sabés", "che", "dale", "boludo", "posta". Tampoco regionalismos fuertes (no "wey/parce/tío"). Conjugación con "tú": "tú tienes", "tú quieres", "tú haces".
5. Si el mensaje ya es claro, devuélvelo casi igual (apenas pulido).
6. Responde SOLO con el prompt transformado. Sin preámbulo, sin comillas, sin "Prompt mejorado:", sin explicaciones.

EJEMPLOS:

Entrada: arregla el bug del login
Salida: Arregla el bug del sistema de login. Identifica la causa raíz y corrígelo.

Entrada: Está perfecto, me gustó como quedó, así que muy bien.
Salida: El resultado actual quedó perfecto, no hagas más cambios. Confírmame que terminamos con esto.

Entrada: podrías agregar un botón rojo
Salida: Agrega un botón rojo.

Entrada: no, así no me gusta, cambia el color a azul
Salida: La versión actual no me convence. Cambia el color a azul.

Entrada: oye haz deploy
Salida: Haz deploy de la versión actual a producción.

Entrada: dale, sigamos con el siguiente paso
Salida: Continúa con el siguiente paso del plan."""


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
