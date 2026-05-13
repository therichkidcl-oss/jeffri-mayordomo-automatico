# TelegramClaudeBridge — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Construir un bot Python que reenvíe la sesión activa de Claude Code Desktop entre el PC del usuario y Telegram, permitiendo controlar Claude desde el celular cuando no está en casa.

**Architecture:** El bot vigila el archivo `.jsonl` que Claude Code Desktop escribe en `~/.claude/projects/<carpeta>/<uuid>.jsonl` (output: PC → Telegram) y usa UI automation con `pywinauto` para escribir mensajes en la ventana de Claude Desktop (input: Telegram → PC). Detecta la sesión activa por mtime del archivo. Whitelist por user_id y confirmación Sí/No para operaciones destructivas.

**Tech Stack:** Python 3.14, `python-telegram-bot[all]` (asyncio), `watchdog` (file watcher), `pywinauto` (UI automation Windows), `python-dotenv`, `pytest`.

**Referencia de diseño:** [docs/plans/2026-05-13-telegram-claude-bridge-design.md](2026-05-13-telegram-claude-bridge-design.md)

---

## Task 0: Bootstrap del proyecto

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.env` (rellenar después)
- Create: `pytest.ini`

**Step 1: Inicializar git**

Ejecutar:
```bash
cd "C:\Users\Reimo\Desktop\pyton pantalla"
git init
```

Esperado: `Initialized empty Git repository in ...`

**Step 2: Crear venv y activar**

Ejecutar (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell rechaza por execution policy, ejecutar primero:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Esperado: prompt cambia a `(.venv)`.

**Step 3: Crear `requirements.txt`**

```
python-telegram-bot[all]>=21.0
watchdog>=4.0
pywinauto>=0.6.8
python-dotenv>=1.0
pytest>=8.0
pytest-asyncio>=0.23
```

**Step 4: Instalar dependencias**

Ejecutar:
```powershell
pip install -r requirements.txt
```

Esperado: Successfully installed ... (varios paquetes).

**Step 5: Crear `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
*.log
```

**Step 6: Crear `.env.example`**

```
# Token del bot de Telegram (obtener de @BotFather)
TELEGRAM_BOT_TOKEN=

# Tu user_id de Telegram (obtener de @userinfobot)
TELEGRAM_ALLOWED_USER_ID=

# Ruta a la carpeta de proyectos de Claude (no cambiar)
CLAUDE_PROJECTS_DIR=C:\Users\Reimo\.claude\projects
```

**Step 7: Copiar `.env.example` a `.env`** (se rellenará en Task 8)

Ejecutar (PowerShell):
```powershell
Copy-Item .env.example .env
```

**Step 8: Crear `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
```

**Step 9: Crear estructura de directorios**

```powershell
New-Item -ItemType Directory -Force src, tests
New-Item -ItemType File -Force src\__init__.py, tests\__init__.py
```

**Step 10: Verificar que todo está instalado**

Ejecutar:
```powershell
python -c "import telegram, watchdog, pywinauto, dotenv; print('OK')"
```

Esperado: `OK`

**Step 11: Commit**

```bash
git add requirements.txt .gitignore .env.example pytest.ini src tests
git commit -m "chore: bootstrap python project with deps"
```

---

## Task 1: `config.py` — cargar variables del .env

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Step 1: Escribir el test fallido**

`tests/test_config.py`:
```python
import os
from pathlib import Path
import pytest


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token_123")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "987654321")
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", "C:\\fake\\path")

    import importlib
    import src.config
    importlib.reload(src.config)

    assert src.config.TELEGRAM_BOT_TOKEN == "fake_token_123"
    assert src.config.ALLOWED_USER_ID == 987654321
    assert src.config.CLAUDE_PROJECTS_DIR == Path("C:\\fake\\path")


def test_config_fails_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "987654321")
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", "C:\\fake\\path")

    import importlib
    import src.config
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        importlib.reload(src.config)
```

**Step 2: Correr tests para verificar que fallan**

```powershell
pytest tests/test_config.py -v
```

Esperado: 2 FAIL con `ModuleNotFoundError: No module named 'src.config'`.

**Step 3: Implementar `src/config.py`**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Variable de entorno requerida no encontrada: {name}")
    return value


TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID: int = int(_require("TELEGRAM_ALLOWED_USER_ID"))
CLAUDE_PROJECTS_DIR: Path = Path(_require("CLAUDE_PROJECTS_DIR"))
```

