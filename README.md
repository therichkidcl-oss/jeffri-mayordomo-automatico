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

## Setup inicial

Antes de la primera ejecución necesitas:

1. **Crear el bot en Telegram**: abre `@BotFather`, envía `/newbot`, sigue las instrucciones, copia el token.
2. **Obtener tu user_id**: abre `@userinfobot` y pulsa `/start` — te devuelve tu user_id.
3. **Rellenar el `.env`** con esos dos valores (template en `.env.example`).
4. **Verificar que NO tienes `ANTHROPIC_API_KEY` en el entorno** (el bot usa tu autenticación de Claude Code, no la API directa).

## Comandos del bot

- `/start` — bienvenida + sesión activa detectada
- `/estado` — estado del bot (pausado/activo + sesión actual)
- `/sesiones` — lista de las 10 sesiones más recientes
- `/captura` — screenshot de la ventana de Claude (útil para ver detalle visual)
- `/parar` — pausa el reenvío (Claude sigue trabajando en la PC, pero Telegram no recibe)
- `/seguir` — reanuda el reenvío
- `/ayuda` — lista de comandos

Cualquier otro texto se envía como mensaje a la sesión activa de Claude.

## Confirmación para operaciones destructivas

Si tu mensaje contiene palabras como `deploy`, `borra`, `rm`, `delete`, `drop`, `truncate`,
`force push`, `git reset --hard`, `producción`, etc., el bot te pedirá confirmación
con botones `[✅ Sí, mandar]` `[❌ No, cancelar]` antes de enviarlo a Claude.

## Limitaciones (v1)

- La PC debe estar prendida y desbloqueada (no funciona con Win+L).
- Claude Code Desktop debe estar abierto (en cualquier sesión).
- Solo el `TELEGRAM_ALLOWED_USER_ID` del `.env` puede usar el bot — otros mensajes se ignoran silenciosamente.
- El bot escribe en la ventana de Claude usando UI automation (`pywinauto`). Cuando manda un mensaje, brevemente roba foco a esa ventana.
- Si tienes varias ventanas de Claude abiertas, usa la primera visible.

## Estructura del código

| Archivo | Responsabilidad |
|---|---|
| `src/bot.py` | Entry point. Handlers de Telegram, comandos, callbacks. |
| `src/config.py` | Carga variables del `.env`. |
| `src/session_detector.py` | Detecta la sesión activa (`.jsonl` con `mtime` más reciente). |
| `src/transcript_watcher.py` | Vigila el `.jsonl` activo y emite eventos parseados. |
| `src/claude_controller.py` | UI automation: escribe en la ventana de Claude Desktop. |
| `src/formatters.py` | Convierte eventos JSON a mensajes Telegram con emojis e iconos. |
| `src/security.py` | Whitelist por user_id + detección de operaciones destructivas. |

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Cubre `config`, `session_detector`, `formatters`, `security`, `transcript_watcher`. El bot y el controller no tienen tests automatizados (son integration points, validados por smoke test manual).

## Diseño y plan

- [docs/plans/2026-05-13-telegram-claude-bridge-design.md](docs/plans/2026-05-13-telegram-claude-bridge-design.md)
- [docs/plans/2026-05-13-telegram-claude-bridge-plan.md](docs/plans/2026-05-13-telegram-claude-bridge-plan.md)
