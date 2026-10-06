# Jeffri — Guia para Claude Code (auto-instalacion asistida)

Este archivo te guia a ti (**la IA Claude Code**) para instalar Jeffri en la
PC de un usuario cuando el te lo pida.

## Resumen del proyecto

**Jeffri** es un bot que conecta Telegram con Claude Code Desktop. El usuario
le manda mensajes (texto/voz/foto) por Telegram, Jeffri los pule con DeepSeek,
los pega en Claude Code Desktop via UI automation, y reenvia las respuestas
de Claude de vuelta a Telegram. Opcionalmente tambien activa un push-to-talk
F9 para hablarle con voz local (Whisper + Piper).

- **Plataforma**: Windows 10/11 (usa `pywinauto`, `win32api`, `win32clipboard`,
  `winocr`). Linux/Mac NO soportados.
- **Python**: 3.13+.
- **Entry point recomendado**: `python -m src.main` (Telegram + voz).
- **Alternativa sin voz**: `python -m src.bot`.

## Flujo de auto-instalacion

Cuando el usuario te diga *"instalame Jeffri"*, *"configura Jeffri en mi PC"*
o algo equivalente, sigue estos pasos **en orden**. Pide confirmacion antes
de pasos destructivos o cuando necesites un dato que solo el usuario tiene.

### Paso 1 — Verificar requisitos

```powershell
python --version
```
Debe decir `Python 3.13.x` o superior. Si falta o es menor, pide al usuario
que lo instale desde https://www.python.org/downloads/ (Windows installer,
marcar "Add Python to PATH").

```powershell
Test-Path "$env:LOCALAPPDATA\Programs\claude-code"
```
Si devuelve `False`, Claude Code Desktop no esta instalado. Pide al usuario
que lo instale desde https://claude.com/download.

```powershell
Test-Path "$env:USERPROFILE\.claude\projects"
```
Debe devolver `True`. Si no, el usuario nunca abrio Claude Code Desktop —
pidele que lo abra una vez.

### Paso 2 — Clonar el repo

Si ya estas dentro del repo (el usuario clono manualmente), salta este paso.
Si no:

```powershell
cd $env:USERPROFILE\Desktop
git clone https://github.com/therichkidcl-spec/jeffri-mayordomo-automatico.git
cd jeffri-mayordomo-automatico
```

### Paso 3 — Crear entorno virtual e instalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell bloquea el activate, el usuario necesita una sola vez:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Paso 4 — Configurar `.env`

```powershell
Copy-Item .env.example .env
```

Ahora **pide al usuario los siguientes datos** y edita `.env`:

1. **Token del bot de Telegram** (`TELEGRAM_BOT_TOKEN`).
   Instrucciones para el usuario:
   > *"En Telegram abre @BotFather, escribe `/newbot`, elige nombre y
   > username (debe terminar en 'bot'). Te dara un token tipo
   > `123456789:ABC-DEF...`. Pegamelo aqui."*

2. **User_id de Telegram** (`TELEGRAM_ALLOWED_USER_ID`).
   > *"En Telegram abre @userinfobot y escribe `/start`. Te dara un numero
   > de ~10 digitos. Pegamelo aqui."*

3. **Ruta de proyectos de Claude** (`CLAUDE_PROJECTS_DIR`).
   Puedes autocompletarla con el user actual:
   ```powershell
   "$env:USERPROFILE\.claude\projects"
   ```
   Verifica que exista y usala.

4. **DeepSeek API key** (`DEEPSEEK_API_KEY`, opcional pero recomendado).
   > *"Para que Jeffri pula tus mensajes antes de pegarlos en Claude,
   > necesita una API key de DeepSeek. Es gratis crear cuenta en
   > https://platform.deepseek.com/api_keys. ¿Quieres saltarte esto por ahora?
   > Si saltas, el bot pega los mensajes crudos (igual funciona)."*

Nunca inventes valores; siempre pide al usuario que te los pase. Usa
`Edit` tool para ir rellenando `.env` campo por campo.

### Paso 5 — Verificar la instalacion

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Debe decir `142 passed`. Si algun test falla, lee el output y arregla antes
de continuar — probablemente es un valor mal puesto en `.env` o una
dependencia que no instalo bien.

```powershell
.\.venv\Scripts\python.exe -c "import src.bot; print('Import OK')"
```

Debe imprimir `Import OK` precedido por un log que diga `DeepSeek habilitado`
(si pusiste la API key). Si falla, hay un error de config.

### Paso 6 — Primera ejecucion

Dile al usuario:

1. **Abre Claude Code Desktop** en cualquier sesion que NO sea la actual
   (si lo instalaste tu mismo guiando al usuario, salte esa sesion).