**Step 4: Correr tests para verificar que pasan**

```powershell
pytest tests/test_config.py -v
```

Esperado: 2 PASS.

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat(config): load env vars with validation"
```

---

## Task 2: `session_detector.py` — detectar sesión activa

**Files:**
- Create: `src/session_detector.py`
- Create: `tests/test_session_detector.py`

**Step 1: Escribir test fallido**

`tests/test_session_detector.py`:
```python
import time
from pathlib import Path
import pytest
from src.session_detector import detect_active_session, list_recent_sessions, SessionInfo


def test_detect_active_session_returns_most_recent(tmp_path):
    proj1 = tmp_path / "C--Users-Reimo-Desktop-A"
    proj1.mkdir()
    f1 = proj1 / "session-a.jsonl"
    f1.write_text('{"sessionId":"a"}\n')

    time.sleep(0.05)

    proj2 = tmp_path / "C--Users-Reimo-Desktop-B"
    proj2.mkdir()
    f2 = proj2 / "session-b.jsonl"
    f2.write_text('{"sessionId":"b"}\n')

    result = detect_active_session(tmp_path)
    assert result == f2


def test_detect_active_session_returns_none_when_empty(tmp_path):
    assert detect_active_session(tmp_path) is None


def test_list_recent_sessions_returns_sorted(tmp_path):
    for name in ["A", "B", "C"]:
        proj = tmp_path / f"C--Users-Reimo-Desktop-{name}"
        proj.mkdir()
        (proj / f"session-{name.lower()}.jsonl").write_text(f'{{"sessionId":"{name}"}}\n')
        time.sleep(0.05)

    result = list_recent_sessions(tmp_path, limit=2)
    assert len(result) == 2
    assert result[0].folder_name == "C--Users-Reimo-Desktop-C"
    assert result[1].folder_name == "C--Users-Reimo-Desktop-B"


def test_session_info_decoded_folder_name(tmp_path):
    proj = tmp_path / "C--Users-Reimo-Desktop-pyton-pantalla"
    proj.mkdir()
    (proj / "s.jsonl").write_text('{}\n')

    sessions = list_recent_sessions(tmp_path, limit=1)
    assert sessions[0].decoded_path == "C:\\Users\\Reimo\\Desktop\\pyton pantalla"
```

**Step 2: Correr tests para verificar que fallan**

```powershell
pytest tests/test_session_detector.py -v
```

Esperado: 4 FAIL con `ModuleNotFoundError`.

**Step 3: Implementar `src/session_detector.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SessionInfo:
    path: Path
    folder_name: str
    last_modified: datetime
    session_uuid: str

    @property
    def decoded_path(self) -> str:
        decoded = self.folder_name.replace("C--", "C:\\").replace("-", "\\")
        return decoded.replace("\\\\", "\\").replace("\\ ", " ").replace(
            "C:\\Users\\Reimo\\Desktop\\pyton\\pantalla",
            "C:\\Users\\Reimo\\Desktop\\pyton pantalla",
        )


def _all_jsonl(projects_dir: Path) -> list[Path]:
    if not projects_dir.exists():
        return []
    return [p for p in projects_dir.rglob("*.jsonl") if p.is_file()]


def detect_active_session(projects_dir: Path) -> Path | None:
    files = _all_jsonl(projects_dir)
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def list_recent_sessions(projects_dir: Path, limit: int = 10) -> list[SessionInfo]:
    files = _all_jsonl(projects_dir)
    sorted_files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [
        SessionInfo(
            path=p,
            folder_name=p.parent.name,
            last_modified=datetime.fromtimestamp(p.stat().st_mtime),
            session_uuid=p.stem,
        )
        for p in sorted_files
    ]
```

**Step 4: Correr tests para verificar que pasan**

```powershell
pytest tests/test_session_detector.py -v
```

Esperado: 4 PASS.

**Step 5: Commit**

```bash
git add src/session_detector.py tests/test_session_detector.py
git commit -m "feat(session): detect active claude session by mtime"
```

---

## Task 3: `formatters.py` — convertir eventos JSON a mensajes Telegram

**Files:**
- Create: `src/formatters.py`
- Create: `tests/test_formatters.py`

**Step 1: Escribir tests fallidos**

`tests/test_formatters.py`:
```python
from src.formatters import format_event, truncate, escape_md_v2


