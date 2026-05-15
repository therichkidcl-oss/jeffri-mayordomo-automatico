# Jeffri — Guía para Claude

Este archivo te guía (a vos, Claude) para auto-instalar este proyecto en una PC nueva. Si el usuario te dice "instálame Jeffri" o "configurá este repo", seguí estos pasos en orden.

## Contexto del proyecto

**Jeffri** es un bot Python que conecta Telegram con Claude Code Desktop. El usuario manda mensajes/voz/fotos por Telegram, Jeffri los recibe en la PC, los procesa (mejora prompts con Groq, transcribe audios con Whisper) y los pega en la ventana activa de Claude Code Desktop. Las respuestas de Claude se reenvían al chat de Telegram.

- Entry point: `src/bot.py`
- Plataforma: Windows 10/11 (usa pywinauto, win32api, win32clipboard)
- Python: 3.13+
- Diseño completo: `docs/plans/2026-05-13-telegram-claude-bridge-design.md`

## Instrucciones de auto-instalación

Si el usuario pide instalar el proyecto, ejecutá estos pasos. Pedí confirmación antes de cada paso destructivo o cuando necesités información del usuario.

### Paso 1: Verificar requisitos

```powershell
python --version       # Debe ser 3.13 o mayor
where claude           # Debe existir Claude Code Desktop
```

Si Python falta, pedirle al usuario que lo instale desde https://www.python.org/downloads/.
Si Claude Code Desktop falta, pedirle que lo instale desde https://claude.com/download.

### Paso 2: Setup del entorno

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell rechaza el activate por política de ejecución:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Paso 3: Configurar `.env`

```powershell
Copy-Item .env.example .env
```

Pedile al usuario:
1. El **token del bot de Telegram** (lo obtiene de @BotFather con `/newbot`).
2. Su **user_id de Telegram** (lo obtiene de @userinfobot con `/start`).
3. (Opcional) **API keys de Groq** separadas por coma (de https://console.groq.com/keys).

Editá `.env` con esos valores. Confirmá que `CLAUDE_PROJECTS_DIR` apunta a la carpeta `.claude/projects` del usuario (típicamente `C:\Users\<USUARIO>\.claude\projects`).

### Paso 4: Verificar la instalación

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Debe pasar 48 tests. Si alguno falla, revisá el error y corregí antes de continuar.

```powershell
.\.venv\Scripts\python.exe -c "import src.bot; print('Import OK')"
```

Debe imprimir `Import OK`. Si falla, hay un problema con `.env` o las dependencias.

### Paso 5: Primera ejecución

Decirle al usuario que:
1. **Abra Claude Code Desktop** en cualquier sesión que NO sea esta misma (para no crear loop).
2. **Doble-click en `run.bat`** o ejecutar `.\.venv\Scripts\python.exe -m src.bot` desde terminal.
3. **En Telegram, mandar `/start`** al bot. Debe responder con la sesión activa.

Si todo eso funciona, la instalación está completa.

## Convenciones del código

### Idioma
- **El usuario habla español latino neutro con "tú"** (no voseo argentino).
- **El usuario quiere ser tratado como "Sir Rich"** en respuestas.
- Comentarios en código pueden ir en español o inglés indistintamente.

### Estructura
```
src/
├── bot.py                  # entrypoint, handlers Telegram
├── config.py               # carga .env
├── claude_controller.py    # UI automation + OCR + click
├── transcript_watcher.py   # vigila .jsonl
├── formatters.py           # eventos JSON → mensajes Telegram
├── groq_client.py          # enhancer + Whisper
├── security.py             # whitelist + detección destructiva
└── session_detector.py     # detecta sesión activa + proyectos
tests/
docs/plans/                 # diseño y plan original
```

### Patrón de tests
TDD por módulo. Tests en `tests/test_<modulo>.py`. Usar `monkeypatch` para variables de entorno y `tmp_path` para archivos.

### Subprocesos UI
Todas las operaciones de pywinauto/clipboard/click corren en threads via `asyncio.to_thread`. Nunca bloquees el loop de asyncio con calls síncronos de UI.

### Sin API keys de Anthropic
Este bot usa el plan Max via Claude Code Desktop. NO usa ANTHROPIC_API_KEY. Si el usuario intenta configurarla, decile que no hace falta.

## Comandos útiles para mantenimiento

```powershell
# Tests rápidos
.\.venv\Scripts\python.exe -m pytest -q

# Tests verbose
.\.venv\Scripts\python.exe -m pytest -v

# Solo un módulo
.\.venv\Scripts\python.exe -m pytest tests/test_formatters.py -v

# Arrancar el bot
.\.venv\Scripts\python.exe -m src.bot

# Verificar import sin arrancar
.\.venv\Scripts\python.exe -c "import src.bot; print('OK')"
```

## Cuando el usuario pida features nuevas

Antes de implementar:
1. Usá la skill `superpowers:brainstorming` si la feature es no trivial.
2. Hacé un plan corto en un archivo o en `docs/plans/` si es grande.
3. Confirmá con el usuario antes de tocar código.

Durante implementación:
1. TDD donde sea posible.
2. Tests deben pasar antes del commit.
3. Commits descriptivos con `feat:`, `fix:`, `refactor:`, etc.
4. Cada commit debe dejar el sistema en estado funcional.

## Reglas inflexibles

- **NUNCA commitear `.env`**. Si lo ves en `git status`, abortá inmediatamente.
- **NUNCA logear el token de Telegram en plain text**. Truncalo (`token[:10]+"..."+token[-4:]`).
- **NUNCA push a `main`/`master`** sin confirmación explícita del usuario.
- **NUNCA usar voseo argentino** al hablar con el usuario.
- **SIEMPRE tratar al usuario como "Sir Rich"** en mensajes generados para él.

## Estado actual del proyecto

Versión: v1 funcional, todos los módulos integrados.
Última verificación: 48/48 tests pasan.
Plataforma probada: Windows 11 con Python 3.14, Claude Code Desktop 2.1.x.

---

🎩 *Cualquier duda durante la instalación, preguntá al usuario antes de adivinar.*
