# 🎩 Jeffri — Mayordomo automatico

> *"A su servicio."* — Un bot de Telegram con tono de mayordomo que opera tu
> Claude Code Desktop en remoto. Hablale por texto, voz o foto desde el
> celular; Jeffri lo pule con DeepSeek y lo pega en Claude por ti.

**Jeffri** vive en tu PC. Cuando estas afuera y te acuerdas de algo que
quieres pedirle a Claude, le mandas un mensaje a Jeffri por Telegram y el:

1. Lo recibe en tu PC (encendida y desbloqueada).
2. Lo pule con **DeepSeek V4.1-Flash** (corrige tildes, ordena las frases, lo convierte en un prompt accionable).
3. Te pregunta en Telegram con `[✅ Mandar mejorado] [📤 Original] [❌ Cancelar]`.
4. Lo pega en Claude Code Desktop como si lo hubieses tipeado.
5. Reenvia a tu Telegram las respuestas de Claude, incluidos screenshots.

Jeffri usa **tu plan de Claude Code** por autenticacion local — no gasta API
de Anthropic.

---

## 🎓 Como se dirige a ti

La primera vez que mandes `/start`, Jeffri te preguntara:

> *"🎩 A su servicio. Soy Jeffri, su mayordomo. Antes de ponerme a su
> disposicion, permitame una pregunta: ¿como desea que me dirija a usted?
> Puede responder con el titulo que prefiera — por ejemplo `Sir Smith`,
> `Doña Maria`, `Jefa`, `Doctor`, `Capitan`, o cualquier forma que sea de
> su agrado. Lo recordare en adelante."*

Tu respondes como quieras (`Jefa`, `Patron`, `Mi reina`, etc.) y Jeffri te
tratara asi para siempre. Puedes cambiarlo despues con `/titulo Nuevo Titulo`
o resetearlo con `/titulo reset`.

---

## 🚀 Instalacion (10 minutos)

### Requisitos previos

| Requisito | Como verificar |
|---|---|
| **Windows 10 u 11** | `winver` |
| **Python 3.13+** | `python --version` |
| **Claude Code Desktop** instalado y autenticado con tu plan | abrelo y verifica que puedes chatear con Claude |
| **Git** (para clonar) | `git --version` |

> ℹ️ El bot usa la autenticacion local de Claude Code Desktop, no la API.
> Si tienes `ANTHROPIC_API_KEY` en el entorno, el bot la ignora.

### 1. Clonar e instalar

```powershell
git clone https://github.com/therichkidcl-spec/jeffri-mayordomo-automatico.git
cd jeffri-mayordomo-automatico

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell rechaza ejecutar scripts, una sola vez:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 2. Configurar `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Rellena por lo menos estos 3 campos:

**(a) Token del bot de Telegram** — en Telegram abre `@BotFather`:
```
/newbot
→ (elige nombre, ej. "Jeffri IA")
→ (elige username, debe terminar en bot, ej. mi_jeffri_bot)
→ Copia el token (123456789:ABC-DEF...) a TELEGRAM_BOT_TOKEN
```

**(b) Tu user_id de Telegram** — abre `@userinfobot`:
```
/start
→ Copia el numero (10 digitos) a TELEGRAM_ALLOWED_USER_ID
```

**(c) Ruta de proyectos de Claude** — cambia `TU_USUARIO` por tu usuario
Windows real en `CLAUDE_PROJECTS_DIR`.

**Opcional (recomendado)**:

**(d) DeepSeek API key** para el enhancer. Si no la pones, el bot funciona
pero manda tus mensajes sin pulir. Obtenla en
[platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)
(cuenta gratis). Pegala en `DEEPSEEK_API_KEY`.

### 3. Verificar

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Debe decir `142 passed`. Si falla, revisa `.env`.

### 4. Arrancar

**Doble-click en `run.bat`**, o desde terminal:
```powershell
.\.venv\Scripts\Activate.ps1
python -m src.main
```

Esto arranca Telegram **y** la voz F9 (si la activaste). Si solo quieres
Telegram sin voz, usa `python -m src.bot`.

En Telegram, escribele `/start` a tu bot. Te preguntara el titulo honorifico
y a partir de ahi, listo.

> 🔒 **Single-instance lock**: Jeffri guarda su PID en `logs/jeffri.pid`.
> Si intentas arrancarlo dos veces, el segundo se bloquea con un mensaje
> claro. Esto previene duplicados en Telegram.

