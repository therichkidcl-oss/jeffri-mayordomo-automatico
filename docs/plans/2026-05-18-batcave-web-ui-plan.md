# Batcave Web UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Construir una web local pixel art estilo Batcave en `localhost:8000` (servida por el mismo Python de Jeffri) que funcione como alternativa a Telegram, manteniendo ambos canales en paralelo.

**Architecture:** Extender `bot.py` con un servidor FastAPI/uvicorn que comparte el mismo event loop y `BotState`. La web ofrece WebSocket bidireccional para chat y eventos, mas endpoints REST para acciones puntuales. Frontend en HTML estatico con **Canvas 2D vanilla** (no Phaser — los sprites reales del pack `pixel-agents` no necesitan motor de juego complejo).

**Tech Stack:** Python 3.13+, FastAPI, uvicorn, websockets, Canvas 2D, TailwindCSS (CDN), vanilla JS.

**Referencia de diseno:** [docs/plans/2026-05-18-batcave-web-ui-design.md](2026-05-18-batcave-web-ui-design.md)

## Optimizaciones desde repos open source

Aprovechamos del repo MIT [pablodelucca/pixel-agents](https://github.com/pablodelucca/pixel-agents):
- **6 sprites de personajes** (`char_0.png` a `char_5.png`) — uno sera Jeffri
- **9 sprites de pisos** (`floor_0.png` a `floor_8.png`)
- **25 muebles** con orientaciones (escritorios, sillas, PCs, plantas, cuadros, sofas...)
- Atribucion en `static/assets/NOTICE.md` (ya commiteada)

**Cambio vs plan inicial:** descartamos Phaser. Canvas 2D vanilla es suficiente, mas liviano (sin CDN), y los sprites pixel-perfect ya estan listos.

## Convenciones de seguridad del codigo JS

- NUNCA `innerHTML` con datos dinamicos. Siempre `createElement` + `textContent` + `appendChild`.
- Eventos con `onclick =` o `addEventListener`.

---

## Fase MVP-1: Chat funcional + Batcave basica

Las tareas 0-10 cubren el MVP-1.

---

## Task 0: Bootstrap del servidor FastAPI

**Files:**
- Modify: `requirements.txt`
- Create: `src/web_server.py`
- Modify: `src/config.py`
- Modify: `.env.example`
- Modify: `.env`

**Step 1: Agregar dependencias a `requirements.txt`**

```
fastapi>=0.115
uvicorn[standard]>=0.32
```

**Step 2: Instalar**

```powershell
.\.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]"
```

**Step 3: Agregar variables a `.env.example` (y a `.env`)**

```
WEB_BIND=127.0.0.1
WEB_PORT=8000
WEB_AUTH_TOKEN=
```

**Step 4: Extender `src/config.py`**

```python
WEB_BIND: str = os.environ.get("WEB_BIND", "127.0.0.1")
WEB_PORT: int = int(os.environ.get("WEB_PORT", "8000"))
WEB_AUTH_TOKEN: str = os.environ.get("WEB_AUTH_TOKEN", "")
```

**Step 5: Crear `src/web_server.py`**

```python
"""Servidor FastAPI que sirve la UI Batcave."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def create_app(state) -> FastAPI:
    app = FastAPI(title="Jeffri Batcave")
    app.state.bot_state = state

    static_dir = Path(__file__).resolve().parent.parent / "static"
    static_dir.mkdir(exist_ok=True)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return HTMLResponse("<h1>Batcave under construction</h1>")
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/api/state")
    async def get_state():
        return {
            "paused": state.paused,
            "enhancer_enabled": state.enhancer_enabled,
            "groq_available": state.groq is not None,
        }

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"FastAPI app creada, static dir: {static_dir}")
    return app
```

**Step 6: Smoke test**

```powershell
.\.venv\Scripts\python.exe -c "from src.web_server import create_app; print('OK')"
```

**Step 7: Commit**

```bash
git add requirements.txt src/web_server.py src/config.py .env.example .env
git commit -m "feat(web): bootstrap FastAPI server scaffold"
```

---

## Task 1: Integrar el servidor web en `bot.py`

**Files:** `src/bot.py`

**Step 1: Imports al tope**

```python
import uvicorn
from src.web_server import create_app
from src.config import WEB_BIND, WEB_PORT
```

**Step 2: En `post_init`, agregar al final**

```python
    web_app = create_app(state)
    config = uvicorn.Config(
        web_app, host=WEB_BIND, port=WEB_PORT,
        log_level="warning", access_log=False,
    )
    server = uvicorn.Server(config)
    app.bot_data["web_server_task"] = asyncio.create_task(server.serve())
    logger.info(f"Batcave web disponible en http://{WEB_BIND}:{WEB_PORT}")
```

**Step 3: Smoke test**

```powershell
Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m","src.bot"
Start-Sleep -Seconds 5
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/state" -UseBasicParsing | Select-Object -ExpandProperty Content
```

Esperado: `{"paused":false,"enhancer_enabled":true,"groq_available":true}`

**Step 4: Commit**

```bash
git add src/bot.py
git commit -m "feat(web): launch FastAPI alongside Telegram polling"
```

---

## Task 2: Commit de assets pixel-agents + NOTICE

**Files:** `static/assets/**` (ya copiados), `static/assets/NOTICE.md` (ya creado)

**Step 1: Verificar que esten los assets**

```powershell
Get-ChildItem static/assets/characters | Measure-Object | Select-Object Count
Get-ChildItem static/assets/floors | Measure-Object | Select-Object Count
Get-ChildItem static/assets/furniture | Measure-Object | Select-Object Count
```

Esperado: 6, 9, 25.

**Step 2: Commit**

```bash
git add static/assets/
git commit -m "feat(web): import MIT-licensed pixel art assets from pixel-agents"
```

---

## Task 3: HTML basico + estilos Batcave

**Files:**
- Create: `static/index.html`
- Create: `static/css/main.css`
- Create: `static/js/state.js`

**Step 1: Crear `static/index.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🦇 Batcave</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="/static/css/main.css">
</head>
<body class="bg-slate-900 text-amber-100 min-h-screen flex flex-col">
  <header class="border-b border-amber-700/40 p-4 flex justify-between items-center">
    <h1 class="text-2xl font-bold tracking-wider">🦇 Batcave — Jeffri al servicio</h1>
    <div id="status" class="text-sm text-amber-300/70">Conectando...</div>
  </header>

  <main class="flex-1 grid grid-cols-3 gap-4 p-4 max-w-7xl mx-auto w-full">
    <section class="col-span-2 bg-slate-800/60 rounded-lg p-2 border border-amber-700/30 flex items-center justify-center">
      <canvas id="batcave-canvas" width="640" height="360" class="pixelated max-w-full"></canvas>
    </section>

    <aside class="bg-slate-800/60 rounded-lg p-4 flex flex-col border border-amber-700/30">
      <div id="messages" class="flex-1 overflow-y-auto space-y-2 mb-2 min-h-[300px]"></div>
      <form id="chat-form" class="flex gap-2">
        <input id="chat-input" type="text" placeholder="Sus ordenes, senor..."
               class="flex-1 bg-slate-900 border border-amber-700/40 rounded px-3 py-2 text-amber-100 placeholder-amber-700/40 focus:outline-none focus:border-amber-500">
        <button type="submit"
                class="bg-amber-700 hover:bg-amber-600 px-4 py-2 rounded font-bold">Enviar</button>
      </form>
    </aside>
  </main>

  <script type="module" src="/static/js/state.js"></script>
</body>
</html>
```

**Step 2: Crear `static/css/main.css`**

```css
body {
  font-family: 'Courier New', Courier, monospace;
}

.pixelated {
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}

#messages > div {
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  line-height: 1.4;
}

.msg-user {
  background: rgba(180, 83, 9, 0.3);
  border-left: 3px solid rgb(217, 119, 6);
}

.msg-jeffri {
  background: rgba(15, 23, 42, 0.6);
  border-left: 3px solid rgb(245, 158, 11);
}

.msg-system {
  color: rgba(252, 211, 77, 0.6);
  font-style: italic;
  font-size: 0.75rem;
  text-align: center;
}
```

**Step 3: Crear `static/js/state.js`**

```javascript
const statusEl = document.getElementById('status');
const messagesEl = document.getElementById('messages');

async function fetchState() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    statusEl.textContent = `Conectado. Enhancer ${data.enhancer_enabled ? 'ON' : 'OFF'}.`;
    addSystemMessage('🦇 Batcave operativa, senor.');
  } catch (e) {
    statusEl.textContent = 'Sin conexion';
    addSystemMessage('Sin conexion al backend.');
  }
}

export function addSystemMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg-system';
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

export function addUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg-user';
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

export function addJeffriMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg-jeffri';
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

fetchState();
```

**Step 4: Smoke test**

Abrir `http://localhost:8000`, ver el layout con header, canvas vacio, sidebar de chat, mensaje "🦇 Batcave operativa".

**Step 5: Commit**

```bash
git add static/index.html static/css/main.css static/js/state.js
git commit -m "feat(web): batcave HTML skeleton with canvas + sidebar"
```

---

## Task 4: WebSocket /ws/chat — backend

**Files:**
- Create: `src/ws_chat.py`
- Modify: `src/web_server.py`

**Step 1: Crear `src/ws_chat.py`**

```python
"""WebSocket handler para el chat de la Batcave."""
import asyncio
import json
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from src.config import WEB_AUTH_TOKEN
from src.security import is_destructive

logger = logging.getLogger(__name__)


async def handle_chat_ws(websocket: WebSocket, bot_state):
    await websocket.accept()
    logger.info("Cliente conectado a /ws/chat")

    if WEB_AUTH_TOKEN:
        try:
            auth = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
            if auth.get("token") != WEB_AUTH_TOKEN:
                await websocket.send_json({"type": "auth_failed"})
                await websocket.close(code=4001)
                return
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.close(code=4001)
            return

    await websocket.send_json({"type": "welcome", "message": "Bienvenido, Sir Rich"})

    try:
        while True:
            data = await websocket.receive_json()
            await _route_message(data, websocket, bot_state)
    except WebSocketDisconnect:
        logger.info("Cliente desconectado de /ws/chat")
    except Exception as e:
        logger.exception(f"Error en ws_chat: {e}")


async def _route_message(data: dict, websocket: WebSocket, bot_state):
    msg_type = data.get("type")
    if msg_type == "user_text":
        await _handle_user_text(data, websocket, bot_state)
    elif msg_type == "confirm_response":
        await _handle_confirm(data, websocket, bot_state)
    else:
        await websocket.send_json({"type": "error", "message": f"Tipo desconocido: {msg_type}"})


async def _handle_user_text(data: dict, websocket: WebSocket, bot_state):
    text = (data.get("text") or "").strip()
    if not text:
        return

    if is_destructive(text):
        token = uuid.uuid4().hex[:8]
        bot_state.pending_destructive[token] = text
        await websocket.send_json({
            "type": "confirm_destructive", "token": token, "text": text,
        })
        return

    if bot_state.groq is None or not bot_state.enhancer_enabled:
        await _do_send_to_claude(text, websocket, bot_state)
        return

    try:
        enhanced = await bot_state.groq.enhance_prompt(text, source="texto")
    except Exception as e:
        logger.warning(f"Groq fallo: {e}, mando original")
        await _do_send_to_claude(text, websocket, bot_state)
        return

    if enhanced.strip() == text.strip():
        await _do_send_to_claude(text, websocket, bot_state)
        return

    token = uuid.uuid4().hex[:8]
    bot_state.pending_enhanced[token] = {"original": text, "enhanced": enhanced}
    await websocket.send_json({
        "type": "confirm_enhanced", "token": token,
        "original": text, "enhanced": enhanced,
    })


async def _handle_confirm(data: dict, websocket: WebSocket, bot_state):
    token = data.get("token", "")
    choice = data.get("choice", "")

    if not bot_state.claim_token(f"web:{token}"):
        return

    payload = bot_state.pending_enhanced.pop(token, None)
    if payload:
        if choice == "send_enhanced":
            await _do_send_to_claude(payload["enhanced"], websocket, bot_state)
        elif choice == "send_original":
            await _do_send_to_claude(payload["original"], websocket, bot_state)
        else:
            await websocket.send_json({"type": "cancelled"})
        return

    text = bot_state.pending_destructive.pop(token, None)
    if text and choice == "send_enhanced":
        await _do_send_to_claude(text, websocket, bot_state)
    else:
        await websocket.send_json({"type": "cancelled"})


async def _do_send_to_claude(text: str, websocket: WebSocket, bot_state):
    try:
        async with bot_state.send_lock:
            await bot_state.controller.send(text)
        await websocket.send_json({"type": "sent", "text": text})
    except Exception as e:
        logger.exception("Error enviando a Claude desde web")
        await websocket.send_json({"type": "error", "message": str(e)})
```

**Step 2: Registrar endpoint en `web_server.py`**

Agregar despues de `get_state`:

```python
    from fastapi import WebSocket
    from src.ws_chat import handle_chat_ws

    @app.websocket("/ws/chat")
    async def ws_chat_endpoint(websocket: WebSocket):
        await handle_chat_ws(websocket, state)
```

**Step 3: Smoke test**

```powershell
.\.venv\Scripts\python.exe -c "
import asyncio, websockets
async def t():
    async with websockets.connect('ws://localhost:8000/ws/chat') as ws:
        print(await ws.recv())
asyncio.run(t())
"
```

Esperado: `{"type": "welcome", ...}`

**Step 4: Commit**

```bash
git add src/ws_chat.py src/web_server.py
git commit -m "feat(web): websocket /ws/chat with enhancer + confirm flow"
```

---

## Task 5: WebSocket /ws/chat — cliente JS

**Files:**
- Create: `static/js/chat.js`
- Modify: `static/index.html`

**Step 1: Crear `static/js/chat.js`** (sin innerHTML, todo con createElement)

```javascript
import { addJeffriMessage, addUserMessage, addSystemMessage } from './state.js';

let ws = null;
let reconnectDelay = 1000;
const MAX_DELAY = 10000;

function connect() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${window.location.host}/ws/chat`);

  ws.onopen = () => {
    addSystemMessage('🟢 Conectado a Jeffri');
    reconnectDelay = 1000;
  };
  ws.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch (e) { return; }
    handleServerMessage(data);
  };
  ws.onclose = () => {
    addSystemMessage(`🔴 Desconectado. Reintentando en ${reconnectDelay/1000}s...`);
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY);
  };
}

