"""TTS local con Piper. `speak(text)` sintetiza voz en espanol y la reproduce.

Local, gratis, sin API. La voz Piper se carga una vez (lazy singleton).
Si algo falla, hace fallback a imprimir el texto (nunca crashea el loop de voz).
"""
import io
import logging
import wave

logger = logging.getLogger(__name__)


class PiperTTS:
    def __init__(self, voice_path: str, length_scale: float = 1.0):
        self.voice_path = voice_path
        self.length_scale = length_scale  # >1.0 = mas lento/pausado (tono sabio)
        self._voice = None

    def _ensure_voice(self):
        if self._voice is None:
            from piper import PiperVoice
            logger.info(f"Cargando voz Piper: {self.voice_path} (length_scale={self.length_scale})")
            self._voice = PiperVoice.load(self.voice_path)
        return self._voice

    def synthesize_wav_bytes(self, text: str) -> bytes:
        voice = self._ensure_voice()
        cfg = None
        if self.length_scale != 1.0:
            from piper import SynthesisConfig
            cfg = SynthesisConfig(length_scale=self.length_scale)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            voice.synthesize_wav(text, w, syn_config=cfg)
        return buf.getvalue()

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        try:
            wav_bytes = self.synthesize_wav_bytes(text)
            _play_wav_bytes(wav_bytes)
        except Exception:
            logger.exception("TTS Piper fallo; fallback a texto")
            print(f"[Jeffri dice] {text}")


def _play_wav_bytes(wav_bytes: bytes) -> None:
    import numpy as np
    import sounddevice as sd

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16)
    sd.play(audio, rate)
    sd.wait()


_default: PiperTTS | None = None


def speak(text: str, voice_path: str) -> None:
    """Helper de modulo: TTS por defecto (singleton perezoso)."""
    global _default
    if _default is None or _default.voice_path != voice_path:
        _default = PiperTTS(voice_path)
    _default.speak(text)
