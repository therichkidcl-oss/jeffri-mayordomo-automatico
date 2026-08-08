"""Loop de voz de Jeffri: push-to-talk -> STT -> cerebro -> TTS, y despacho a
Claude con resumen hablado.

Un turno:
1. record_fn(hotkey) graba mientras F9 esta presionado -> WAV bytes
2. transcriber(wav) -> texto (faster-whisper local)
3. brain.handle_user_turn(texto) -> BrainResponse
4. tts_speak(respuesta.speech)
5. si respuesta.dispatch_prompt: se adquiere send_lock, controller.send(prompt),
   luego get_claude_response() espera la salida de Claude, brain.summarize_claude
   la condensa y se habla.

Todo se inyecta por constructor para que sea testeable y para compartir el
ClaudeController + send_lock con la interfaz de Telegram (mismo proceso).
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


class VoiceLoop:
    def __init__(
        self,
        transcriber,          # callable(wav_bytes) -> str
        brain,                # Brain
        tts_speak,            # callable(text) -> None
        controller,           # ClaudeController (compartido)
        send_lock,            # asyncio.Lock (compartido con Telegram)
        get_claude_response,  # async callable() -> str | None  (lee la salida de Claude)
        record_fn,            # callable(hotkey) -> wav_bytes
        hotkey: str = "f9",
    ):
        self.transcriber = transcriber
        self.brain = brain
        self.speak = tts_speak
        self.controller = controller
        self.send_lock = send_lock
        self.get_claude_response = get_claude_response
        self.record_fn = record_fn
        self.hotkey = hotkey

    async def process_turn(self) -> None:
        audio = await asyncio.to_thread(self.record_fn, self.hotkey)
        if not audio:
            return
        text = await asyncio.to_thread(self.transcriber, audio)
        if not text or not text.strip():
            return

        logger.info(f"voz: {text!r}")
        resp = await self.brain.handle_user_turn(text)
        if resp.speech:
            self.speak(resp.speech)

        if resp.switch_project:
            try:
                async with self.send_lock:
                    await self.controller.switch_session(resp.switch_project)
            except Exception as e:
                logger.exception("error cambiando de proyecto")
                self.speak(f"No pude cambiar de proyecto, Sir Rich: {e}")
            return

        if resp.dispatch_prompt:
            try:
                async with self.send_lock:
                    await self.controller.send(resp.dispatch_prompt)
            except Exception as e:
                logger.exception("error mandando a Claude")
                self.speak(f"No pude mandarselo a Claude, Sir Rich: {e}")
                return
            # esperar la respuesta de Claude y resumirla en voz
            try:
                claude_text = await self.get_claude_response()
            except Exception:
                logger.exception("error esperando respuesta de Claude")
                claude_text = None
            if claude_text:
                summary = await self.brain.summarize_claude(claude_text)
                if summary:
                    self.speak(summary)

    async def run(self) -> None:
        logger.info("Loop de voz iniciado. Manten F9 para hablar con Jeffri.")
        while True:
            try:
                await self.process_turn()
            except Exception:
                logger.exception("error en turno de voz; sigo")
