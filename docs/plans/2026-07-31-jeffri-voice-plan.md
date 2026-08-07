# Jeffri Voz — Plan de Implementación

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Arreglar Jeffri de Telegram (audio + mejorador) con faster-whisper local, y construir "Jeffri Voz": una capa conversacional por voz (push-to-talk) con cerebro DeepSeek que investiga, opina y despacha prompts refinados a Claude con confirmación por voz.

**Architecture:** Un proceso Python. `src/` plano actúa como núcleo compartido (NO se mueve nada — evita romper los 65 tests). Se agrega `src/stt.py` (faster-whisper) y el paquete `src/voice/` (cerebro, TTS, audio, búsqueda). `src/main.py` corre Telegram + Voz concurrentemente, compartiendo un solo `ClaudeController` con su `send_lock`.

**Tech Stack:** Python 3.14, python-telegram-bot 22.7, faster-whisper (STT local), piper-tts (TTS local), sounddevice + pynput (audio + hotkey F9), ddgs (búsqueda web DuckDuckGo), DeepSeek API (OpenAI-compatible vía httpx), pytest.

**Notas de disciplina:**
- TDD en módulos de lógica pura (stt wrapper, deepseek_client, search, brain state machine).
- `superpowers:test-driven-development` para cada ciclo test→impl.
- `superpowers:verification-before-completion` antes de marcar una fase completa.
- `superpowers:systematic-debugging` para el bug del mejorador (Task 4): NO parchear a ciegas.
- El bot corre por tarea programada "Jeffri Telegram Bot" (actualmente **Disabled**). Mantener disabled hasta terminar Fase 1.
- Requisito de setup para Fase 2: `DEEPSEEK_API_KEY` en `.env` (el usuario la pega). Todo lo demás funciona sin ella.

---

## FASE 1 — Jeffri Telegram sano + faster-whisper local

### Task 1: Dependencias de STT local

**Files:**
- Modify: `requirements.txt`

**Step 1: Añadir faster-whisper a requirements**

Agregar al final de `requirements.txt`:
```
faster-whisper>=1.0.0
```

**Step 2: Instalar en el venv**

Run: `.venv/Scripts/python.exe -m pip install faster-whisper`
Expected: instala sin error (trae ctranslate2, tokenizers, onnxruntime).

**Step 3: Verificar import**

Run: `.venv/Scripts/python.exe -c "from faster_whisper import WhisperModel; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add faster-whisper para STT local"
```

---

### Task 2: `src/stt.py` — transcripción local (TDD)

Wrapper de faster-whisper. Carga el modelo una vez (lazy singleton) y transcribe bytes de audio a texto en español. Reemplaza la transcripción de Groq.

**Files:**
- Create: `src/stt.py`
- Create: `tests/test_stt.py`

**Step 1: Test que falla**

`tests/test_stt.py`:
```python
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
```

