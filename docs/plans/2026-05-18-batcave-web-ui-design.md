# Batcave Web UI — Diseno

**Fecha**: 2026-05-18
**Autor**: Sir Rich + Jeffri
**Estado**: Aprobado, listo para escribir plan de implementacion

## Vision

Reemplazar la dependencia exclusiva de Telegram por una **aplicacion web local con estetica Batcave pixel art**, donde Jeffri es el mayordomo (estilo Alfred de Bruce Wayne) y Sir Rich es el superheroe millonario que comanda todo desde su cueva. La app corre en `localhost:8000` servida por el mismo Python que ya tiene Jeffri.

Cuando Claude use sub-agentes (Task tool), cada agente aparece como un personaje pixel adicional en la Batcave, trabajando en su escritorio. Al final, el "jefe del laboratorio" entrega el reporte. Eventualmente Jeffri podra controlar la PC completa (computer use real): abrir apps, navegar Chrome, subir archivos a Google, etc.

## No-objetivos (v1)

- No reemplaza Telegram: ambos canales conviven.
- No requiere Electron ni distribucion: corre como `python -m src.bot` y abres `localhost:8000` en Chrome.
- No es multi-usuario: solo Sir Rich, misma whitelist que Telegram.
- No tiene cloud propio: todo en la PC. Excepcion: Groq sigue siendo cloud para enhancer + Whisper.

## Arquitectura

```
                       ┌──────────────────────┐
                       │ Telegram (existente) │
                       └──────────┬───────────┘
                                  │
   ┌──────────────────────────────┴─────────────────────────────┐
   │              Jeffri Python (extendido)                     │
   │  bot.py: handlers Telegram + arranque del servidor web     │
   │  Nuevos modulos:                                           │
   │   • web_server.py    FastAPI + uvicorn                     │
   │   • ws_chat.py       WebSocket /ws/chat                    │
   │   • ws_events.py     WebSocket /ws/events                  │
   │   • api_routes.py    REST /api/{projects,switch,capture}   │
   │  Reusa: groq_client, claude_controller, transcript_watcher,│
   │         security, session_detector, formatters             │
   └──────┬─────────────────────────────────────────┬───────────┘
          │                                         │
          ▼                                         ▼
   ┌─────────────────┐                       ┌──────────────────┐
   │ Claude Desktop  │                       │  Web Batcave     │
   │ (sin cambios)   │                       │  localhost:8000  │
   └─────────────────┘                       └──────────────────┘
```

## Decisiones tecnicas

### Backend

- **FastAPI + uvicorn**: framework ligero, soporta WebSocket nativo, ASGI compatible con asyncio existente.
- **Mismo proceso que el bot de Telegram**: arrancar uvicorn como `asyncio.create_task` dentro de `post_init` para que comparta el event loop y el `BotState`. Esto evita IPC/socket entre procesos.
- **WebSocket bidireccional**:
  - `/ws/chat`: cliente envia mensajes (texto, comandos), servidor envia confirmaciones + respuestas de Claude.
  - `/ws/events`: stream de eventos del transcript_watcher (texto del asistente, screenshots, cambios de sesion).
- **REST para operaciones puntuales**:
  - `GET /api/projects` → lista de proyectos detectados.
  - `POST /api/switch` → cambia de proyecto.
  - `POST /api/capture` → screenshot de Claude Desktop.
  - `POST /api/stop` → interrumpe Claude.
  - `GET /api/state` → estado actual (sesion activa, paused, enhancer on/off).
- **Autenticacion**: localhost-only por default (bind a 127.0.0.1). Si el usuario quiere acceder desde celular en LAN, configura `WEB_BIND=0.0.0.0` y un `WEB_AUTH_TOKEN` en `.env`.

### Frontend

- **Phaser 3**: motor de juegos JS perfecto para pixel art, animaciones de sprites, escenas.
- **TailwindCSS via CDN**: estilos del chat y layout sin build complejo.
- **Vanilla JS modular**: sin React. La complejidad de un framework no compensa para esta UI focused. Modulos:
  - `chat.js`: maneja WebSocket, render de mensajes.
  - `scene_batcave.js`: escena Phaser, sprites, animaciones.
  - `api.js`: wrapper REST.
  - `state.js`: estado compartido (sesion activa, proyectos, etc.).
- **Sin bundler**: archivos JS sueltos cargados con `<script type="module">`. Si crece, migramos a Vite.

