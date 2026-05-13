# TelegramClaudeBridge — Diseño

**Fecha**: 2026-05-13
**Autor**: Reimo + Claude
**Estado**: Aprobado, listo para implementar

## Objetivo

Un bot Python que permite a Reimo controlar su sesión activa de **Claude Code Desktop** desde Telegram cuando no está en casa. El bot reenvía a Telegram lo que Claude escribe (incluyendo tool calls al detalle) y envía a Claude lo que Reimo escribe en Telegram. Usa el plan Max — sin costos de API.

## No-objetivos (v1)

- No reemplaza Claude Dispatch ni Cowork.
- No abre sesiones paralelas: opera sobre la sesión que ya está abierta en la app Claude Code Desktop.
- No cambia de sesión por Telegram (eso es v2).
- No funciona si la PC está apagada o bloqueada con Win+L.

## Arquitectura

```
                  Celular (Telegram)
                          ↓ ↑
                  ┌────────────────┐
                  │   bot.py       │
                  │   (Python)     │
                  └────────────────┘
                  ↓                ↑
       ┌──────────────────┐  ┌──────────────────────┐
       │ claude_          │  │ transcript_watcher   │
       │ controller.py    │  │ .py                  │
       │ (pywinauto:      │  │ (watchdog: vigila    │
       │ escribe en       │  │ archivo .jsonl en    │
       │ ventana)         │  │ tiempo real)         │
       └──────────────────┘  └──────────────────────┘
                  ↓                ↑
       ┌───────────────────────────────────────────┐
       │  Claude Code Desktop (app abierta)        │
       │  Sesión activa en una carpeta             │
       └───────────────────────────────────────────┘
                  ↓ (escribe transcript)
       C:\Users\Reimo\.claude\projects\
            C--Users-Reimo-Desktop-<carpeta>\
            <session-uuid>.jsonl
```

## Decisiones técnicas

### Output: leer `.jsonl` en tiempo real (no OCR)

Claude Code Desktop escribe TODO lo que pasa en una sesión a un archivo JSON Lines en:
```
C:\Users\Reimo\.claude\projects\<encoded-folder-path>\<session-uuid>.jsonl
```