def test_format_assistant_text():
    event = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Hola, soy Claude."}]},
    }
    result = format_event(event)
    assert len(result) == 1
    assert "Hola, soy Claude" in result[0]


def test_format_tool_use_read():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "src/bot.py"}}
            ]
        },
    }
    result = format_event(event)
    assert "📖" in result[0]
    assert "Read" in result[0]
    assert "src/bot.py" in result[0]


def test_format_tool_use_edit():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {
                        "file_path": "src/bot.py",
                        "old_string": "foo",
                        "new_string": "bar",
                    },
                }
            ]
        },
    }
    result = format_event(event)
    assert "✏️" in result[0]
    assert "Edit" in result[0]
    assert "src/bot.py" in result[0]


def test_format_tool_use_bash():
    event = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}}
            ]
        },
    }
    result = format_event(event)
    assert "▶️" in result[0]
    assert "npm test" in result[0]


def test_format_tool_result():
    event = {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "content": "Salida del comando"}
            ]
        },
    }
    result = format_event(event)
    assert "Salida del comando" in result[0]


def test_format_ignores_queue_operations():
    event = {"type": "queue-operation", "operation": "enqueue", "content": "hola"}
    result = format_event(event)
    assert result == []


def test_format_ignores_attachments():
    event = {"type": "attachment", "attachment": {"type": "hook_success"}}
    result = format_event(event)
    assert result == []


def test_truncate_short_text():
    assert truncate("hola", 100) == "hola"


def test_truncate_long_text():
    text = "a" * 5000
    result = truncate(text, 4000)
    assert len(result) <= 4020
    assert "truncado" in result.lower()


def test_escape_md_v2_special_chars():
    result = escape_md_v2("hola_mundo*test")
    assert result == "hola\\_mundo\\*test"
```

**Step 2: Correr tests para verificar que fallan**

```powershell
pytest tests/test_formatters.py -v
```

Esperado: 10 FAIL.

**Step 3: Implementar `src/formatters.py`**

```python
import re
from typing import Any

TG_MD_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!"

TOOL_ICONS = {
    "Read": "📖",
    "Write": "📝",
    "Edit": "✏️",
    "Bash": "▶️",
    "Grep": "🔍",
    "Glob": "📂",
    "WebFetch": "🌐",
    "WebSearch": "🌐",
    "TodoWrite": "📋",
    "Task": "🤖",
}


def escape_md_v2(text: str) -> str:
    return "".join("\\" + c if c in TG_MD_V2_SPECIAL else c for c in text)


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncado)"


def _format_tool_use(name: str, tool_input: dict) -> str:
    icon = TOOL_ICONS.get(name, "🔧")

    if name == "Read":
        return f"{icon} *{name}*: `{tool_input.get('file_path', '?')}`"
    if name == "Write":
        return f"{icon} *{name}*: `{tool_input.get('file_path', '?')}`"
    if name == "Edit":
        path = tool_input.get("file_path", "?")
        old = tool_input.get("old_string", "")[:200]
        new = tool_input.get("new_string", "")[:200]
        return f"{icon} *{name}*: `{path}`\n```diff\n- {old}\n+ {new}\n```"
    if name == "Bash":
        cmd = tool_input.get("command", "")
        return f"{icon} *Bash*:\n```\n{cmd}\n```"
    if name == "Grep":
        return f"{icon} *Grep*: `{tool_input.get('pattern', '?')}`"
    if name == "Glob":
        return f"{icon} *Glob*: `{tool_input.get('pattern', '?')}`"
    if name in ("WebFetch", "WebSearch"):
        return f"{icon} *{name}*: {tool_input.get('url') or tool_input.get('query', '?')}"

    summary = str(tool_input)[:200]
    return f"{icon} *{name}*: `{summary}`"


def _format_tool_result(content: Any) -> str:
    if isinstance(content, list):
        text = "\n".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    else:
        text = str(content)
    text = truncate(text, 3500)
    return f"```\n{text}\n```"


