import io
import wave

import numpy as np

from src.voice.audio_io import frames_to_wav, SAMPLE_RATE, _vk_code


def test_frames_to_wav_produces_valid_mono_16k():
    audio = np.zeros(1600, dtype=np.int16)  # 0.1s de silencio
    data = frames_to_wav(audio)
    with wave.open(io.BytesIO(data), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == SAMPLE_RATE
        assert w.getnframes() == 1600


def test_frames_to_wav_respects_sample_rate():
    audio = np.zeros(800, dtype=np.int16)
    data = frames_to_wav(audio, sample_rate=8000)
    with wave.open(io.BytesIO(data), "rb") as w:
        assert w.getframerate() == 8000


def test_frames_to_wav_roundtrip_preserves_samples():
    audio = np.array([100, -100, 200, -200], dtype=np.int16)
    data = frames_to_wav(audio)
    with wave.open(io.BytesIO(data), "rb") as w:
        frames = w.readframes(w.getnframes())
    restored = np.frombuffer(frames, dtype=np.int16)
    assert list(restored) == [100, -100, 200, -200]


def test_vk_code_f9_es_0x78():
    # F9 debe mapear al codigo de tecla virtual correcto de Windows.
    assert _vk_code("f9") == 0x78


def test_vk_code_teclas_funcion():
    assert _vk_code("f1") == 0x70
    assert _vk_code("f12") == 0x7B


def test_vk_code_letra_suelta():
    assert _vk_code("a") == 0x41  # 'A'
    assert _vk_code("z") == 0x5A


def test_vk_code_fallback_a_f9():
    # entrada rara -> F9 por defecto (no revienta)
    assert _vk_code("no-existe") == 0x78
