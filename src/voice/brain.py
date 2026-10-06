"""Cerebro conversacional de Jeffri Voz (DeepSeek).

Es un companero que charla, investiga (busqueda web cuando hace falta), opina y
sugiere. Cuando el usuario quiere EJECUTAR/construir algo, el cerebro redacta un
prompt "masticado" para Claude y pide confirmacion por voz antes de mandarlo.
Tambien condensa la salida de Claude en un resumen hablado.

El tono mayordomo usa el titulo honorifico que el usuario eligio (ver
src/user_settings.py). Si no hay titulo, fallback a "mi senor".

Maquina de estados: idle -> conversing -> awaiting_confirmation -> (dispatch) -> idle
"""
import json
import logging
import re
from dataclasses import dataclass

from src.voice.search import format_results_for_llm

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres Jeffri, el companero de voz del usuario (que te pide dirigirte a el como "{user_title}"). Hablas espanol latino neutro con "tu" (NUNCA voseo argentino: nada de "vos", "tenes", "queres", "dale", "che"). Tratas al usuario con tono de mayordomo sumiso, dirigiendote a el como "{user_title}" cuando sea natural.

TU ROL:
- Conversas con {user_title} de forma natural y breve (esto es VOZ: respuestas cortas, sin listas largas ni markdown).
- Investigas, opinas y sugieres. Si necesitas informacion actual (precios, noticias, versiones nuevas), usa la herramienta web_search.
- Tu NO ejecutas codigo ni tareas de desarrollo. Para eso esta Claude, otro asistente que hace el trabajo pesado en la PC.
- Cuando {user_title} quiere EJECUTAR, CONSTRUIR, PROGRAMAR o que se HAGA algo concreto, usa la herramienta dispatch_to_claude: redacta un PROMPT claro, estructurado y accionable para Claude (masticado y mejorado, sin inventar datos que {user_title} no dio).
- Si solo estan conversando/opinando, responde normal SIN usar dispatch_to_claude.