### Visual / Sprites

- **MVP-1**: assets gratuitos de [itch.io free pixel art](https://itch.io/game-assets/free/tag-pixel-art) y [OpenGameArt](https://opengameart.org/). Buscar:
  - Fondo de cueva oscura con tech / monitores.
  - Sprite de mayordomo estilo Alfred (traje, postura formal).
  - Sprites de NPCs trabajadores para futuros sub-agentes.
- **MVP-2+**: si Sir Rich quiere, customizar sprites con Aseprite o IA (Stable Diffusion + pixel-art LoRA).

### Comunicacion en tiempo real

- WebSocket reconnect automatico con backoff exponencial.
- Mensajes JSON con `type` discriminator: `chat_message`, `enhance_result`, `confirm_request`, `transcript_event`, `screenshot`, etc.
- Reusamos el flujo de Telegram: mensaje de usuario → enhancer Groq → Original/Mejorado con botones de confirmacion → al confirmar, click en Claude Desktop.

## Componentes (resumen)

### Backend (`src/`)

| Modulo | Responsabilidad |
|---|---|
| `web_server.py` | Crea la app FastAPI, monta estaticos, define rutas |
| `ws_chat.py` | Handler de `/ws/chat`. Recibe mensajes, los procesa con el mismo pipeline que Telegram |
| `ws_events.py` | Handler de `/ws/events`. Broadcast de eventos del transcript_watcher |
| `api_routes.py` | Endpoints REST (proyectos, switch, captura) |
| `bot.py` (modificado) | Arranca uvicorn como task paralela a `app.run_polling()` |
| `config.py` (modificado) | Nuevas vars: `WEB_BIND`, `WEB_PORT`, `WEB_AUTH_TOKEN` |

### Frontend (`static/`)

| Archivo | Responsabilidad |
|---|---|
| `index.html` | Estructura base (canvas Phaser + sidebar chat) |
| `css/main.css` | Estilos (o Tailwind CDN) |
| `js/chat.js` | WebSocket cliente del chat |
| `js/scene_batcave.js` | Escena Phaser con Jeffri animado |
| `js/api.js` | Wrappers fetch para REST |
| `js/state.js` | Pub-sub simple para estado compartido |
| `assets/sprites/` | PNGs de personajes y fondos |
| `assets/sfx/` | SFX opcionales (clicks, mensaje recibido) |

## Flujo end-to-end

### Caso 1: enviar mensaje desde la Batcave

1. Sir Rich escribe en la caja de chat de la web.
2. JS envia `{"type": "user_text", "text": "..."}` por WebSocket `/ws/chat`.
3. Backend valida con `requires_whitelist_ws` (token desde `.env`).
4. Backend pasa el texto por `groq.enhance_prompt()` (mismo pipeline que Telegram).
5. Backend responde con `{"type": "confirm", "token": "...", "original": "...", "enhanced": "..."}`.
6. UI muestra Original + Mejorado con botones `[Mandar mejorado] [Mandar original] [Cancelar]`.
7. Sir Rich confirma → JS envia `{"type": "confirm_response", "token": "...", "choice": "send"}`.
8. Backend ejecuta `claude_controller.send(text)` → pega en Claude Desktop.
9. Mientras Claude responde, `transcript_watcher` emite eventos.
10. Eventos llegan por WebSocket `/ws/events` y la UI los pinta como mensajes de Jeffri / sub-agentes.

### Caso 2: cambio de proyecto

1. UI llama `GET /api/projects` → lista actual.
2. UI muestra grid pixel-art de proyectos como "estantes de la batcueva".
3. Usuario click en uno → `POST /api/switch` con el nombre.
4. Backend ejecuta `claude_controller.switch_session(name)`.
5. UI feedback visual: Jeffri "se levanta y camina al estante" (animacion Phaser).

## Errores y casos borde

| Situacion | Comportamiento |
|---|---|
| Claude Desktop cerrado | UI muestra modal pixel "Senor, el laboratorio esta cerrado. Abra Claude Desktop." |
| PC bloqueada | Idem con texto "Su PC esta bloqueada, senor." |
| WebSocket desconectado | Reconnect automatico con backoff 1s, 2s, 5s, 10s. UI muestra icono pixel de "senal" parpadeando. |
| Token de auth invalido (LAN) | HTTP 401, UI redirige a pantalla "ingrese token". |
| Groq falla | UI muestra warning pixel "Groq no responde, mando el original" y procede sin enhancer. |
| Multiples mensajes simultaneos (Telegram + web) | Se serializan con el mismo `send_lock` del controller. |

## Compatibilidad con Telegram

- El bot Telegram **sigue funcionando exactamente igual**.
- Los eventos del transcript_watcher se reenvian a AMBOS canales (Telegram y WebSocket).
- Si Sir Rich manda algo por Telegram mientras esta en la web, el evento aparece en ambas interfaces.
- Estado compartido: `paused`, `enhancer_enabled`, sesion activa son globales.

## Fases (roadmap)

### MVP-1 (~1 semana)

Funcional: chat de la web habla con Claude Desktop, mismo pipeline que Telegram.

- FastAPI + WebSocket /ws/chat funcional
- HTML basico con chat plano (sin pixel art aun)
- Integracion con Jeffri: enhancer + Claude controller
- Telegram sigue activo en paralelo
- Phaser 3 con escena Batcave: fondo + Jeffri animado idle/talking
- Burbujas de chat con estilo pixel
- Botones REST: proyectos, captura, stop
- Smoke test E2E

### MVP-2 (semanas 2-3)

Sub-agentes visualizados, "jefe del laboratorio".

- Detectar uso de Task tool en el transcript → spawn de NPC pixel adicional
- Animaciones de "trabajando" (typing, ir al escritorio)
- Reporte final del jefe cuando los sub-agentes terminan
- SFX opcionales (clicks, "mensaje" beep, etc.)
- Tema oscuro Batcave con monitores en pared

### MVP-3 (semanas 4-6)

Computer use real.

- Integrar `pyautogui` + `mss` para acciones libres
- Comando "Jeffri, abre Chrome y entra a X" → animacion de Jeffri saliendo del escritorio + ejecuta accion
- Posible integracion de UI-TARS o Open Interpreter como motor de decisiones de UI
- Browser automation con Playwright

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Pixel art lleva mas tiempo del esperado | Empezar con assets gratuitos. Reskinear despues. |
| WebSocket interfiere con polling de Telegram | Tareas separadas en el event loop, send_lock comun. |
| El usuario tiene varias ventanas de Chrome — la app puede confundirlas | Detectar la pestania de la app por titulo de la pagina. |
| Performance: Phaser y el watcher en el mismo browser | Phaser corre en GPU/Canvas, no afecta watcher (que es Python). |
| Computer use peligroso (MVP-3) | Mismo sistema de confirmacion destructiva que ya existe. |
| Sprites con licencia restrictiva | Filtrar por CC0 / dominio publico desde el principio. |

## Estructura de archivos resultante

```
src/
├── bot.py                  (modificado: arranca web server)
├── config.py               (modificado: WEB_BIND, WEB_PORT, WEB_AUTH_TOKEN)
├── web_server.py           (NUEVO)
├── ws_chat.py              (NUEVO)
├── ws_events.py            (NUEVO)
├── api_routes.py           (NUEVO)
├── claude_controller.py    (sin cambios)
├── transcript_watcher.py   (minor: broadcast a multiples consumers)
├── groq_client.py          (sin cambios)
├── security.py             (extender: requires_whitelist_ws)
├── session_detector.py     (sin cambios)
└── formatters.py           (sin cambios)

static/
├── index.html
├── css/
│   └── main.css
├── js/
│   ├── chat.js
│   ├── scene_batcave.js
│   ├── api.js
│   └── state.js
└── assets/
    ├── sprites/
    │   ├── jeffri.png
    │   ├── batcave_bg.png
    │   └── ...
    └── sfx/

tests/
└── test_web_server.py      (NUEVO)
└── test_ws_protocols.py    (NUEVO)
```

## Testing

- Tests unitarios para `web_server.py`, `ws_chat.py`, `api_routes.py` con `TestClient` de FastAPI.
- Smoke test manual E2E: arrancar bot, abrir `localhost:8000`, mandar mensaje, ver respuesta.
- Mantener los 48 tests existentes pasando.

---

## Comandos clave despues de implementar

```powershell
# Arrancar el bot (Telegram + web simultaneamente)
.\.venv\Scripts\python.exe -m src.bot

# Abrir la batcueva
start http://localhost:8000
```

🦇 *La Batcueva esta lista, senor.*