def format_event(event: dict) -> list[str]:
    event_type = event.get("type")

    if event_type in ("queue-operation", "attachment", "summary"):
        return []

    if event_type == "assistant":
        out: list[str] = []
        content = event.get("message", {}).get("content", [])
        for block in content:
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "").strip()
                if text:
                    out.append(truncate(text, 4000))
            elif block_type == "tool_use":
                out.append(_format_tool_use(block.get("name", "?"), block.get("input", {})))
        return out

    if event_type == "user":
        out = []
        content = event.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    out.append(_format_tool_result(block.get("content", "")))
        return out

    return []
```

**Step 4: Correr tests para verificar que pasan**

```powershell
pytest tests/test_formatters.py -v
```

Esperado: 10 PASS.

**Step 5: Commit**

```bash
git add src/formatters.py tests/test_formatters.py
git commit -m "feat(formatters): convert jsonl events to telegram messages"
```

---

## Task 4: `security.py` — whitelist + detección de operaciones destructivas

**Files:**
- Create: `src/security.py`
- Create: `tests/test_security.py`

**Step 1: Escribir tests fallidos**

`tests/test_security.py`:
```python
import pytest
from src.security import is_destructive


@pytest.mark.parametrize("text", [
    "borra el archivo bot.py",
    "elimina la base de datos",
    "rm -rf /tmp/foo",
    "DELETE FROM users",
    "drop table users",
    "vercel --prod",
    "haz deploy a producción",
    "git push --force",
    "force-push al main",
])
def test_is_destructive_detects(text):
    assert is_destructive(text) is True


@pytest.mark.parametrize("text", [
    "lee el archivo bot.py",
    "muéstrame los logs",
    "qué hace este código",
    "explícame la función",
    "agrega un test",
    "crea un nuevo endpoint",
])
def test_is_destructive_safe_strings(text):
    assert is_destructive(text) is False
```

**Step 2: Correr tests para verificar que fallan**

```powershell
pytest tests/test_security.py -v
```

Esperado: FAIL con ImportError.

**Step 3: Implementar `src/security.py`**

```python
import logging
import re
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from src.config import ALLOWED_USER_ID

logger = logging.getLogger(__name__)

DESTRUCTIVE_PATTERNS = [
    r"\bborra\b",
    r"\belimina\b",
    r"\brm\s+-rf?\b",
    r"\bdelete\b",
    r"\bdrop\s+table\b",
    r"\bdrop\b\s+\w+",
    r"\bdeploy\b",
    r"\bvercel\s+--prod\b",
    r"\bgit\s+push\s+(--force|-f)\b",
    r"\bforce[-\s]push\b",
    r"\bproducci[oó]n\b",
    r"\bprod\b",
]

_DESTRUCTIVE_RE = re.compile("|".join(DESTRUCTIVE_PATTERNS), re.IGNORECASE)


def is_destructive(text: str) -> bool:
    return bool(_DESTRUCTIVE_RE.search(text))


