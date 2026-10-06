"""Mejorador/limpiador de prompts con DeepSeek V4.1-Flash.

Reemplaza el path que antes usaba Groq (llama-3.3-70b) para:
- Reformular textos escritos por el usuario en Telegram antes de mandarlos a Claude.
- Limpiar transcripciones de audio (source="voz") — la transcripcion en si sigue
  siendo LOCAL con faster-whisper (src/stt.py), aca solo se pule el texto.

Diseno:
- Una sola API key de DeepSeek (sin rotacion, a diferencia de Groq).
- Modelo default: deepseek-flash (V4.1-Flash). Alias oficial mas reciente.
- Thinking mode DESACTIVADO: un enhancer de prompts no necesita razonamiento;
  seria mas lento y mas caro sin beneficio.
- Los 2 system prompts (texto vs voz) viven aca, no en groq_client.

Uso:
    enh = PromptEnhancer(api_key, model="deepseek-flash")
    reformulado = await enh.enhance(texto, source="texto")   # o source="voz"
"""
import logging

import httpx

logger = logging.getLogger(__name__)

DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-flash"


ENHANCE_SYSTEM_PROMPT = """Eres un MEJORADOR DE PROMPTS. NO eres un asistente conversacional. NO respondes nada.

CONTEXTO: el usuario ({user_title}) escribe una instruccion. Esa instruccion va a ser enviada COMO PROMPT a otro asistente de programacion llamado Claude. Tu trabajo es REFORMULAR el mensaje para que sea un prompt CLARO, ESTRUCTURADO y ACCIONABLE para Claude.

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

Entrada: la api externa esta tirando errores 429 mira que pasa
Salida: La API externa esta devolviendo errores 429. Investiga la causa y propon una solucion.

Entrada: no se que pasa pero no funciona
Salida: Algo no esta funcionando. Investiga el estado actual del sistema, identifica el problema y reporta los hallazgos.

Entrada: sigamos con esto
Salida: Continua con el siguiente paso del plan.

Entrada: arregla los tests
Salida: Identifica los tests que estan fallando y corrigelos.

Devuelve SOLO el prompt reformulado. Sin comillas. Sin preambulo. Sin explicacion."""


ENHANCE_AUDIO_SYSTEM_PROMPT = """Eres un LIMPIADOR Y ESTRUCTURADOR de transcripciones de audio. NO eres un asistente conversacional. NO respondes nada.

CONTEXTO: el usuario ({user_title}) dicto un mensaje por audio. Whisper lo transcribio pero la transcripcion tiene muletillas, oraciones inconexas, y estilo oral. Ese mensaje va a ser pegado en el chat de Claude (otro asistente). Tu trabajo es LIMPIAR y ESTRUCTURAR el dictado para que sea un prompt claro y conciso.

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

Entrada: este bueno entonces lo que necesito es que arregles el bug del deploy y tambien que veas si la api externa esta funcionando bien
Salida: Arregla el bug del deploy y verifica si la API externa esta funcionando correctamente.

Entrada: ok asi quedo bien
Salida: Asi quedo bien, no hagas mas cambios.

Entrada: necesito que hagas tres cosas primero subir el repo segundo arreglar el bug del login y tercero actualizar el readme
Salida: Necesito que hagas tres cosas:
1. Subir el repo
2. Arreglar el bug del login
3. Actualizar el README

Devuelve SOLO el prompt limpio. Sin comillas. Sin preambulo. Sin explicacion."""


class EnhancerError(Exception):
    """El enhancer (DeepSeek) fallo: status distinto de 200, timeout o error de red."""


class PromptEnhancer:
    def __init__(
        self,
        api_key: str,
        model: str = DEEPSEEK_DEFAULT_MODEL,
        base_url: str = DEEPSEEK_DEFAULT_BASE_URL,
    ):
        if not api_key:
            raise ValueError("Se requiere una API key de DeepSeek")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def enhance(
        self,
        text: str,
        source: str = "texto",
        user_title: str = "mi senor",
    ) -> str:
        """Devuelve el texto reformulado. Levanta EnhancerError si DeepSeek falla.

        source="voz"  -> usa el prompt de LIMPIADOR (transcripcion oral).
        source="texto" (default) o cualquier otro valor -> usa el prompt de MEJORADOR.

        user_title: el titulo honorifico que el usuario eligio (Sir Smith, Jefa,
        Doctor, etc.). Se inyecta en el system prompt para que DeepSeek sepa
        a quien se refiere la instruccion. Fallback: "mi senor".
        """
        template = ENHANCE_AUDIO_SYSTEM_PROMPT if source == "voz" else ENHANCE_SYSTEM_PROMPT
        # Reemplazo literal (NO .format) — los prompts contienen "{" y "}" de los
        # ejemplos y uno .format los interpretaria como campos.
        system = template.replace("{user_title}", user_title)
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
            # V4.1-Flash tiene thinking mode ON por default; un enhancer NO lo
            # necesita — solo agrega latencia y costo. Lo apagamos explicitamente.
            "thinking": {"type": "disabled"},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                r = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                resp = e.response
                status = getattr(resp, "status_code", "desconocido")
                detail = (getattr(resp, "text", "") or "")[:500]
                logger.warning(f"DeepSeek respondio status {status}: {detail}")
                raise EnhancerError(
                    f"DeepSeek respondio status {status}: {detail}"
                ) from e
            except httpx.RequestError as e:
                logger.warning(f"Error de red con DeepSeek ({type(e).__name__}): {e}")
                raise EnhancerError(f"Error de red con DeepSeek: {e}") from e

            if r.status_code != 200:
                detail = (getattr(r, "text", "") or "")[:500]
                raise EnhancerError(
                    f"DeepSeek respondio status {r.status_code}: {detail}"
                )

            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else ""