REGLAS DE VOZ:
- Respuestas cortas y habladas (1-3 frases). Sin markdown, sin vinetas, sin codigo largo.
- Directo, con criterio, sin rodeos ni relleno.
"""

SUMMARY_SYSTEM_PROMPT = """Eres el resumidor de Jeffri. Claude (un asistente de programacion) acaba de escribir una respuesta larga y tecnica. Resume en 1-3 frases HABLADAS lo mas importante para {user_title}, en espanol neutro con "tu", sin markdown ni tecnicismos innecesarios. Ejemplo: "Claude ya arreglo el login y corrio los tests, dice que faltan 2 por revisar". Responde SOLO con el resumen."""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca en internet cuando necesitas informacion ACTUAL que no sabes con certeza (precios, noticias, versiones nuevas, datos del dia). No la uses para opiniones o conocimiento general.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "La consulta de busqueda"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dispatch_to_claude",
            "description": "Usa esto cuando el usuario quiere EJECUTAR, construir, programar, arreglar o que se HAGA una tarea concreta en la PC. Redacta un prompt claro y accionable para Claude. NO inventes datos que el usuario no dio.",
            "parameters": {
                "type": "object",
                "properties": {"prompt": {"type": "string", "description": "El prompt masticado y mejorado para Claude"}},
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_project",
            "description": "Usa esto cuando el usuario quiere CAMBIAR de proyecto o sesion de Claude (ej. 'cambiate a IA-HUB', 'trabajemos en el bot de trading', 'abre el proyecto X'). Pasa el nombre del proyecto lo mas parecido a la lista de proyectos disponibles que ves en el system prompt.",
            "parameters": {
                "type": "object",
                "properties": {"project_name": {"type": "string", "description": "Nombre del proyecto al que cambiar"}},
                "required": ["project_name"],
            },
        },
    },
]


_AFFIRM = {"si", "sí", "dale", "hazlo", "mandalo", "mándalo", "confirmo", "correcto",
           "ok", "okay", "vale", "adelante", "perfecto", "eso", "claro", "envialo",
           "envíalo", "manda", "mandale", "mándale", "obvio", "listo"}
_NEG = {"no", "cancela", "cancelar", "espera", "mejor", "para", "detente", "stop", "nel"}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower(), re.UNICODE))


def is_negative(text: str) -> bool:
    return bool(_tokens(text) & _NEG)


def is_affirmative(text: str) -> bool:
    t = _tokens(text)
    return bool(t & _AFFIRM) and not (t & _NEG)


@dataclass
class BrainResponse:
    speech: str                      # lo que Jeffri dice por voz
    dispatch_prompt: str | None = None  # si no es None, mandar ESTO a Claude ahora
    switch_project: str | None = None   # si no es None, cambiar a este proyecto/sesion


class Brain:
    MAX_HISTORY = 20  # ventana rodante de turnos

    def __init__(
        self,
        deepseek_client,
        search_fn,
        projects_provider=None,
        user_title: str = "mi senor",
    ):
        self.client = deepseek_client
        self.search = search_fn
        self.projects_provider = projects_provider  # callable() -> list[str] de nombres
        self.user_title = user_title
        self.history: list[dict] = []
        self.state = "idle"
        self._pending_prompt: str | None = None

    def _system_prompt(self) -> str:
        # replace (no .format): el prompt contiene llaves ortograficas de ejemplos.
        prompt = SYSTEM_PROMPT.replace("{user_title}", self.user_title)
        if self.projects_provider is not None:
            try:
                projects = self.projects_provider() or []
            except Exception:
                projects = []
            if projects:
                lista = ", ".join(projects)
                prompt += f"\n\nPROYECTOS DISPONIBLES (para switch_project): {lista}"
        return prompt

    def _trim_history(self):
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

    async def handle_user_turn(self, text: str) -> BrainResponse:
        text = (text or "").strip()
        if not text:
            return BrainResponse(speech=f"No te escuche, {self.user_title}, repite.")

        if self.state == "awaiting_confirmation":
            return await self._handle_confirmation(text)

        self.state = "conversing"
        self.history.append({"role": "user", "content": text})
        self._trim_history()
        return await self._run_tool_loop()

    async def _run_tool_loop(self, max_iters: int = 4) -> BrainResponse:
        messages = [{"role": "system", "content": self._system_prompt()}] + self.history
        for _ in range(max_iters):
            msg = await self.client.chat(messages, tools=TOOLS)
            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                content = (msg.get("content") or "").strip()
                self.history.append({"role": "assistant", "content": content})
                self._trim_history()
                return BrainResponse(speech=content)

            call = tool_calls[0]
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "dispatch_to_claude":
                prompt = (args.get("prompt") or "").strip()
                self._pending_prompt = prompt
                self.state = "awaiting_confirmation"
                return BrainResponse(
                    speech=f"Le propongo esto a Claude: {prompt}. ¿Se lo mando, {self.user_title}?"
                )

            if name == "switch_project":
                proj = (args.get("project_name") or "").strip()
                self.state = "idle"
                return BrainResponse(
                    speech=f"Cambiando al proyecto {proj}, {self.user_title}.",
                    switch_project=proj,
                )

            if name == "web_search":
                query = args.get("query", "")
                logger.info(f"web_search: {query!r}")
                results = self.search(query)
                messages.append(msg)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", "c1"),
                    "content": format_results_for_llm(results),
                })
                continue

            # tool desconocido
            return BrainResponse(speech=f"No supe procesar eso, {self.user_title}.")

        return BrainResponse(speech=f"Me enrede pensando, {self.user_title}. Reintenta.")

    async def _handle_confirmation(self, text: str) -> BrainResponse:
        if is_affirmative(text):
            prompt = self._pending_prompt
            self._pending_prompt = None
            self.state = "idle"
            return BrainResponse(speech="Perfecto, se lo mando a Claude.", dispatch_prompt=prompt)
        # negativo o correccion: volver a conversar procesando el texto como nuevo turno
        self._pending_prompt = None
        self.state = "conversing"
        self.history.append({"role": "user", "content": text})
        self._trim_history()
        return await self._run_tool_loop()

    async def summarize_claude(self, claude_text: str) -> str:
        system = SUMMARY_SYSTEM_PROMPT.replace("{user_title}", self.user_title)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": claude_text},
        ]
        msg = await self.client.chat(messages)
        return (msg.get("content") or "").strip()