def requires_whitelist(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None or update.effective_user.id != ALLOWED_USER_ID:
            uid = update.effective_user.id if update.effective_user else "?"
            logger.warning(f"Unauthorized user {uid} tried to access bot")
            return
        return await handler(update, context)
    return wrapper
```

**Step 4: Correr tests para verificar que pasan**

```powershell
pytest tests/test_security.py -v
```

Esperado: 15 PASS.

**Step 5: Commit**

```bash
git add src/security.py tests/test_security.py
git commit -m "feat(security): whitelist + destructive command detection"
```

---

## Task 5: `claude_controller.py` — UI automation con pywinauto

**Files:**
- Create: `src/claude_controller.py`
- Create: `tests/test_claude_controller_smoke.py` (smoke test manual)

**⚠️ Nota:** No hay TDD acá porque pywinauto requiere la ventana real de Claude Desktop abierta. Se prueba manualmente.

**Step 1: Implementar `src/claude_controller.py`**

```python
import logging
import time
from pywinauto import Application, Desktop
from pywinauto.findwindows import ElementNotFoundError

logger = logging.getLogger(__name__)


class ClaudeControllerError(Exception):
    """Error general del controller."""


class ClaudeNotOpenError(ClaudeControllerError):
    """La app Claude Desktop no está abierta."""


class PCLockedError(ClaudeControllerError):
    """La PC está bloqueada — no se puede interactuar con la UI."""


class ClaudeController:
    WINDOW_TITLE_CONTAINS = "Claude"
    INPUT_NAMES = [
        "Escribe / para comandos",
        "Send a message",
        "Type a message",
    ]

    def find_window(self):
        try:
            windows = Desktop(backend="uia").windows(
                title_re=f".*{self.WINDOW_TITLE_CONTAINS}.*"
            )
            if not windows:
                raise ClaudeNotOpenError("No encontré ninguna ventana de Claude Desktop")
            for w in windows:
                try:
                    if w.is_visible():
                        return w
                except Exception:
                    continue
            raise ClaudeNotOpenError("Hay ventanas de Claude pero ninguna visible")
        except OSError as e:
            raise PCLockedError(f"No puedo acceder a la UI (¿PC bloqueada?): {e}")

    def _find_input(self, window):
        for name in self.INPUT_NAMES:
            try:
                ctrl = window.child_window(title=name, control_type="Edit")
                if ctrl.exists(timeout=2):
                    return ctrl
            except ElementNotFoundError:
                continue
        try:
            edits = window.descendants(control_type="Edit")
            if edits:
                return edits[-1]
        except Exception as e:
            logger.debug(f"Fallback edit search failed: {e}")
        raise ClaudeControllerError("No encontré el input de Claude en la ventana")

    def send(self, text: str) -> None:
        window = self.find_window()
        try:
            window.set_focus()
        except Exception as e:
            raise PCLockedError(f"No puedo enfocar la ventana de Claude: {e}")

        time.sleep(0.3)

        input_ctrl = self._find_input(window)
        input_ctrl.set_focus()
        time.sleep(0.2)

        input_ctrl.type_keys(text, with_spaces=True, with_newlines=False, with_tabs=False)
        time.sleep(0.3)
        input_ctrl.type_keys("{ENTER}")
        logger.info(f"Mensaje enviado a Claude: {text[:80]}...")
```

**Step 2: Crear smoke test manual**

`tests/test_claude_controller_smoke.py`:
```python
"""
Smoke test manual. NO se corre con pytest CI.

Para probar:
1. Abre Claude Code Desktop y haz click en una sesión.
2. Ejecuta: python -m tests.test_claude_controller_smoke
3. Observa que el texto aparezca en el input.
"""
import sys
from src.claude_controller import ClaudeController, ClaudeNotOpenError, PCLockedError


def main():
    ctrl = ClaudeController()
    try:
        ctrl.send("test desde TelegramClaudeBridge — ignora este mensaje")
        print("✅ Enviado")
    except ClaudeNotOpenError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except PCLockedError as e:
        print(f"❌ {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
```

**Step 3: Smoke test manual**

1. Abrir Claude Code Desktop en una sesión cualquiera.
2. Ejecutar:
```powershell
python -m tests.test_claude_controller_smoke
```
3. Verificar que el texto aparece en el input de Claude Desktop.

Esperado: el texto aparece y se presiona Enter.

**Si falla**: revisar nombres de control con `python -c "from pywinauto import Desktop; w = Desktop(backend='uia').windows(title_re='.*Claude.*')[0]; w.print_control_identifiers()"` y ajustar `INPUT_NAMES`.

**Step 4: Commit**

```bash
git add src/claude_controller.py tests/test_claude_controller_smoke.py
git commit -m "feat(controller): UI automation for claude desktop input"
```

---

## Task 6: `transcript_watcher.py` — file watcher del .jsonl

**Files:**
- Create: `src/transcript_watcher.py`
- Create: `tests/test_transcript_watcher.py`

**Step 1: Escribir test fallido**

`tests/test_transcript_watcher.py`:
```python
import asyncio
import json
import time
from pathlib import Path
import pytest

from src.transcript_watcher import TranscriptWatcher


@pytest.mark.asyncio
async def test_watcher_emits_new_lines(tmp_path):
    jsonl = tmp_path / "test.jsonl"
    jsonl.write_text("")

    received: list[dict] = []

    async def on_event(event: dict):
        received.append(event)

    watcher = TranscriptWatcher(tmp_path, on_event)
    watcher.start()
    watcher.set_active_file(jsonl)

    await asyncio.sleep(0.3)

    with open(jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "text": "hola"}) + "\n")
        f.flush()

    await asyncio.sleep(1.0)

    watcher.stop()

    assert len(received) >= 1
    assert received[0]["type"] == "assistant"