---

## 📱 Comandos

| Comando | Que hace |
|---|---|
| `/start` | Bienvenida + sesion activa. Primera vez: pregunta tu titulo honorifico |
| `/titulo [nuevo]` | Ver o cambiar como Jeffri se dirige a ti. `/titulo reset` lo borra |
| `/estado` | Estado del bot: activo/pausado, sesion actual, enhancer on/off |
| `/proyectos` | Lista proyectos de Claude. Tocas uno → cambia la sesion automaticamente |
| `/sesiones` | Lista plana de las 10 sesiones recientes |
| `/captura` | Screenshot de la ventana de Claude Desktop |
| `/stop` | Manda ESC a Claude (lo interrumpe) |
| `/enhancer on/off` | Activa o desactiva el pulidor DeepSeek |
| `/parar` | Pausa el reenvio PC→Telegram |
| `/seguir` | Reanuda el reenvio |
| `/fijar` | Fija el bot a la sesion actual (evita flip-flop) |
| `/auto` | Vuelve al seguimiento automatico |
| `/ayuda` | Lista todos los comandos |

### Entradas que acepta

| Mandas... | Jeffri hace... |
|---|---|
| **Texto** | DeepSeek lo pule → te muestra Original / Mejorado → al confirmar lo pega en Claude |
| **Voz / audio** | `faster-whisper` lo transcribe LOCAL → DeepSeek lo pule → confirmas → va a Claude |
| **Foto** | La copia al clipboard → la pega en Claude (con caption si pones texto) |
| **Texto destructivo** (`deploy`, `borra`, `rm`, `drop`, `push --force`, `produccion`...) | Pide confirmacion Si/No antes de pegar |

### Push-to-talk F9 (voz local)

Si `VOICE_ENABLED=true` en `.env`, cuando ejecutas `python -m src.main` tienes
un loop de voz:

1. Manten **F9** presionada y habla.
2. Al soltar, `faster-whisper` transcribe local, DeepSeek entiende, Piper
   responde con TTS natural de mayordomo.
3. Si tu pedido es ejecutable, Jeffri propone un prompt y pide confirmacion
   por voz antes de pasarlo a Claude.

Los modelos de Piper viven en `voice_models/` (se descargan la primera vez).

---

## 🛡️ Seguridad

- **Whitelist estricta**: solo el `TELEGRAM_ALLOWED_USER_ID` del `.env` puede
  usar el bot. Los demas se ignoran silenciosamente y se logean como warning.
- **`.env` gitignoreado**: tu token y user_id nunca van al repo.
- **`data/user_settings.json` gitignoreado**: tu titulo honorifico es local.
- **Confirmacion destructiva**: `rm`, `deploy`, etc. requieren tap Si/No.
- **Todo corre local**: los audios, imagenes y textos no van a servidores
  externos (excepto el procesamiento momentaneo de DeepSeek para el enhancer).
- **Single-instance lock**: solo un proceso de Jeffri puede correr a la vez.

---

## 🏗️ Como funciona por dentro

```
            Tu celular (Telegram)
                    ↕
    ┌─────────────────────────────────┐
    │  Jeffri (Python en tu PC)       │
    ├─────────────────────────────────┤
    │ bot.py              handlers Telegram      │
    │ main.py             entrypoint Telegram+Voz │
    │ user_settings.py    titulo honorifico       │
    │ enhancer.py         DeepSeek V4.1-Flash     │
    │ stt.py              faster-whisper local    │
    │ voice/              push-to-talk F9 + TTS   │
    │ transcript_watcher  vigila los .jsonl       │
    │ claude_controller   UI automation + OCR     │
    │ pidfile.py          single-instance lock    │
    └─────────────────────────────────┘
                    ↕
    ┌─────────────────────────────────┐
    │  Claude Code Desktop            │
    │  (tu sesion abierta)            │
    └─────────────────────────────────┘
                    ↕
    C:\Users\<tu>\.claude\projects\
         <proyecto>\<uuid>.jsonl  ← se actualiza
         en tiempo real cuando Claude habla
```

### Flujo end-to-end (texto)

1. Mandas texto por Telegram.
2. `bot.py` valida tu user_id y detecta si es destructivo.
3. Si no es destructivo y DeepSeek esta disponible, `enhancer.py` lo pule
   usando `deepseek-flash` con thinking mode DESACTIVADO.
