"""Transcripcion de audio LOCAL con faster-whisper. Sin API, sin tokens.

Convierte bytes de audio (WAV/OGG/MP3, cualquier formato que ffmpeg/av lea) a
texto en espanol. El modelo se carga una vez (lazy) y se reutiliza.
"""
import io
import logging

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "small"  # base/small/medium/large-v3; small = buen balance en CPU


class LocalTranscriber:
    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE, language: str = "es"):
        self.model_size = model_size
        self.language = language
        self._model: WhisperModel | None = None

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            logger.info(f"Cargando modelo faster-whisper '{self.model_size}' (int8, CPU)...")
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_bytes: bytes) -> str:
        model = self._ensure_model()
        segments, _info = model.transcribe(
            io.BytesIO(audio_bytes),
            language=self.language,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


_default: LocalTranscriber | None = None


def transcribe_bytes(audio_bytes: bytes, model_size: str = DEFAULT_MODEL_SIZE) -> str:
    """Helper de modulo: transcriptor por defecto (singleton perezoso)."""
    global _default
    if _default is None:
        _default = LocalTranscriber(model_size=model_size)
    return _default.transcribe(audio_bytes)