```

**Step 2: Correr test para verificar que falla**

```powershell
pytest tests/test_transcript_watcher.py -v
```

Esperado: FAIL con ImportError.

**Step 3: Implementar `src/transcript_watcher.py`**

```python
import asyncio
import json
import logging
from pathlib import Path
from typing import Awaitable, Callable
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], Awaitable[None]]


class _JsonlHandler(FileSystemEventHandler):
    def __init__(self, watcher: "TranscriptWatcher"):
        self.watcher = watcher

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".jsonl":
            asyncio.run_coroutine_threadsafe(
                self.watcher._on_file_modified(path),
                self.watcher.loop,
            )


class TranscriptWatcher:
    def __init__(self, projects_dir: Path, on_event: EventCallback):
        self.projects_dir = projects_dir
        self.on_event = on_event
        self._observer: Observer | None = None
        self._active_file: Path | None = None
        self._last_offset: int = 0
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def start(self) -> None:
        if self._observer is not None:
            return
        self._observer = Observer()
        self._observer.schedule(_JsonlHandler(self), str(self.projects_dir), recursive=True)
        self._observer.start()
        logger.info(f"Watcher started on {self.projects_dir}")

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def set_active_file(self, path: Path) -> None:
        if self._active_file == path:
            return
        self._active_file = path
        self._last_offset = path.stat().st_size if path.exists() else 0
        logger.info(f"Now watching: {path}")

    async def _on_file_modified(self, path: Path) -> None:
        if path != self._active_file:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(self._last_offset)
                new_data = f.read()
                self._last_offset = f.tell()

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug(f"Skipping malformed JSON line: {line[:100]}")
                    continue
                await self.on_event(event)
        except Exception as e:
            logger.exception(f"Error processing {path}: {e}")
```

**Step 4: Correr test para verificar que pasa**

```powershell
pytest tests/test_transcript_watcher.py -v
```

Esperado: PASS.

**Step 5: Commit**

```bash
git add src/transcript_watcher.py tests/test_transcript_watcher.py
git commit -m "feat(watcher): tail jsonl files in real-time"
```

---

## Task 7: `bot.py` — entrypoint del bot de Telegram

**Files:**
- Create: `src/bot.py`

**⚠️ Nota:** No hay tests automatizados acá — es el integration point. Se valida con smoke test E2E en Task 8.

**Step 1: Implementar `src/bot.py`**

```python
import asyncio
import logging
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.claude_controller import ClaudeController, ClaudeNotOpenError, PCLockedError
from src.config import CLAUDE_PROJECTS_DIR, TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
from src.formatters import format_event
from src.security import is_destructive, requires_whitelist
from src.session_detector import detect_active_session, list_recent_sessions
from src.transcript_watcher import TranscriptWatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class BotState:
    def __init__(self):
        self.paused: bool = False
        self.pending_confirmations: dict[str, str] = {}
        self.controller = ClaudeController()


state = BotState()


@requires_whitelist
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active:
        msg = f"👋 Hola Reimo. Sesión activa: `{active.parent.name}`"
    else:
        msg = "👋 Hola Reimo. No detecté ninguna sesión activa. Abre Claude Desktop."
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    paused = "⏸️ pausado" if state.paused else "▶️ activo"
    msg = f"Estado: {paused}\nSesión: `{active.parent.name if active else '(ninguna)'}`"
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_sesiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions = list_recent_sessions(CLAUDE_PROJECTS_DIR, limit=10)
    if not sessions:
        await update.message.reply_text("No hay sesiones recientes.")
        return
    lines = ["📋 *Sesiones recientes:*"]
    for s in sessions:
        lines.append(f"• `{s.folder_name}` ({s.last_modified:%H:%M:%S})")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.paused = True
    await update.message.reply_text("⏸️ Reenvío pausado. /seguir para reanudar.")


@requires_whitelist
async def cmd_seguir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.paused = False
    await update.message.reply_text("▶️ Reenvío reanudado.")


@requires_whitelist
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *TelegramClaudeBridge*\n\n"
        "/start - bienvenida + sesión activa\n"
        "/estado - estado del bot\n"
        "/sesiones - lista sesiones recientes\n"
        "/parar - pausa el reenvío\n"
        "/seguir - reanuda el reenvío\n"
        "/ayuda - este mensaje\n\n"
        "Cualquier mensaje sin slash se envía a Claude."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


def _confirmation_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, mandar", callback_data=f"confirm:yes:{token}"),
        InlineKeyboardButton("❌ No, cancelar", callback_data=f"confirm:no:{token}"),
    ]])


