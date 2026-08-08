import wave
import struct
import math
from io import BytesIO

from src.stt import transcribe_bytes, LocalTranscriber


def _make_wav_bytes(seconds=0.3, freq=440, rate=16000):
    """Genera un WAV mono PCM16 sintetico (un tono) para no depender de audio real."""
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            val = int(32767 * 0.2 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", val)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def test_transcriber_singleton_reuses_model(monkeypatch):
    calls = []

    class FakeModel:
        def __init__(self, *a, **k):
            calls.append((a, k))
        def transcribe(self, *a, **k):
            return ([], None)

    monkeypatch.setattr("src.stt.WhisperModel", FakeModel)
    t = LocalTranscriber(model_size="small")
    t.transcribe(b"\x00" * 100)
    t.transcribe(b"\x00" * 100)
    assert len(calls) == 1  # el modelo se crea UNA sola vez


def test_transcribe_joins_segments(monkeypatch):
    class Seg:
        def __init__(self, text): self.text = text

    class FakeModel:
        def __init__(self, *a, **k): pass
        def transcribe(self, audio, **k):
            return ([Seg(" Hola"), Seg(" mundo")], None)

    monkeypatch.setattr("src.stt.WhisperModel", FakeModel)
    t = LocalTranscriber(model_size="small")
    result = t.transcribe(_make_wav_bytes())
    assert result == "Hola mundo"


def test_transcribe_bytes_module_helper(monkeypatch):
    class Seg:
        def __init__(self, text): self.text = text

    class FakeModel:
        def __init__(self, *a, **k): pass
        def transcribe(self, audio, **k):
            return ([Seg("prueba")], None)

    monkeypatch.setattr("src.stt.WhisperModel", FakeModel)
    import src.stt
    src.stt._default = None  # resetea el singleton del helper
    assert transcribe_bytes(_make_wav_bytes()) == "prueba"