2. **Doble-click en `run.bat`** O desde terminal:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m src.main
   ```
3. **En Telegram, mandale `/start` al bot que creaste**. Jeffri te preguntara
   como quieres que te trate — responde con tu titulo honorifico preferido
   (`Sir Smith`, `Jefa`, `Doctor`, lo que quieras).

Si Jeffri responde con un saludo que te menciona por tu titulo, la
instalacion termino.

## Convenciones del codigo

### Idioma
- El bot comunica en **espanol latino con "tu"** (nunca voseo argentino).
- Comentarios en codigo: espanol o ingles indistintamente.
- Prohibido: `vos`, `tenes`, `queres`, `podes`, `dale`, `che`, etc. Usa `tu
  tienes`, `tu puedes`, `tu haces`.
- Tono del bot: mayordomo sumiso. Nunca uses "Sir Rich" ni ningun titulo
  hardcoded — usa `state.address()` que resuelve el titulo que el usuario
  configuro (fallback: `"mi senor"`).

### Estructura
```
src/
├── bot.py                  entrypoint Telegram + handlers
├── main.py                 entrypoint unificado (Telegram + voz)
├── config.py               carga .env
├── user_settings.py        persistencia del titulo honorifico
├── enhancer.py             DeepSeek V4.1-Flash para pulir prompts
├── stt.py                  faster-whisper local para transcribir audio
├── voice/                  loop de voz F9 (DeepSeek + Piper)
├── claude_controller.py    pywinauto + OCR + click en Claude Desktop
├── transcript_watcher.py   watchdog sobre .jsonl de Claude
├── formatters.py           eventos → mensajes de Telegram
├── session_detector.py     que sesion/proyecto usar
├── security.py             whitelist + deteccion destructiva
├── pidfile.py              single-instance lock
└── groq_client.py          (dead code — se dejo por si vuelven a usarlo)
tests/
docs/plans/                 diseno y planes historicos
```

### Tests
TDD por modulo. Tests en `tests/test_<modulo>.py`. Usa `monkeypatch` para
env vars y `tmp_path` para archivos.

### Threads vs asyncio
Todas las operaciones de UI (pywinauto, clipboard, OCR, win32) corren en
threads via `asyncio.to_thread`. **Nunca bloquees el loop de asyncio** con
operaciones sincronas de UI.

### Sin API keys de Anthropic
Jeffri usa el plan Max del usuario via Claude Code Desktop. **NO usa
`ANTHROPIC_API_KEY`**. Si el usuario intenta configurarla, dile que no hace
falta.

## Comandos utiles de mantenimiento

```powershell
# Tests rapidos
.\.venv\Scripts\python.exe -m pytest -q

# Tests verbose
.\.venv\Scripts\python.exe -m pytest -v

# Solo un modulo
.\.venv\Scripts\python.exe -m pytest tests/test_enhancer.py -v

# Arrancar bot (Telegram + voz)
.\.venv\Scripts\python.exe -m src.main

# Arrancar bot (solo Telegram)
.\.venv\Scripts\python.exe -m src.bot

# Verificar import sin arrancar
.\.venv\Scripts\python.exe -c "import src.bot; print('OK')"
```

### Si hay que reiniciar el bot

El bot NO tiene hot-reload. Para aplicar cambios de codigo:

```powershell
# 1. Mata los procesos del bot
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" | Where-Object { $_.CommandLine -match 'src\.(bot|main)' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# 2. Borra el pidfile (atexit no corre con -Force)
Remove-Item logs\jeffri.pid -ErrorAction SilentlyContinue

# 3. Arranca de nuevo
.\.venv\Scripts\python.exe -m src.main
```

## Cuando el usuario pida features nuevos

1. Si es feature no trivial, usa la skill `superpowers:brainstorming`.
2. Haz un plan corto en `docs/plans/YYYY-MM-DD-<slug>.md` si es grande.
3. Confirma con el usuario antes de tocar codigo.
4. TDD donde sea posible. Tests deben pasar antes del commit.
5. Commits descriptivos (`feat:`, `fix:`, `refactor:`).
6. Cada commit debe dejar el sistema en estado funcional.

## Reglas inflexibles

- **NUNCA commitees `.env`**. Si lo ves en `git status`, aborta.
- **NUNCA commitees `data/user_settings.json`** — es local del usuario.
- **NUNCA logees el token de Telegram en plain text**. Truncalo
  (`token[:10]+"..."+token[-4:]`).
- **NUNCA push a `main`/`master`** sin confirmacion explicita del usuario.
- **NUNCA uses voseo argentino** al hablar con el usuario.
- **NUNCA hardcodes un titulo honorifico**. Usa `state.address()` o
  `self.user_title`.

---

🎩 *Cualquier duda durante la instalacion, pregunta al usuario antes de adivinar.*
