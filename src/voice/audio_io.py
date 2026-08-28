"""Captura de audio push-to-talk: graba mientras se mantiene la tecla (F9).

Devuelve el audio como WAV bytes mono 16 kHz PCM16, listo para faster-whisper.

IMPORTANTE: la deteccion de la tecla usa SONDEO (GetAsyncKeyState de Windows),
NO un hook global de teclado. Un hook (como el de pynput) intercepta TODAS las
teclas del sistema y mete lag al escribir en cualquier app: cada pulsacion tiene
que pasar por Python antes de llegar a la ventana. El sondeo solo LEE el estado
de la tecla cada pocos ms y no toca la entrada de teclado -> cero lag.
La codificacion a WAV se aisla en `frames_to_wav` para testearla sin hardware.
"""
import io
import logging
import threading
import time
import wave

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # faster-whisper trabaja bien con 16 kHz mono
_POLL_INTERVAL = 0.03  # 30 ms: imperceptible para push-to-talk, CPU despreciable


def frames_to_wav(audio_int16, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Convierte un arreglo numpy int16 mono a WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(sample_rate)
        w.writeframes(bytes(audio_int16.tobytes()))
    return buf.getvalue()


def _vk_code(hotkey: str) -> int:
    """Codigo de tecla virtual de Windows para el hotkey (ej. 'f9' -> 0x78).
    F1..F24 -> 0x70..0x87 ; letra/digito suelto -> su codigo ASCII en mayuscula.
    """
    hotkey = (hotkey or "f9").strip().lower()
    if len(hotkey) >= 2 and hotkey[0] == "f" and hotkey[1:].isdigit():
        n = int(hotkey[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)  # F1 = 0x70
    if len(hotkey) == 1:
        return ord(hotkey.upper())
    return 0x78  # fallback: F9


def _key_is_down(vk: int) -> bool:
    """True si la tecla esta presionada AHORA (bit alto 0x8000 de GetAsyncKeyState).
    Solo LEE el estado; no instala ningun hook, asi que no afecta al teclado."""
    import ctypes
    return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0


def record_while_held(hotkey: str = "f9", sample_rate: int = SAMPLE_RATE) -> bytes:
    """Bloquea hasta que se presiona `hotkey`, graba mientras se mantiene, y
    devuelve WAV bytes al soltar. Devuelve b"" si no se capturo nada."""
    import numpy as np
    import sounddevice as sd

    vk = _vk_code(hotkey)
    frames: list = []
    recording = threading.Event()

    def audio_callback(indata, _frames, _time, _status):
        if recording.is_set():
            frames.append(indata.copy())

    logger.info(f"Manten {hotkey.upper()} para hablar...")
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", callback=audio_callback):
        # Sondeo (sin hook global -> no lag al escribir en otras apps):
        # 1. esperar a que se presione la tecla
        while not _key_is_down(vk):
            time.sleep(_POLL_INTERVAL)
        # 2. grabar mientras se mantenga presionada
        recording.set()
        while _key_is_down(vk):
            time.sleep(_POLL_INTERVAL)
        recording.clear()

    if not frames:
        return b""
    audio = np.concatenate(frames, axis=0).reshape(-1)
    return frames_to_wav(audio, sample_rate)
