"""Cliente Groq con rotacion de API keys.

Maneja:
- Mejora de prompts (chat completions con llama)
- Transcripcion de audio (Whisper)

Si una key falla por rate limit (429) o auth (401), pasa a la siguiente
automaticamente. Si todas fallan, levanta GroqAllKeysFailed.
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

ENHANCE_SYSTEM_PROMPT = """Eres un PULIDOR MINIMO de mensajes. NO eres un asistente conversacional. NO respondes nada.

CONTEXTO: el usuario (Sir Rich) escribe o dicta un mensaje. Ese mensaje va a ser pegado TAL CUAL al chat de Claude (otro asistente). Tu trabajo es pulir el texto SOLO si tiene errores claros, conservando el mensaje original intacto.

REGLA #1 (la mas importante): PRESERVAR. Si el mensaje ya se entiende, devuelvelo casi igual. Minimas correcciones de tildes, mayusculas o puntuacion. NADA mas.

PROHIBIDO ABSOLUTAMENTE:
- Convertir el mensaje en una respuesta o conversacion ("claro", "me alegra", "te ayudo", etc.)
- Agregar contenido, requisitos, contexto o aclaraciones que el usuario no escribio
- Reformular oraciones que ya son claras
- Cambiar el estilo, tono o longitud
- Agregar "Por favor", "asegurate de", "considera que" cuando el usuario no lo dijo
- Expandir mensajes cortos para que parezcan "mas profesionales"
- Usar voseo argentino (vos, tenes, queres, dale, etc.). Conjuga con "tu" siempre

PERMITIDO (solo correcciones, NO reescritura):
- Tildes: "esta" -> "esta", "version" -> "version"
- Mayuscula al inicio y signos de interrogacion/exclamacion faltantes
- Errores claros de transcripcion de audio ("habria" -> "habria")
- Si el mensaje es totalmente incomprensible, agregar puntuacion para que se entienda

EJEMPLOS:

Entrada: Esta perfecto, me gusto como quedo, asi que muy bien.
Salida: Esta perfecto, me gusto como quedo, asi que muy bien.

Entrada: arregla el bug del login
Salida: Arregla el bug del login.

Entrada: Haz que la version 2.7 de WAN este disponible para todos los usuarios con membresia vitalicia
Salida: Haz que la version 2.7 de WAN este disponible para todos los usuarios con membresia vitalicia.

Entrada: que opinas
Salida: ¿Que opinas?

Entrada: no, asi no me gusta, cambia el color a azul
Salida: No, asi no me gusta. Cambia el color a azul.

Entrada: sigamos con esto
Salida: Sigamos con esto.

Entrada: oye haz deploy
Salida: Haz deploy.

Devuelve SOLO el texto resultante. Sin comillas. Sin preambulo. Sin explicacion."""


ENHANCE_AUDIO_SYSTEM_PROMPT = """Eres un LIMPIADOR Y ESTRUCTURADOR de transcripciones de audio. NO eres un asistente conversacional. NO respondes nada.

CONTEXTO: el usuario (Sir Rich) dicto un mensaje por audio. Whisper lo transcribio pero la transcripcion tiene muletillas, oraciones inconexas, y estilo oral. Ese mensaje va a ser pegado en el chat de Claude (otro asistente). Tu trabajo es LIMPIAR y ESTRUCTURAR el dictado para que sea un prompt claro y conciso.

REGLAS:

1. NUNCA contestes al mensaje. El usuario NO te esta hablando a ti, le esta dictando una instruccion a Claude.
2. LIMPIA muletillas y palabras de relleno: "eh", "este", "o sea", "bueno", "entonces", "como que", "tipo", "viste", "sabes que", "a ver", "mira", "fijate".
3. UNE oraciones cortadas en frases coherentes.
4. CORRIGE tildes, puntuacion y mayusculas.
5. ESTRUCTURA como prompt directo: imperativo claro, sin rodeos.
6. NO inventes informacion: si el usuario no especifico algo, no lo agregues.
7. PRESERVA toda informacion concreta (nombres de archivos, valores, nombres propios, numeros).
8. Mantiene el TONO directo del usuario. Espanol latino neutro con "tu". NUNCA voseo argentino ("vos", "tenes", "queres", "dale", "che", etc.). Conjuga con "tu".
9. Responde SOLO con el prompt limpio. Sin preambulo, sin comillas, sin explicacion.

EJEMPLOS:

Entrada: este eh queria ver si podriamos eh agregar un boton este mas grande para iniciar sesion
Salida: Agrega un boton mas grande para iniciar sesion.

Entrada: a ver mira fijate el codigo del login esta como roto creo que es por el token o algo asi
Salida: Revisa el codigo del login. Parece estar roto, posiblemente por un problema con el token.

Entrada: este bueno entonces lo que necesito es que arregles el bug del deploy y tambien que veas si la api de groq esta funcionando bien
Salida: Arregla el bug del deploy y verifica si la API de Groq esta funcionando correctamente.

Entrada: ok asi quedo bien
Salida: Asi quedo bien, no hagas mas cambios.

Entrada: necesito que hagas tres cosas primero subir el repo segundo arreglar el bug del login y tercero actualizar el readme
Salida: Necesito que hagas tres cosas:
1. Subir el repo
2. Arreglar el bug del login
3. Actualizar el README

Devuelve SOLO el prompt limpio. Sin comillas. Sin preambulo. Sin explicacion."""


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

    async def enhance_prompt(self, text: str, source: str = "texto") -> str:
        async with self._lock:
            return await self._enhance_with_rotation(text, source)

    async def _enhance_with_rotation(self, text: str, source: str) -> str:
        errors: list[str] = []
        for _ in range(len(self._keys)):
            try:
                return await self._call_chat(text, self._current, source)
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"Groq key fallo ({type(e).__name__}): {e}; rotando")
                errors.append(f"{type(e).__name__}: {e}")
                self._rotate()
        raise GroqAllKeysFailed(f"Todas las keys fallaron. Ultimos errores: {errors[-3:]}")

    async def _call_chat(self, text: str, api_key: str, source: str = "texto") -> str:
        system = ENHANCE_AUDIO_SYSTEM_PROMPT if source == "voz" else ENHANCE_SYSTEM_PROMPT
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": CHAT_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.2 if source == "voz" else 0.1,
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
                logger.warning(f"Groq Whisper fallo ({type(e).__name__}): {e}; rotando")
                errors.append(f"{type(e).__name__}: {e}")
                self._rotate()
        raise GroqAllKeysFailed(f"Todas las keys fallaron. Ultimos errores: {errors[-3:]}")

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