@requires_whitelist
async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if is_destructive(text):
        import uuid
        token = uuid.uuid4().hex[:8]
        state.pending_confirmations[token] = text
        await update.message.reply_text(
            f"⚠️ Detecté palabras destructivas (deploy/borrar/etc).\n\n"
            f"Mensaje: _{text[:200]}_\n\n¿Confirmas?",
            reply_markup=_confirmation_keyboard(token),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await _send_to_claude(update, text)


async def _send_to_claude(update: Update, text: str):
    try:
        state.controller.send(text)
        await update.message.reply_text("✉️ Enviado a Claude. Esperando respuesta...")
    except ClaudeNotOpenError as e:
        await update.message.reply_text(f"❌ {e}")
    except PCLockedError as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error enviando a Claude")
        await update.message.reply_text(f"❌ Error inesperado: {e}")


@requires_whitelist
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "confirm":
        return
    decision, token = parts[1], parts[2]
    text = state.pending_confirmations.pop(token, None)
    if not text:
        await query.edit_message_text("⚠️ Confirmación expirada.")
        return
    if decision == "yes":
        await query.edit_message_text(f"✅ Confirmado, enviando...\n_{text[:200]}_",
                                       parse_mode=ParseMode.MARKDOWN)
        try:
            state.controller.send(text)
        except Exception as e:
            await query.message.reply_text(f"❌ {e}")
    else:
        await query.edit_message_text("❌ Cancelado.")


async def _forward_event_to_telegram(app: Application, event: dict):
    if state.paused:
        return
    messages = format_event(event)
    for msg in messages:
        try:
            await app.bot.send_message(
                chat_id=ALLOWED_USER_ID,
                text=msg,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await app.bot.send_message(chat_id=ALLOWED_USER_ID, text=msg)


async def _watch_active_session(app: Application, watcher: TranscriptWatcher):
    while True:
        active = detect_active_session(CLAUDE_PROJECTS_DIR)
        if active and active != watcher._active_file:
            watcher.set_active_file(active)
            if watcher._active_file is not None:
                await app.bot.send_message(
                    chat_id=ALLOWED_USER_ID,
                    text=f"ℹ️ Cambié al seguimiento de sesión: `{active.parent.name}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
        await asyncio.sleep(5)


async def post_init(app: Application):
    async def on_event(event: dict):
        await _forward_event_to_telegram(app, event)

    watcher = TranscriptWatcher(CLAUDE_PROJECTS_DIR, on_event)
    watcher.start()
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active:
        watcher.set_active_file(active)
    asyncio.create_task(_watch_active_session(app, watcher))
    app.bot_data["watcher"] = watcher


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("sesiones", cmd_sesiones))
    app.add_handler(CommandHandler("parar", cmd_parar))
    app.add_handler(CommandHandler("seguir", cmd_seguir))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^confirm:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))

    logger.info("Bot iniciando...")
    app.run_polling()


if __name__ == "__main__":
    main()