**Step 2: Ejecutar test, confirmar FAIL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stt.py -q`
Expected: FAIL (módulo no existe).

**Step 3: Implementar `src/stt.py`**

```python
"""Transcripcion de audio LOCAL con faster-whisper. Sin API, sin tokens.

Convierte bytes de audio (WAV/OGG/MP3, cualquier formato que ffmpeg lea) a
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
```

**Step 4: Ejecutar test, confirmar PASS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stt.py -q`
Expected: 3 passed.

**Step 5: Commit**

```bash
git add src/stt.py tests/test_stt.py
git commit -m "feat: transcripcion local con faster-whisper (src/stt.py)"
```

---

### Task 3: Telegram usa faster-whisper para audio

Reemplaza `state.groq.transcribe(...)` por `src.stt` en el handler de voz.

**Files:**
- Modify: `src/bot.py` (funcion `on_voice_or_audio`, ~línea 652)

**Step 1: Cambiar la transcripción**

En `on_voice_or_audio`, reemplazar el bloque que llama a `state.groq.transcribe`:
```python
    await update.message.reply_text("🎙 Transcribiendo (local, sin API)...")
    try:
        import asyncio
        from src.stt import transcribe_bytes
        transcript = await asyncio.to_thread(transcribe_bytes, audio_bytes)
    except Exception as e:
        logger.exception("Error en transcripcion local")
        await update.message.reply_text(f"❌ Error transcribiendo: {e}")
        return
```

También quitar el guard `if state.groq is None: no puedo transcribir` — la
transcripción ya NO depende de Groq (Groq sigue solo para el mejorador de texto).
Si `state.groq is None`, igual se transcribe local y el texto va directo a Claude.

**Step 2: Verificar import y tests existentes**

Run: `.venv/Scripts/python.exe -c "import src.bot; print('OK')"`
Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: import OK; todos los tests siguen pasando.

**Step 3: Commit**

```bash
git add src/bot.py
git commit -m "feat: Telegram transcribe audio con faster-whisper local (no Groq)"
```

---

### Task 4: Encontrar y arreglar el bug del mejorador / comandos

**REQUIRED SUB-SKILL: superpowers:systematic-debugging.** NO parchear a ciegas.

Síntomas reportados: el mejorador de prompts no se activaba, y "le doy comando y
no se detiene". Groq YA se verificó que funciona (keys + modelos + chat OK).

**Files:**
- Modify: `src/bot.py` (logging a archivo)
- Modify: el módulo donde esté la causa raíz (a determinar)
- Create: test de regresión del bug encontrado

**Step 1: Añadir logging a archivo (instrumentación)**

En `src/bot.py`, en `logging.basicConfig`, agregar un FileHandler a `logs/jeffri.log`:
```python
import os
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/jeffri.log", encoding="utf-8"),
    ],
)
```
Añadir `logs/` a `.gitignore`.

**Step 2: Reproducir con el bot instrumentado**

Arrancar el bot en foreground capturando salida:
`.venv/Scripts/python.exe -m src.bot` (o vía WMI si hace falta que sobreviva).
Mandar por Telegram: (a) un texto normal, (b) `/enhancer on` y luego texto,
(c) un comando. Leer `logs/jeffri.log`.

**Step 3: Identificar causa raíz — hipótesis a verificar EN ORDEN**

1. **`state.enhancer_enabled == False`**: si quedó apagado, el texto va directo
   sin mejorar (esperado, no bug). Verificar con `/estado`. Si es esto, no es
   bug de código; documentar que `/enhancer on` lo reactiva.
2. **El handler nuevo del teclado intercepta texto que no debía**: en Task del
   menú se agregó `MessageHandler(filters.Text(KEYBOARD_ROUTES.keys()), ...)`.
   Verificar que NO capture texto normal (solo las etiquetas exactas). Si captura
   de más, el texto normal nunca llega a `on_text_message` → no se mejora.
3. **Excepción silenciada en `_process_user_text`**: revisar el log por
   tracebacks de Groq o del controller.
4. **"No se detiene"**: aclarar si es `/stop` (interrumpe Claude vía ESC — UI
   automation) o el reenvío. Revisar `cmd_stop` y `controller.interrupt()` en el
   log.

**Step 4: Escribir test de regresión de la causa encontrada**

Ejemplo si es el handler del teclado interceptando de más:
```python
def test_keyboard_filter_does_not_catch_normal_text():
    from src.menu import KEYBOARD_ROUTES
    from telegram.ext import filters
    f = filters.Text(set(KEYBOARD_ROUTES.keys()))
    # un texto normal NO debe matchear el filtro del teclado
    # (se testea la semantica del set de etiquetas)
    assert "arregla el login" not in KEYBOARD_ROUTES
    assert "🗂 Proyectos" in KEYBOARD_ROUTES
```
(El test real depende de la causa raíz encontrada.)

**Step 5: Implementar el fix mínimo + verificar**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: todos pasan, incluido el nuevo test de regresión.

**Step 6: Commit**

```bash
git add src/bot.py tests/ .gitignore
git commit -m "fix: <causa raiz encontrada del mejorador/comandos> + logging a archivo"
```

---

### Task 5: Reactivar Telegram y verificar salud

**Files:** (ninguno — operación)

**Step 1: Reactivar la tarea programada**

```powershell
Enable-ScheduledTask -TaskName "Jeffri Telegram Bot"
Start-ScheduledTask  -TaskName "Jeffri Telegram Bot"
```

**Step 2: Verificar (superpowers:verification-before-completion)**

- 2 procesos `pythonw` de `src.bot` vivos (bot + worker)
- Telegram getMyCommands: 10 comandos
- Mandar `/start`, `/estado`, un audio (debe transcribir local), un texto (debe
  ofrecer mejora). Confirmar en `logs/jeffri.log` sin errores.

**Step 3: Reportar al usuario** el estado de Fase 1 antes de seguir a Fase 2.

---

## FASE 2 — Jeffri Voz

### Task 6: Dependencias de voz

**Files:** Modify `requirements.txt`

Añadir:
```
piper-tts>=1.2.0
sounddevice>=0.4.6
pynput>=1.7.6
ddgs>=6.0.0
```
Instalar en el venv. Verificar imports uno por uno. Descargar una voz Piper
español (ej. `es_MX-ald-medium`) a `voice_models/`. Commit.

### Task 7: `src/voice/audio_io.py` — hotkey F9 + captura de mic

Graba audio mientras F9 está presionado (pynput global listener), devuelve WAV
bytes al soltar. Función `record_while_held(key="f9") -> bytes`. Test con
sounddevice/pynput mockeados (no audio real). TDD. Commit.

### Task 8: `src/voice/tts.py` — Piper

`speak(text: str)` sintetiza con Piper y reproduce por sounddevice. Carga la voz
una vez (singleton). Fallback: si Piper falla, log + print (no crashea). Test con
Piper mockeado. Commit.

### Task 9: `src/voice/deepseek_client.py` — cliente DeepSeek (TDD)

Cliente OpenAI-compatible (httpx, patrón de `groq_client`). `chat(messages, tools=None)`
contra `https://api.deepseek.com/chat/completions`, key `DEEPSEEK_API_KEY`.
Soporta tool-calling. Test con httpx mockeado (respuesta normal y con tool_calls).
Commit.

### Task 10: `src/voice/search.py` — búsqueda web (TDD)

`web_search(query, max_results=5) -> list[dict]` vía `ddgs`. Devuelve títulos +
snippets + urls. Test con ddgs mockeado. Commit.

### Task 11: `src/voice/brain.py` — cerebro conversacional (TDD, el corazón)

Máquina de estados `idle → conversing → awaiting_confirmation → dispatched → summarizing`.
- `handle_user_turn(text) -> BrainAction`: llama a DeepSeek con el historial y el
  system prompt; puede (a) responder charla, (b) pedir búsqueda web y responder,
  (c) proponer un prompt para Claude y pasar a `awaiting_confirmation`.
- `handle_confirmation(text) -> BrainAction`: interpreta sí/no; si sí, devuelve
  `DispatchAction(prompt)`; si no, vuelve a `conversing`.
- `summarize_claude(events) -> str`: condensa la salida de Claude.
- Historial rodante (últimos N turnos).
Tests con `deepseek_client` mockeado cubriendo cada rama y transición de estado.
El system prompt exige español neutro con "tú", trata al usuario como "Sir Rich",
sin voseo. Commit.

### Task 12: `src/voice/app.py` — loop de voz

Orquesta: `audio_io.record_while_held` → `stt.transcribe_bytes` →
`brain.handle_user_turn` → `tts.speak`. En `awaiting_confirmation`, el siguiente
turno va a `brain.handle_confirmation`; si dispatch, adquiere el `send_lock`
compartido y llama `controller.send(prompt)`. Suscribe al watcher para recibir
eventos de Claude → `brain.summarize_claude` → `tts.speak`. Recibe el
`ClaudeController` y el watcher por inyección (los comparte con Telegram). Commit.

### Task 13: `src/main.py` — corre ambas interfaces

Un solo proceso asyncio: crea UN `ClaudeController` y UN `TranscriptWatcher`
compartidos; arranca el bot de Telegram y el loop de voz concurrentemente,
inyectándoles el controller/watcher. El watcher hace fan-out de eventos a ambas
interfaces. Actualizar la tarea programada para que ejecute `-m src.main` en vez
de `-m src.bot`. Commit.

### Task 14: Integración manual + setup

Documentar en README: instalar deps, descargar voz Piper, pegar `DEEPSEEK_API_KEY`
en `.env`. Probar el loop completo en la PC: F9 → hablar → escuchar respuesta →
"mándaselo a Claude" → confirmar → ver el prompt en Claude → escuchar el resumen.
Crear `docs/smoke-test-voz.md` con hallazgos. Commit.

---

## Sub-skills durante la ejecución

- `superpowers:test-driven-development` en cada Task con ciclo test→impl.
- `superpowers:systematic-debugging` en Task 4 (bug del mejorador).
- `superpowers:verification-before-completion` al cerrar cada Fase.

## Resumen

14 tasks en 2 fases. Fase 1 (Tasks 1-5) devuelve Jeffri Telegram sano con
transcripción local — prioridad, entrega valor inmediato. Fase 2 (Tasks 6-14)
construye el sistema de voz con cerebro DeepSeek, reciclando el puente a Claude y
la transcripción local de la Fase 1.