Donde `<encoded-folder-path>` es la ruta del cwd con `\` y `/` reemplazados por `-`. Ejemplo: `C:\Users\Reimo\Desktop\pyton pantalla` → `C--Users-Reimo-Desktop-pyton-pantalla`.

Cada línea es un evento JSON con `type`, `timestamp`, `sessionId`, y un cuerpo según el tipo (mensaje del asistente, tool use, tool result, error, etc.).

**Ventaja**: precisión 100%, sin OCR, sin depender de scroll o ventana visible. Vemos cada chunk de streaming conforme se escribe.

### Input: UI automation con `pywinauto`

El `.jsonl` es solo un log — la app no lee ese archivo para detectar input. Para inyectar mensajes:
1. Encontrar el proceso de Claude Code Desktop con `pywinauto.Application(backend="uia")`.
2. Localizar la ventana principal.
3. Encontrar el input "Escribe / para comandos" (textbox dentro del DOM accesible).
4. Hacer foco, escribir el texto, presionar Enter.

**Alternativa descartada**: `pyautogui` con coordenadas hardcoded. Demasiado frágil ante cambios de layout. `pywinauto` con UI Automation lee el árbol de elementos por nombre/tipo, es mucho más robusto.

### Detección de sesión activa

El bot escanea `C:\Users\Reimo\.claude\projects\` recursivamente buscando todos los `.jsonl`. Elige el de `mtime` (modification time) más reciente. Esa es la sesión activa.

**Comportamiento**: si Reimo cambia de sesión en Claude Desktop, el bot lo detecta al recibir el siguiente mensaje (rescan antes de cada envío) y avisa por Telegram: *"Cambié al seguimiento de sesión: `<nombre-carpeta>`"*.

### Formato de mensajes en Telegram

Cada evento del `.jsonl` se traduce a un mensaje de Telegram:

| Evento JSON | Mensaje Telegram |
|---|---|
| `assistant` text | Texto plano (markdown V2) |
| `tool_use` Read | `📖 Read: ruta/archivo.py` |
| `tool_use` Edit | `✏️ Edit: ruta/archivo.py` + diff en bloque de código |
| `tool_use` Write | `📝 Write: ruta/archivo.py` |
| `tool_use` Bash | `▶️ Bash: <comando>` |
| `tool_use` Grep | `🔍 Grep: <patrón>` |
| `tool_use` Glob | `📂 Glob: <patrón>` |
| `tool_use` WebFetch/WebSearch | `🌐 Web: <URL>` |
| `tool_use` (otros) | `🔧 <Tool>: <input resumido>` |
| `tool_result` | Bloque de código con output (truncado a 4000 chars si es largo) |
| Error | `❌ Error: <mensaje>` |

Telegram tiene un límite de 4096 chars por mensaje. Mensajes largos se cortan en múltiples partes.

### Seguridad

**Whitelist obligatoria** — el bot lee `TELEGRAM_ALLOWED_USER_ID` del `.env`. Cualquier mensaje de otro user_id se ignora y se loggea con `logging.warning`.

**Confirmación Sí/No para operaciones destructivas** — antes de enviar el mensaje a Claude, el bot lo escanea contra una lista de patrones:
```
borra | elimina | rm \-rf | delete | drop | drop table |
deploy | vercel \-\-prod | git push \-\-force | force\-push |
prod | producción
```

Si hay match → el bot manda al chat de Telegram dos InlineKeyboardButtons: `[✅ Sí, mandar]` `[❌ No, cancelar]`. Sólo se envía a Claude si el usuario presiona Sí.

### Almacenamiento de estado

El bot guarda estado mínimo en memoria (no DB):
- `current_session_path` — ruta al .jsonl que está siendo monitoreado
- `last_seen_line` — último offset procesado del .jsonl (para no duplicar al reiniciar)
- `pending_confirmations` — dict `{message_id: texto_pendiente}` para los botones Sí/No
- `paused` — bool, si está pausado por `/parar`

Si el bot se reinicia, recalcula `last_seen_line` por timestamp para no reenviar mensajes viejos.

## Componentes (archivos)

### `bot.py` — entrypoint
- Crea `Application` de python-telegram-bot.
- Registra handlers: `CommandHandler` para `/start`, `/estado`, `/sesiones`, `/parar`, `/seguir`, `/ayuda`. `MessageHandler` para mensajes de texto. `CallbackQueryHandler` para los botones Sí/No.
- Inicia el `TranscriptWatcher` en una tarea async.
- Aplica el decorador `@requires_whitelist` a TODOS los handlers.

### `transcript_watcher.py`
- Clase `TranscriptWatcher` con `watchdog.observers.Observer`.
- En `on_modified`, lee solo las nuevas líneas (desde `last_seen_line`).
- Por cada línea: parsea JSON → llama a `formatters.format_event(event)` → manda a Telegram con `bot.send_message`.
- Maneja casos especiales: si el `.jsonl` activo cambia (otra sesión), detecta el cambio y notifica.

### `claude_controller.py`
- Clase `ClaudeController`.
- Método `send(text)`: encuentra ventana Claude Code Desktop, hace foco, escribe `text`, presiona Enter.
- Estrategia de búsqueda de ventana: por título (`"Claude"`) o por proceso (`Claude.exe`).
- Estrategia de búsqueda del input: por `AutomationId` o por nombre accesible (`"Escribe / para comandos"`, "Send a message", etc — probar varios).
- Si no encuentra ventana → lanza `ClaudeNotOpenError`.
- Si la PC está bloqueada → lanza `PCLockedError`.

### `session_detector.py`
- Función `detect_active_session() -> Path | None`: escanea `~/.claude/projects/**/*.jsonl`, devuelve el más reciente por mtime.
- Función `list_recent_sessions(n=10) -> list[SessionInfo]`: devuelve las n más recientes con metadatos (carpeta, último mensaje, timestamp).
- `SessionInfo` dataclass: `path`, `folder_name`, `last_modified`, `session_uuid`.

### `formatters.py`
- Función `format_event(event: dict) -> list[str]`: devuelve una lista de strings (uno o más mensajes de Telegram) según el tipo de evento.
- Helper `truncate(text, limit=4000)`: corta y agrega `... (truncado)`.
- Helper `escape_md_v2(text)`: escapa caracteres especiales de MarkdownV2.

### `security.py`
- `requires_whitelist(handler)`: decorador que verifica `update.effective_user.id == ALLOWED_USER_ID`.
- `is_destructive(text: str) -> bool`: regex match contra patrones definidos.
- `pending_confirmations: dict[int, str]`: cola en memoria de confirmaciones.

### `config.py`
- Carga `.env` con `python-dotenv`.
- Expone constantes: `TELEGRAM_BOT_TOKEN`, `ALLOWED_USER_ID`, `CLAUDE_PROJECTS_DIR`.
- Valida que existan al importar.

### `.env` (NO commitear)
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_USER_ID=987654321
CLAUDE_PROJECTS_DIR=C:\Users\Reimo\.claude\projects
```

### `.gitignore`
```
.env
__pycache__/
*.pyc
.venv/
```