4. Te muestra Original / Mejorado con botones.
5. Al confirmar, `claude_controller`:
   - Encuentra la ventana de Claude Desktop.
   - Click en el input del chat.
   - Pega via clipboard + Enter.
6. `transcript_watcher` vigila el `.jsonl` de la sesion. Cada evento nuevo:
   `formatters` lo convierte en un mensaje de Telegram que llega a ti.

---

## 🧪 Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

142 tests cubren los modulos puros (config, formatters, security, enhancer,
pidfile, stt, user_settings, voice/brain, etc.). `claude_controller.py` es
integration point — se valida con smoke test manual.

---

## 🐛 Troubleshooting

### "Otra instancia de Jeffri ya corre (PID 1234)"
Ya hay un proceso vivo. Matalo:
```powershell
taskkill /F /PID 1234
Remove-Item logs\jeffri.pid
```
Y vuelve a arrancar.

### "No encontre ninguna ventana de Claude Desktop"
Abre Claude Code Desktop. Literalmente.

### "Tu PC esta bloqueada"
Desbloqueala con Windows+contrasena.

### El bot no responde a mis mensajes
- Verifica que `TELEGRAM_ALLOWED_USER_ID` sea TU user_id (no otro).
- Mira `logs/jeffri.log` — hay un `[WARN]` que dice si un user_id no autorizado
  intento usar el bot.
- Si cambiaste de bot token, borra `logs/jeffri.pid` y reinicia.

### El enhancer no esta puliendo (va directo)
- Verifica que `DEEPSEEK_API_KEY` en `.env` es valida.
- `/estado` te dice si el enhancer esta ON y si DeepSeek esta habilitado.

### Mensajes se duplican en Telegram
- Casi siempre es dos instancias corriendo. Mira:
  ```powershell
  Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match 'src\.(bot|main)' }
  ```
  Si ves mas de 1, matalos todos y arranca uno con `python -m src.main`.
  El pidfile lock impide esto a partir de 2026-09-12 — si lo ves, revisa que
  tengas la version actualizada.

### `/proyectos` → toco un proyecto y no cambia
- El proyecto puede estar fuera de vista en el sidebar de Claude. Scrollea manualmente.
- Si el OCR lee mal el nombre, manda `/debug_ui` para ver que detecta.

### F9 no graba audio para la voz
- Verifica que `VOICE_ENABLED=true` y que arrancaste con `python -m src.main`
  (NO con `src.bot`).
- Verifica que la voz Piper esta descargada en `voice_models/`.
- Si otra app esta usando F9, cambia `VOICE_HOTKEY` en `.env`.

---

## 📂 Estructura

```
src/
├── bot.py              Entrypoint Telegram + handlers
├── main.py             Entrypoint unificado (Telegram + voz F9)
├── config.py           Carga .env
├── user_settings.py    Persistencia del titulo honorifico
├── enhancer.py         Pulidor con DeepSeek
├── stt.py              Transcripcion local con faster-whisper
├── voice/              Loop de voz F9 (DeepSeek + Piper)
├── claude_controller.py  UI automation (pywinauto + OCR + click)
├── transcript_watcher.py Vigila los .jsonl de Claude
├── formatters.py       Eventos .jsonl → mensajes de Telegram
├── session_detector.py Detecta sesion/proyecto activo
├── security.py         Whitelist + deteccion destructiva
├── pidfile.py          Single-instance lock
├── web_server.py       (opcional) FastAPI para UI web local
├── ws_chat.py          (opcional) WebSocket del web UI
└── menu.py             Teclado persistente y menu de comandos

tests/     142 tests que cubren los modulos puros
docs/      disenos y planes historicos
static/    (opcional) UI web local
```

---

## 🤖 Para Claude Code (IA): instalacion asistida

Si tu Claude Code Desktop (u otra IA) te pregunta como ayudarte a instalar
Jeffri, dile:

> *"Lee `CLAUDE.md` del repo e instalame Jeffri siguiendo esos pasos."*

El archivo [`CLAUDE.md`](CLAUDE.md) tiene instrucciones paso a paso para que
la IA haga el setup entero (verificar requisitos, pedirte los tokens, correr
tests, arrancar) sin que tengas que escribir comandos manualmente.

---

## ⚖️ Licencia

MIT — ver [LICENSE](LICENSE).

Jeffri usa la autenticacion local de Claude Code Desktop; los terminos de
servicio de Anthropic para Claude Code aplican a tu uso individual.

---

🎩 *— A sus ordenes.*
