"""Captura de audio push-to-talk: graba mientras se mantiene la tecla (F9).

Devuelve el audio como WAV bytes mono 16 kHz PCM16, listo para faster-whisper.
La parte de captura real usa pynput (tecla global) + sounddevice (mic); la
codificacion a WAV se aisla en `frames_to_wav` para poder testearla sin hardware.
"""
import io
import logging
import threading
import wave

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # faster-whisper trabaja bien con 16 kHz mono


def frames_to_wav(audio_int16, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Convierte un arreglo numpy int16 mono a WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(sample_rate)
        w.writeframes(bytes(audio_int16.tobytes()))
    return buf.getvalue()


def _resolve_key(hotkey: str):
    from pynput import keyboard
    # "f9" -> keyboard.Key.f9 ; letras sueltas -> KeyCode
    if hasattr(keyboard.Key, hotkey):
        return getattr(keyboard.Key, hotkey)
    return keyboard.KeyCode.from_char(hotkey)


def record_while_held(hotkey: str = "f9", sample_rate: int = SAMPLE_RATE) -> bytes:
    """Bloquea hasta que se presiona `hotkey`, graba mientras se mantiene, y
    devuelve WAV bytes al soltar. Devuelve b"" si no se capturo nada."""
    import numpy as np
    import sounddevice as sd

    target = _resolve_key(hotkey)
    frames: list = []
    recording = threading.Event()
    released = threading.Event()

    def on_press(key):
        if key == target:
            recording.set()

    def on_release(key):
        if key == target and recording.is_set():
            released.set()
            return False  # detiene el listener

    def audio_callback(indata, _frames, _time, _status):
        if recording.is_set():
            frames.append(indata.copy())

    from pynput import keyboard
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    logger.info(f"Manten {hotkey.upper()} para hablar...")
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", callback=audio_callback):
        released.wait()
    listener.stop()

    if not frames:
        return b""
    audio = np.concatenate(frames, axis=0).reshape(-1)
    return frames_to_wav(audio, sample_rate)
