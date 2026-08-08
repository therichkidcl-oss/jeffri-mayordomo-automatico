import io
import wave

from src.voice.tts import PiperTTS


def _fake_voice_synthesize(text, wav_file):
    # Escribe un WAV mono PCM16 minimo valido.
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(22050)
    wav_file.writeframes(b"\x00\x00" * 100)


class _FakeVoice:
    def synthesize_wav(self, text, wav_file):
        _fake_voice_synthesize(text, wav_file)


def test_synthesize_wav_bytes_returns_wav(monkeypatch):
    t = PiperTTS("dummy.onnx")
    t._voice = _FakeVoice()  # evita cargar Piper real
    data = t.synthesize_wav_bytes("hola")
    # debe ser un WAV valido
    with wave.open(io.BytesIO(data), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 22050


def test_voice_loaded_once(monkeypatch):
    calls = []

    class FakePiperVoice:
        @staticmethod
        def load(path):
            calls.append(path)
            return _FakeVoice()

    import sys
    import types
    fake_piper = types.ModuleType("piper")
    fake_piper.PiperVoice = FakePiperVoice
    monkeypatch.setitem(sys.modules, "piper", fake_piper)

    t = PiperTTS("voz.onnx")
    t.synthesize_wav_bytes("a")
    t.synthesize_wav_bytes("b")
    assert calls == ["voz.onnx"]  # cargada UNA sola vez


def test_speak_falls_back_to_print_on_error(monkeypatch, capsys):
    t = PiperTTS("dummy.onnx")

    def boom(text):
        raise RuntimeError("sin audio")

    monkeypatch.setattr(t, "synthesize_wav_bytes", boom)
    t.speak("mensaje importante")
    captured = capsys.readouterr()
    assert "mensaje importante" in captured.out  # fallback imprime el texto


def test_speak_ignores_empty():
    t = PiperTTS("dummy.onnx")
    # no debe lanzar ni intentar sintetizar
    t.speak("")
    t.speak("   ")