### `requirements.txt`
```
python-telegram-bot[all]>=21.0
watchdog>=4.0
pywinauto>=0.6.8
python-dotenv>=1.0
```

## Flujo end-to-end (caso real)

1. Reimo abre Claude Code Desktop en la sesión "IA-Hub" antes de salir de casa.
2. Sale a la calle. El bot Python está corriendo en su PC.
3. Por Telegram: *"revisa los logs de IA-Hub y dime si hay errores"*.
4. `bot.py`:
   - `@requires_whitelist` valida user_id ✓
   - `is_destructive("revisa los logs...")` → False
   - Llama a `claude_controller.send("revisa los logs...")`.
5. `claude_controller`:
   - Encuentra ventana "Claude" en Windows.
   - Localiza el input.
   - Escribe el texto, presiona Enter.
6. Claude empieza a procesar. Escribe líneas al `.jsonl`.
7. `transcript_watcher` detecta cada línea nueva:
   - `tool_use Bash` → manda `▶️ Bash: vercel logs ia-hub`
   - `tool_result` → manda bloque de código con output
   - `assistant text` → manda `💬 Encontré 3 errores...`
8. Reimo responde por Telegram: *"corrige el primero y haz deploy a producción"*.
9. `is_destructive` detecta `deploy` y `producción` → manda botones Sí/No.
10. Reimo presiona [✅ Sí].
11. Bot envía el mensaje a Claude. Claude corrige, hace build, deploy.
12. Transcript watcher reenvía todo el proceso paso a paso a Telegram.

## Errores y casos borde

| Situación | Comportamiento del bot |
|---|---|
| Claude Desktop cerrada | Telegram: `❌ Claude Code Desktop no está abierto en tu PC. Ábrelo primero.` |
| PC bloqueada (Win+L) | Telegram: `❌ Tu PC está bloqueada. Desbloquéala para continuar.` (detectado porque pywinauto no puede interactuar con ventanas en sesión bloqueada) |
| No hay sesiones recientes en `~/.claude/projects/` | Telegram: `❌ No detecté ninguna sesión activa. Abre alguna sesión en Claude Desktop.` |
| El `.jsonl` activo cambia (Reimo cambió de sesión) | Telegram: `ℹ️ Cambié al seguimiento de sesión: <nombre-carpeta>` |
| Mensaje > 4096 chars | Se divide en partes con `(1/N)`, `(2/N)`. |
| User no autorizado escribe al bot | Ignorado silenciosamente. Log: `WARNING: Unauthorized user <id> tried to access bot` |
| Bot se reinicia | Recupera `last_seen_line` por timestamp (lee desde el último timestamp mayor a `bot_start_time - 1min`). |

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| pywinauto falla porque Anthropic cambia el UI de Claude Desktop | Múltiples estrategias de búsqueda del input (por AutomationId, por nombre, por tipo). Fácil de actualizar en `claude_controller.py`. |
| Confirmaciones destructivas no detectan algo peligroso | Lista de patrones expandible. Pueden agregarse más palabras en `security.py`. |
| Bot expone API key de Telegram en .env | `.gitignore` incluye `.env`. Nunca se commitea. |
| Alguien obtiene el user_id del owner y el bot token | Whitelist por user_id + las confirmaciones Sí/No reducen el daño. Si se sospecha compromiso: revocar token bot en @BotFather. |
| Race condition: bot manda mensaje mientras Claude todavía está procesando el anterior | Detectar si Claude está "pensando" (en el .jsonl aparece `queue-operation: enqueue` sin su `dequeue` correspondiente) y avisar: `⏳ Claude está procesando aún. Espera o pulsa /forzar.` (futuro v2) |

## v2 (futuro, no en este alcance)

- Cambio de sesión por Telegram (click automatizado en sidebar de Claude Desktop).
- Múltiples chats Telegram = múltiples sesiones simultáneas.
- Slash commands desde Telegram (`/memory`, `/clear`, `/skill`).
- Modo headless (sin ventana visible) usando `claude --resume <uuid>` desde un proceso bg.
- Streaming "vivo" de mensajes largos (editar el mensaje de Telegram conforme llegan más chunks).
- Resumen automático al pausar / al final del día.

## Testing

Cada componente se desarrolla con TDD donde tenga sentido:
- `formatters.py`: tests unitarios con eventos JSON de ejemplo.
- `security.py`: tests sobre `is_destructive()` (positivos y negativos).
- `session_detector.py`: tests con árbol de archivos temporales (`tmp_path` de pytest).
- `transcript_watcher.py`: test integración con archivo .jsonl real escrito por el test.
- `claude_controller.py`: imposible de testear sin la app abierta → smoke test manual.
- `bot.py`: integration test con bot de prueba real (token de bot de testing).