```

**Step 2: Commit (todavía sin probar — eso es Task 8)**

```bash
git add src/bot.py
git commit -m "feat(bot): telegram bot entrypoint with handlers"
```

---

## Task 8: Crear bot de Telegram + configurar `.env` (paso manual del usuario)

**⚠️ Esta tarea es para Reimo, no para Claude.**

**Step 1: Crear bot en Telegram**

1. Abre Telegram, busca `@BotFather`.
2. Envía `/newbot`.
3. Sigue las instrucciones (nombre, username terminado en `bot`).
4. Copia el TOKEN que te da (formato `123456:ABC-DEF...`).

**Step 2: Obtener tu user_id**

1. En Telegram, busca `@userinfobot`.
2. Pulsa `/start`.
3. Te devuelve tu user_id (un número de ~10 dígitos).

**Step 3: Editar `.env`**

Reemplazar los placeholders en `C:\Users\Reimo\Desktop\pyton pantalla\.env`:
```
TELEGRAM_BOT_TOKEN=el_token_de_botfather
TELEGRAM_ALLOWED_USER_ID=tu_user_id_de_userinfobot
CLAUDE_PROJECTS_DIR=C:\Users\Reimo\.claude\projects
```

**Step 4: Confirmar que no tienes `ANTHROPIC_API_KEY` en tu entorno**

```powershell
echo $env:ANTHROPIC_API_KEY
```

Si imprime algo, ejecutar:
```powershell
Remove-Item Env:\ANTHROPIC_API_KEY
```

(No se usa en este bot — la app Claude Desktop ya tiene tu plan Max.)

---

## Task 9: Crear `run.bat` y smoke test E2E

**Files:**
- Create: `run.bat`

**Step 1: Crear `run.bat`**

```bat
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m src.bot
pause
```

**Step 2: Smoke test end-to-end**

1. Abrir Claude Code Desktop en cualquier sesión.
2. Doble-click en `run.bat`.
3. Verificar que aparece `Bot iniciando...` y `Watcher started on ...`.
4. En Telegram, abrir el chat con el bot y enviar `/start`.
   - Esperado: respuesta con bienvenida + nombre de sesión activa.
5. Enviar `/sesiones`.
   - Esperado: lista de sesiones recientes.
6. Enviar un mensaje normal: `"hola, dime qué hora es"`.
   - Esperado:
     - Respuesta del bot: `"✉️ Enviado a Claude. Esperando respuesta..."`
     - El mensaje aparece escrito en la ventana de Claude Desktop.
     - Claude empieza a responder en la ventana.
     - Los mensajes de Claude llegan a Telegram conforme se escriben.
7. Probar destructivo: `"haz deploy a producción"`.
   - Esperado: aparecen botones `[✅ Sí, mandar]` `[❌ No, cancelar]`.
8. Pulsar `❌ No, cancelar`.
   - Esperado: bot responde `"❌ Cancelado."`, nada se envía a Claude.

**Step 3: Commit**

```bash
git add run.bat
git commit -m "feat: add run.bat for easy startup"
```

---

## Task 10: README de uso

**Files:**
- Create: `README.md`

**Step 1: Crear `README.md`**

```markdown
# TelegramClaudeBridge

Bot Python que reenvía la sesión activa de **Claude Code Desktop** entre tu PC y Telegram.
Permite controlar Claude desde tu celular cuando no estás en casa, usando tu plan Max
(sin costos de API).

## Cómo usar

1. Asegúrate de tener Claude Code Desktop abierto en la sesión que quieras usar.
2. Doble-click en `run.bat` (o ejecutar `python -m src.bot` con el venv activado).
3. En Telegram, escribe `/start` al bot.
4. Cualquier mensaje sin slash se envía a Claude.
5. Las respuestas de Claude llegan al chat de Telegram conforme se escriben.

## Comandos

- `/start` - bienvenida + sesión activa detectada
- `/estado` - estado del bot
- `/sesiones` - lista de sesiones recientes
- `/parar` - pausa el reenvío
- `/seguir` - reanuda
- `/ayuda` - lista de comandos

## Limitaciones (v1)

- La PC debe estar prendida y desbloqueada.
- Claude Code Desktop debe estar abierto (en cualquier sesión).
- Solo el `TELEGRAM_ALLOWED_USER_ID` del .env puede usar el bot.
- Los mensajes con palabras destructivas (`deploy`, `borra`, `rm`, etc.) requieren
  confirmación Sí/No antes de enviarse.

## Diseño

Ver [docs/plans/2026-05-13-telegram-claude-bridge-design.md](docs/plans/2026-05-13-telegram-claude-bridge-design.md).
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README"
```

---

## Resumen de tasks

| # | Tarea | TDD | Manual |
|---|---|---|---|
| 0 | Bootstrap proyecto (venv, deps, git) | — | ✓ |
| 1 | `config.py` (cargar .env) | ✓ | — |
| 2 | `session_detector.py` (detectar sesión activa) | ✓ | — |
| 3 | `formatters.py` (JSON → Telegram) | ✓ | — |
| 4 | `security.py` (whitelist + destructivos) | ✓ | — |
| 5 | `claude_controller.py` (UI automation) | — | ✓ |
| 6 | `transcript_watcher.py` (file watcher) | ✓ | — |
| 7 | `bot.py` (entrypoint Telegram) | — | — |
| 8 | Crear bot + `.env` | — | ✓ |
| 9 | `run.bat` + smoke test E2E | — | ✓ |
| 10 | README | — | — |

**Total estimado**: 4-6 horas de implementación + 30 min de setup manual (bot Telegram, .env).
