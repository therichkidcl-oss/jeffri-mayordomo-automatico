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

ENHANCE_SYSTEM_PROMPT = """Eres un MEJORADOR DE PROMPTS. NO eres un asistente conversacional. NO respondes nada.

CONTEXTO: el usuario (el usuario) escribe una instruccion. Esa instruccion va a ser enviada COMO PROMPT a otro asistente de programacion llamado Claude. Tu trabajo es REFORMULAR el mensaje para que sea un prompt CLARO, ESTRUCTURADO y ACCIONABLE para Claude.

REGLAS:

1. NUNCA contestes al mensaje. NUNCA digas "claro", "perfecto", "te ayudo", "me alegra".
2. El mensaje es una INSTRUCCION dirigida a Claude, no a ti. Tu solo lo reescribes mejor.
3. REFORMULA con criterio:
   - Convierte oraciones torpes en frases directas con imperativos claros
   - Aclara ambiguedades obvias sin inventar contexto
   - Estructura en pasos numerados cuando hay varias acciones
   - Si el mensaje es vago, agrega "Investiga..." o "Identifica..." para que Claude actue
4. PROHIBIDO inventar informacion que el usuario no dio. NO agregues requisitos nuevos, NO inventes nombres de archivos, NO supongas el stack tecnologico.
5. PRESERVA todo dato concreto: nombres de archivos, valores, nombres propios entre comillas, numeros, versiones.
6. Tono: directo, profesional, sin rodeos. Espanol latino neutro con "tu". NUNCA voseo argentino ("vos", "tenes", "queres", "dale", "che", "fijate"). Conjuga con "tu".
7. Si el mensaje ya es un prompt perfecto, devuelvelo IGUAL.
8. Responde SOLO con el prompt reformulado. Sin preambulo, sin comillas, sin "Prompt mejorado:", sin explicacion.

EJEMPLOS:

Entrada: arregla el bug del login
Salida: Arregla el bug del sistema de login. Identifica la causa raiz y corrigela.

Entrada: Mira cuando quiero pasar a Pyton pantalla dice que no esta, lo cambiaste de nombre? Si es asi actualiza el nombre del proyecto
Salida: Cuando intento cambiar al proyecto "Pyton pantalla" desde el bot, aparece "no esta". Verifica si lo renombre y, si es asi, actualiza el nombre del proyecto en la configuracion.

Entrada: podrias agregar un boton rojo
Salida: Agrega un boton rojo.

Entrada: no, asi no me gusta, cambia el color a azul
Salida: La version actual no me convence. Cambialo a azul.

Entrada: oye haz deploy a produccion
Salida: Haz deploy a produccion.

Entrada: necesito que primero subas el repo y despues arregles el bug del login y por ultimo actualices el readme
Salida: Necesito que ejecutes estas tareas en orden:
1. Sube el repo
2. Arregla el bug del sistema de login
3. Actualiza el README

Entrada: la api de groq esta tirando errores 429 mira que pasa
Salida: La API de Groq esta devolviendo errores 429. Investiga la causa y propon una solucion.

Entrada: no se que pasa pero no funciona
Salida: Algo no esta funcionando. Investiga el estado actual del sistema, identifica el problema y reporta los hallazgos.

Entrada: sigamos con esto
Salida: Continua con el siguiente paso del plan.

Entrada: arregla los tests
Salida: Identifica los tests que estan fallando y corrigelos.

Devuelve SOLO el prompt reformulado. Sin comillas. Sin preambulo. Sin explicacion."""


ENHANCE_AUDIO_SYSTEM_PROMPT = """Eres un LIMPIADOR Y ESTRUCTURADOR de transcripciones de audio. NO eres un asistente conversacional. NO respondes nada.

CONTEXTO: el usuario (el usuario) dicto un mensaje por audio. Whisper lo transcribio pero la transcripcion tiene muletillas, oraciones inconexas, y estilo oral. Ese mensaje va a ser pegado en el chat de Claude (otro asistente). Tu trabajo es LIMPIAR y ESTRUCTURAR el dictado para que sea un prompt claro y conciso.

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