function handleServerMessage(data) {
  switch (data.type) {
    case 'welcome': addSystemMessage(data.message); break;
    case 'confirm_enhanced': renderEnhancedConfirm(data); break;
    case 'confirm_destructive': renderDestructiveConfirm(data); break;
    case 'sent': addSystemMessage(`✉️ Enviado: ${data.text.slice(0, 80)}`); break;
    case 'cancelled': addSystemMessage('❌ Cancelado'); break;
    case 'error': addSystemMessage(`❌ ${data.message}`); break;
  }
}

function makeButton(label, classes, onClick) {
  const btn = document.createElement('button');
  btn.textContent = label;
  btn.className = classes;
  btn.onclick = onClick;
  return btn;
}

function renderEnhancedConfirm(data) {
  const wrap = document.createElement('div');
  wrap.className = 'msg-jeffri';

  const orig = document.createElement('div');
  const ol = document.createElement('strong');
  ol.textContent = '📝 Original: ';
  orig.appendChild(ol);
  orig.appendChild(document.createTextNode(data.original));
  wrap.appendChild(orig);

  const enh = document.createElement('div');
  enh.className = 'mt-2';
  const el = document.createElement('strong');
  el.textContent = '✨ Mejorado: ';
  enh.appendChild(el);
  enh.appendChild(document.createTextNode(data.enhanced));
  wrap.appendChild(enh);

  const buttons = document.createElement('div');
  buttons.className = 'mt-2 flex gap-2';
  const send = (choice) => {
    ws.send(JSON.stringify({ type: 'confirm_response', token: data.token, choice }));
    buttons.querySelectorAll('button').forEach(b => b.disabled = true);
  };
  buttons.appendChild(makeButton('✅ Mejorado', 'bg-green-700 hover:bg-green-600 px-2 py-1 rounded text-xs', () => send('send_enhanced')));
  buttons.appendChild(makeButton('📤 Original', 'bg-blue-700 hover:bg-blue-600 px-2 py-1 rounded text-xs', () => send('send_original')));
  buttons.appendChild(makeButton('❌ Cancelar', 'bg-red-700 hover:bg-red-600 px-2 py-1 rounded text-xs', () => send('cancel')));
  wrap.appendChild(buttons);

  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

function renderDestructiveConfirm(data) {
  const wrap = document.createElement('div');
  wrap.className = 'msg-jeffri';
  const t = document.createElement('div');
  const warn = document.createElement('strong');
  warn.textContent = '⚠️ Destructivo: ';
  t.appendChild(warn);
  t.appendChild(document.createTextNode(data.text));
  wrap.appendChild(t);

  const buttons = document.createElement('div');
  buttons.className = 'mt-2 flex gap-2';
  const send = (choice) => {
    ws.send(JSON.stringify({ type: 'confirm_response', token: data.token, choice }));
    buttons.querySelectorAll('button').forEach(b => b.disabled = true);
  };
  buttons.appendChild(makeButton('✅ Si, mandar', 'bg-green-700 px-2 py-1 rounded text-xs', () => send('send_enhanced')));
  buttons.appendChild(makeButton('❌ Cancelar', 'bg-red-700 px-2 py-1 rounded text-xs', () => send('cancel')));
  wrap.appendChild(buttons);

  document.getElementById('messages').appendChild(wrap);
  document.getElementById('messages').scrollTop = 99999;
}

document.getElementById('chat-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  addUserMessage(text);
  ws.send(JSON.stringify({ type: 'user_text', text }));
  input.value = '';
});

