# Jeffri — Guia para Claude

Este archivo te guia (a ti, Claude) para auto-instalar este proyecto en una PC nueva. Si el usuario te dice "instalame Jeffri" o "configura este repo", sigue estos pasos en orden.

## Contexto del proyecto

**Jeffri** es un bot Python que conecta Telegram con Claude Code Desktop. El usuario manda mensajes/voz/fotos por Telegram, Jeffri los recibe en la PC, los procesa (mejora prompts con Groq, transcribe audios con Whisper) y los pega en la ventana activa de Claude Code Desktop. Las respuestas de Claude se reenvian al chat de Telegram.

- Entry point: `src/bot.py`
- Plataforma: Windows 10/11 (usa pywinauto, win32api, win32clipboard)
- Python: 3.13+
- Diseno completo: `docs/plans/2026-05-13-telegram-claude-bridge-design.md`

## Instrucciones de auto-instalacion

Si el usuario pide instalar el proyecto, ejecuta estos pasos. Pide confirmacion antes de cada paso destructivo o cuando necesites informacion del usuario.

### Paso 1: Verificar requisitos

```powershell
python --version       # Debe ser 3.13 o mayor
where claude           # Debe existir Claude Code Desktop
```

Si Python falta, pide al usuario que lo instale desde https://www.python.org/downloads/.
Si Claude Code Desktop falta, pide que lo instale desde https://claude.com/download.

### Paso 2: Setup del entorno

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell rechaza el activate por politica de ejecucion:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Paso 3: Configurar `.env`

```powershell
Copy-Item .env.example .env
```

Pide al usuario:
1. El **token del bot de Telegram** (lo obtiene de @BotFather con `/newbot`).
2. Su **user_id de Telegram** (lo obtiene de @userinfobot con `/start`).
3. (Opcional) **API keys de Groq** separadas por coma (de https://console.groq.com/keys).

Edita `.env` con esos valores. Confirma que `CLAUDE_PROJECTS_DIR` apunta a la carpeta `.claude/projects` del usuario (tipicamente `C:\Users\<USUARIO>\.claude\projects`).

### Paso 4: Verificar la instalacion

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Debe pasar 48 tests. Si alguno falla, revisa el error y corrige antes de continuar.

```powershell
.\.venv\Scripts\python.exe -c "import src.bot; print('Import OK')"
```

Debe imprimir `Import OK`. Si falla, hay un problema con `.env` o las dependencias.

### Paso 5: Primera ejecucion

Dile al usuario que:
1. **Abra Claude Code Desktop** en cualquier sesion que NO sea esta misma (para no crear loop).
2. **Doble-click en `run.bat`** o ejecutar `.\.venv\Scripts\python.exe -m src.bot` desde terminal.
3. **En Telegram, mandar `/start`** al bot. Debe responder con la sesion activa.

Si todo eso funciona, la instalacion esta completa.

## Convenciones del codigo

### Idioma
- **El usuario habla espanol latino neutro con "tu"** (no voseo argentino).
- **El usuario quiere ser tratado como "Sir Rich"** en respuestas.
- Comentarios en codigo pueden ir en espanol o ingles indistintamente.
- **Nada de voseo**: prohibido "vos", "tenes", "queres", "podes", "dale", "che", "andate", "mira" como imperativo, etc. Usa "tu tienes", "tu quieres", "tu puedes", "tu haces".

### Estructura
```
src/
├── bot.py                  # entrypoint, handlers Telegram
├── config.py               # carga .env
├── claude_controller.py    # UI automation + OCR + click
├── transcript_watcher.py   # vigila .jsonl
├── formatters.py           # eventos JSON → mensajes Telegram
├── groq_client.py          # enhancer + Whisper
├── security.py             # whitelist + deteccion destructiva
└── session_detector.py     # detecta sesion activa + proyectos
tests/
docs/plans/                 # diseno y plan original
```

### Patron de tests
TDD por modulo. Tests en `tests/test_<modulo>.py`. Usa `monkeypatch` para variables de entorno y `tmp_path` para archivos.

### Subprocesos UI
Todas las operaciones de pywinauto/clipboard/click corren en threads via `asyncio.to_thread`. Nunca bloquees el loop de asyncio con calls sincronos de UI.

### Sin API keys de Anthropic
Este bot usa el plan Max via Claude Code Desktop. NO usa ANTHROPIC_API_KEY. Si el usuario intenta configurarla, dile que no hace falta.

## Comandos utiles para mantenimiento

```powershell
# Tests rapidos
.\.venv\Scripts\python.exe -m pytest -q

# Tests verbose
.\.venv\Scripts\python.exe -m pytest -v

# Solo un modulo
.\.venv\Scripts\python.exe -m pytest tests/test_formatters.py -v

# Arrancar el bot
.\.venv\Scripts\python.exe -m src.bot

# Verificar import sin arrancar
.\.venv\Scripts\python.exe -c "import src.bot; print('OK')"
```

## Cuando el usuario pida features nuevas

Antes de implementar:
1. Usa la skill `superpowers:brainstorming` si la feature es no trivial.
2. Haz un plan corto en un archivo o en `docs/plans/` si es grande.
3. Confirma con el usuario antes de tocar codigo.

Durante implementacion:
1. TDD donde sea posible.
2. Tests deben pasar antes del commit.
3. Commits descriptivos con `feat:`, `fix:`, `refactor:`, etc.
4. Cada commit debe dejar el sistema en estado funcional.

## Reglas inflexibles

- **NUNCA commitear `.env`**. Si lo ves en `git status`, aborta inmediatamente.
- **NUNCA logear el token de Telegram en plain text**. Truncalo (`token[:10]+"..."+token[-4:]`).
- **NUNCA push a `main`/`master`** sin confirmacion explicita del usuario.
- **NUNCA usar voseo argentino** al hablar con el usuario.
- **SIEMPRE tratar al usuario como "Sir Rich"** en mensajes generados para el.

## Estado actual del proyecto

Version: v1 funcional, todos los modulos integrados.
Ultima verificacion: 48/48 tests pasan.
Plataforma probada: Windows 11 con Python 3.14, Claude Code Desktop 2.1.x.

---

🎩 *Cualquier duda durante la instalacion, pregunta al usuario antes de adivinar.*