connect();
```

**Step 2: Cargar en `index.html`**

Antes del `</body>`:
```html
<script type="module" src="/static/js/chat.js"></script>
```

**Step 3: Smoke test E2E**

Mandar texto en la web → ver Original/Mejorado → click "✅ Mejorado" → el mensaje se pega en Claude Desktop.

**Step 4: Commit**

```bash
git add static/js/chat.js static/index.html
git commit -m "feat(web): chat client with safe DOM rendering"
```

---

## Task 6: Endpoints REST + cliente api.js

**Files:**
- Create: `src/api_routes.py`
- Modify: `src/web_server.py`
- Create: `static/js/api.js`

**Step 1: Crear `src/api_routes.py`**

```python
"""Endpoints REST de la Batcave."""
import base64
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.config import CLAUDE_PROJECTS_DIR
from src.session_detector import list_projects

logger = logging.getLogger(__name__)


class SwitchRequest(BaseModel):
    display_name: str


def create_router(bot_state) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/projects")
    async def get_projects():
        projects = list_projects(CLAUDE_PROJECTS_DIR)
        return [
            {
                "folder_name": p.folder_name,
                "display_name": p.display_name,
                "session_count": p.session_count,
                "last_modified": p.last_modified.isoformat(),
            }
            for p in projects
        ]

    @router.post("/switch")
    async def switch_project(req: SwitchRequest):
        try:
            async with bot_state.send_lock:
                await bot_state.controller.switch_session(req.display_name)
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/capture")
    async def capture():
        try:
            png_bytes = await bot_state.controller.capture()
            return {"ok": True, "png_b64": base64.b64encode(png_bytes).decode()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/stop")
    async def stop():
        try:
            async with bot_state.send_lock:
                await bot_state.controller.interrupt()
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
```

**Step 2: Montar en `web_server.py`**

```python
    from src.api_routes import create_router
    app.include_router(create_router(state))
```

**Step 3: Crear `static/js/api.js`**

```javascript
export async function listProjects() {
  const res = await fetch('/api/projects');
  return res.json();
}

export async function switchProject(displayName) {
  const res = await fetch('/api/switch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function capture() {
  const res = await fetch('/api/capture', { method: 'POST' });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function stopClaude() {
  const res = await fetch('/api/stop', { method: 'POST' });
  return res.json();
}
```

**Step 4: Smoke test**

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/projects" -UseBasicParsing | Select-Object -ExpandProperty Content
```

**Step 5: Commit**

```bash
git add src/api_routes.py src/web_server.py static/js/api.js
git commit -m "feat(web): REST endpoints + JS client"
```

---

## Task 7: Escena Canvas 2D con Jeffri pixel real

**Files:**
- Create: `static/js/scene_batcave.js`
- Modify: `static/index.html`

**Step 1: Crear `static/js/scene_batcave.js`**

Carga sprites reales del pack `pixel-agents`. Usa Canvas 2D, sin Phaser.

```javascript
// Escena Canvas 2D de la Batcave. Carga sprites reales.

const canvas = document.getElementById('batcave-canvas');
const ctx = canvas.getContext('2d');
ctx.imageSmoothingEnabled = false;

const SCALE = 3;
const W = canvas.width;
const H = canvas.height;

const assets = {
  floor: null,
  desk: null,
  chair: null,
  bookshelf: null,
  pc: null,
  jeffri: null,
};

let bobPhase = 0;
let speechText = 'Sus ordenes, senor.';
let speechExpire = Infinity;

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

async function loadAssets() {
  const [floor, desk, chair, bookshelf, pc, jeffri] = await Promise.all([
    loadImage('/static/assets/floors/floor_3.png'),
    loadImage('/static/assets/furniture/DESK/DESK_FRONT.png').catch(() =>
      loadImage('/static/assets/furniture/DESK/DESK.png').catch(() => null)),
    loadImage('/static/assets/furniture/WOODEN_CHAIR/WOODEN_CHAIR_FRONT.png').catch(() =>
      loadImage('/static/assets/furniture/WOODEN_CHAIR/WOODEN_CHAIR.png').catch(() => null)),
    loadImage('/static/assets/furniture/BOOKSHELF/BOOKSHELF.png').catch(() => null),
    loadImage('/static/assets/furniture/PC/PC.png').catch(() => null),
    loadImage('/static/assets/characters/char_0.png'),
  ]);
  assets.floor = floor;
  assets.desk = desk;
  assets.chair = chair;
  assets.bookshelf = bookshelf;
  assets.pc = pc;
  assets.jeffri = jeffri;
}

function drawFloor() {
  if (!assets.floor) return;
  const tileW = assets.floor.width;
  const tileH = assets.floor.height;
  for (let y = H - tileH * SCALE; y < H; y += tileH * SCALE) {
    for (let x = 0; x < W; x += tileW * SCALE) {
      ctx.drawImage(assets.floor, x, y, tileW * SCALE, tileH * SCALE);
    }
  }
}

function drawBackground() {
  ctx.fillStyle = '#0a0e1a';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#1a1f2e';
  for (let i = 0; i < 6; i++) {
    const x = (W / 6) * i + 20;
    const h = 40 + Math.sin(i * 1.7) * 20;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x + 30, 0);
    ctx.lineTo(x + 15, h);
    ctx.closePath();
    ctx.fill();
  }
  ctx.fillStyle = '#1c2335';
  ctx.fillRect(W - 220, 50, 180, 110);
  ctx.fillStyle = '#10b981';
  ctx.fillRect(W - 215, 55, 170, 100);
  ctx.fillStyle = 'rgba(16, 185, 129, 0.3)';
  ctx.font = '10px Courier New';
  ctx.fillText('JEFFRI v1.0', W - 210, 70);
  ctx.fillText('STATUS: ON', W - 210, 85);
  ctx.fillText('AGENT: READY', W - 210, 100);
}

function drawFurniture() {
  const baseY = H - 100;
  if (assets.bookshelf) {
    const w = assets.bookshelf.width * SCALE;
    const h = assets.bookshelf.height * SCALE;
    ctx.drawImage(assets.bookshelf, 30, baseY - h + 50, w, h);
  }
  if (assets.pc) {
    const w = assets.pc.width * SCALE;
    const h = assets.pc.height * SCALE;
    ctx.drawImage(assets.pc, W / 2 - w / 2 - 30, baseY - 50, w, h);
  }
  if (assets.desk) {
    const w = assets.desk.width * SCALE;
    const h = assets.desk.height * SCALE;
    ctx.drawImage(assets.desk, W / 2 - w / 2, baseY, w, h);
  }
  if (assets.chair) {
    const w = assets.chair.width * SCALE;
    const h = assets.chair.height * SCALE;
    ctx.drawImage(assets.chair, W / 2 - w / 2 + 80, baseY + 20, w, h);
  }
}

function drawJeffri() {
  if (!assets.jeffri) return;
  const w = assets.jeffri.width * SCALE;
  const h = assets.jeffri.height * SCALE;
  const x = W / 2 - w / 2;
  const y = H - 100 - h + 30 + Math.sin(bobPhase) * 2;
  ctx.drawImage(assets.jeffri, x, y, w, h);

  if (speechText && Date.now() < speechExpire) {
    const txt = speechText.slice(0, 40);
    ctx.font = '14px Courier New';
    const tw = ctx.measureText(txt).width;
    const bx = x + w / 2 - tw / 2 - 8;
    const by = y - 30;
    ctx.fillStyle = '#0a0e1a';
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 2;
    ctx.fillRect(bx, by, tw + 16, 22);
    ctx.strokeRect(bx, by, tw + 16, 22);
    ctx.fillStyle = '#fbbf24';
    ctx.fillText(txt, bx + 8, by + 16);
  }
}

function render() {
  drawBackground();
  drawFloor();
  drawFurniture();
  drawJeffri();
  bobPhase += 0.04;
  requestAnimationFrame(render);
}

export function showSpeech(text, durationMs = 5000) {
  speechText = text;
  speechExpire = Date.now() + durationMs;
}

window.batcaveShowSpeech = showSpeech;

loadAssets().then(() => {
  console.log('Batcave assets cargados');
  render();
}).catch(e => {
  console.error('Error cargando assets:', e);
  drawBackground();
});
```

**Step 2: Cargar en `index.html`**

Antes del `</body>` (despues de `chat.js`):
```html
<script type="module" src="/static/js/scene_batcave.js"></script>
```

**Step 3: Smoke test**

Abrir la web. Verificar:
- Fondo oscuro con estalactitas
- Monitor verde con texto "JEFFRI v1.0" en la pared
- Piso con tiles
- Muebles pixel (bookshelf, PC, desk, chair)
- Jeffri (char_0.png) sobre el escritorio respirando
- Bocadillo "Sus ordenes, senor."

**Step 4: Commit**

```bash
git add static/js/scene_batcave.js static/index.html
git commit -m "feat(web): canvas 2d batcave scene with real pixel art assets"
```

---

## Task 8: Conectar la escena con el chat

**Files:** Modify `static/js/chat.js`

**Step 1: Llamar a `batcaveShowSpeech` en eventos**

En `handleServerMessage`, cambiar los cases:

```javascript
    case 'welcome':
      addSystemMessage(data.message);
      if (window.batcaveShowSpeech) window.batcaveShowSpeech('Bienvenido, Sir Rich.');
      break;
    ...
    case 'sent':
      addSystemMessage(`✉️ Enviado: ${data.text.slice(0, 80)}`);
      if (window.batcaveShowSpeech) window.batcaveShowSpeech('Entregado a Claude, senor.');
      break;
```

**Step 2: Smoke test**

Mandar un mensaje y ver el bocadillo cambiando en el canvas.

**Step 3: Commit**

```bash
git add static/js/chat.js
git commit -m "feat(web): jeffri speech bubble reacts to chat events"
```

---

## Task 9: WebSocket /ws/events + render de respuestas de Claude

**Files:**
- Create: `src/ws_events.py`
- Modify: `src/web_server.py`, `src/bot.py`, `static/js/chat.js`

**Step 1: Crear `src/ws_events.py`**

```python
"""Broadcast de eventos del transcript watcher."""
import asyncio
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

from src.config import WEB_AUTH_TOKEN

logger = logging.getLogger(__name__)


class EventBroadcaster:
    def __init__(self):
        self.clients: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def add(self, ws): 
        async with self.lock:
            self.clients.add(ws)

    async def remove(self, ws):
        async with self.lock:
            self.clients.discard(ws)

    async def broadcast(self, payload: dict):
        async with self.lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                await self.remove(ws)


broadcaster = EventBroadcaster()


async def handle_events_ws(websocket: WebSocket):
    if WEB_AUTH_TOKEN:
        token = websocket.query_params.get("token", "")
        if token != WEB_AUTH_TOKEN:
            await websocket.close(code=4001)
            return
    await websocket.accept()
    await broadcaster.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.remove(websocket)
```

**Step 2: Registrar en `web_server.py`**

```python
    from src.ws_events import handle_events_ws

    @app.websocket("/ws/events")
    async def ws_events_endpoint(websocket: WebSocket):
        await handle_events_ws(websocket)
```

**Step 3: Modificar `bot.py` para broadcast**

Renombrar `_forward_event_to_telegram` a `_forward_event` y agregar broadcast:

```python
async def _forward_event(app: Application, event: dict):
    if state.paused:
        return
    messages = format_event(event)
    from src.ws_events import broadcaster
    import base64
    for msg in messages:
        if isinstance(msg, TextMessage):
            await _send_text(app, msg.text)
            await broadcaster.broadcast({"type": "claude_text", "text": msg.text})
        elif isinstance(msg, PhotoMessage):
            await _send_photo(app, msg.data, msg.caption)
            await broadcaster.broadcast({
                "type": "claude_photo",
                "png_b64": base64.b64encode(msg.data).decode(),
                "caption": msg.caption,
            })
```

Actualizar `on_event` en `post_init` para llamar a `_forward_event`.

**Step 4: Cliente en `chat.js`**

Agregar al final:

```javascript
let eventsWs = null;

function connectEvents() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  eventsWs = new WebSocket(`${proto}//${window.location.host}/ws/events`);

  eventsWs.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch (e) { return; }
    if (data.type === 'claude_text') {
      addJeffriMessage(`🤖 ${data.text}`);
      if (window.batcaveShowSpeech) window.batcaveShowSpeech(data.text);
    } else if (data.type === 'claude_photo') {
      const wrap = document.createElement('div');
      wrap.className = 'msg-jeffri';
      const img = document.createElement('img');
      img.src = `data:image/png;base64,${data.png_b64}`;
      img.className = 'max-w-full rounded';
      wrap.appendChild(img);
      if (data.caption) {
        const cap = document.createElement('div');
        cap.textContent = data.caption;
        cap.className = 'text-xs mt-1 opacity-70';
        wrap.appendChild(cap);
      }
      document.getElementById('messages').appendChild(wrap);
    }
  };

  eventsWs.onclose = () => setTimeout(connectEvents, 2000);
}

connectEvents();
```

**Step 5: Smoke E2E**

Mandar "hola" desde la web → ver respuesta de Claude llegar a la web y a Telegram.

**Step 6: Commit**

```bash
git add src/ws_events.py src/web_server.py src/bot.py static/js/chat.js
git commit -m "feat(web): broadcast transcript events to web + telegram"
```

---

## Task 10: Toolbar (proyectos, captura, stop)

**Files:** Modify `static/index.html`, create `static/js/toolbar.js`

**Step 1: Agregar barra de botones**

Reemplazar `<header>` en `index.html`:

```html
  <header class="border-b border-amber-700/40 p-4 flex justify-between items-center">
    <h1 class="text-2xl font-bold tracking-wider">🦇 Batcave — Jeffri al servicio</h1>
    <div class="flex gap-2 items-center">
      <button id="btn-projects" class="bg-amber-700 hover:bg-amber-600 px-3 py-1 rounded text-sm">📁 Proyectos</button>
      <button id="btn-capture" class="bg-amber-700 hover:bg-amber-600 px-3 py-1 rounded text-sm">📸 Captura</button>
      <button id="btn-stop" class="bg-red-700 hover:bg-red-600 px-3 py-1 rounded text-sm">⏹ Stop</button>
      <div id="status" class="text-sm text-amber-300/70 ml-4">Conectando...</div>
    </div>
  </header>
```

Antes del `</body>`:
```html
<script type="module" src="/static/js/toolbar.js"></script>
```

**Step 2: Crear `static/js/toolbar.js`**

```javascript
import { listProjects, switchProject, capture, stopClaude } from './api.js';
import { addSystemMessage } from './state.js';

document.getElementById('btn-projects').onclick = async () => {
  const projects = await listProjects();
  showProjectPicker(projects);
};

document.getElementById('btn-capture').onclick = async () => {
  try {
    const data = await capture();
    const wrap = document.createElement('div');
    wrap.className = 'msg-jeffri';
    const img = document.createElement('img');
    img.src = `data:image/png;base64,${data.png_b64}`;
    img.className = 'max-w-full rounded';
    wrap.appendChild(img);
    document.getElementById('messages').appendChild(wrap);
  } catch (e) {
    addSystemMessage(`❌ ${e.message}`);
  }
};

document.getElementById('btn-stop').onclick = async () => {
  await stopClaude();
  addSystemMessage('⏹ ESC enviado a Claude');
};

function showProjectPicker(projects) {
  const modal = document.createElement('div');
  modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-50';

  const dialog = document.createElement('div');
  dialog.className = 'bg-slate-800 border border-amber-700 rounded p-6 max-w-md w-full max-h-[80vh] overflow-y-auto';

  const title = document.createElement('h2');
  title.className = 'text-xl font-bold mb-4';
  title.textContent = '📁 Proyectos';
  dialog.appendChild(title);

  const list = document.createElement('div');
  list.className = 'space-y-2';
  dialog.appendChild(list);

  projects.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'block w-full text-left bg-slate-700 hover:bg-slate-600 px-3 py-2 rounded';
    btn.textContent = `📁 ${p.display_name} · ${p.session_count}`;
    btn.onclick = async () => {
      modal.remove();
      try {
        await switchProject(p.display_name);
        addSystemMessage(`✅ Cambiado a ${p.display_name}`);
      } catch (e) {
        addSystemMessage(`❌ ${e.message}`);
      }
    };
    list.appendChild(btn);
  });

  const close = document.createElement('button');
  close.textContent = 'Cerrar';
  close.className = 'mt-4 bg-red-700 px-3 py-1 rounded';
  close.onclick = () => modal.remove();
  dialog.appendChild(close);

  modal.appendChild(dialog);
  document.body.appendChild(modal);
}
```

**Step 3: Smoke test**

Click "📁 Proyectos" → modal con lista. Tocar uno → cambia. "📸 Captura" → screenshot. "⏹ Stop" → ESC.

**Step 4: Commit**

```bash
git add static/index.html static/js/toolbar.js
git commit -m "feat(web): toolbar with projects/capture/stop"
```

---

## Resumen MVP-1

11 tasks. ~1 semana o menos por el atajo de assets reusados.

Despues queda funcional:
- Chat web en `localhost:8000` con sprites pixel reales (no placeholders)
- Canvas 2D vanilla (sin Phaser, mas liviano)
- Enhancer Groq con confirmacion
- Eventos del transcript reenviados a la web
- Toolbar proyectos/captura/stop
- Telegram en paralelo

---

## Fases posteriores (docs separados)

### MVP-2 (1-2 semanas): Sub-agentes visualizados
- Detectar `tool_use` con `name == "Task"` en el transcript
- Spawn de NPCs adicionales en el canvas (otros `char_*.png`)
- Animaciones "trabajando" (cambio de sprite, opacidad, bocadillos)
- Reporte final del jefe del laboratorio

### MVP-3 (2-4 semanas): Computer use real
- Modulo `src/computer_use.py` con primitivas
- Integrar UI-TARS o Open Interpreter
- Browser automation con Playwright
- Animacion Jeffri "saliendo del escritorio"
- Customizar sprite de Jeffri-Alfred (corbatin pintado a mano)
