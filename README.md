# 🎩 Jeffri — Mayordomo Automático

> Tu mayordomo personal en Telegram que controla Claude Code Desktop por vos.
> Hablale por texto, voz o foto y Jeffri se encarga de que Claude haga el trabajo.

**Jeffri** es un bot de Telegram que se conecta a tu instalación local de **Claude Code Desktop**. Cuando no estás frente al PC, le mandás un mensaje a Jeffri por Telegram y él:

1. Lo recibe en tu PC (que sigue corriendo en casa).
2. Lo mejora con Groq (corrige tildes, puntuación).
3. Te pide confirmación con `[✅ Mandar mejorado] [📤 Original] [❌ Cancelar]`.
4. Lo pega en la ventana de Claude Code Desktop como si lo hubieras tipeado tú.
5. Reenvía a tu Telegram lo que Claude responde, screenshots del navegador incluidos.

Todo usando **tu plan Max de Claude Code** — cero costos de API.

---

## 📜 ¿Por qué Jeffri?

Imagínate que estás afuera y te acordás de un bug que querés arreglar en tu proyecto. Sin Jeffri tendrías que esperar a llegar a casa. Con Jeffri:

```
Vos en Telegram: 🎙 (audio) "oye, arregla el login que ayer me reportaron error"
Jeffri:          🎙 Transcribiendo con Whisper, Sir Rich...
Jeffri:          🎙 Original: Oye, arregla el login que ayer me reportaron error.
                 ✨ Mejorado: Arregla el login. Ayer me reportaron un error allí.
                 [✅ Mandar mejorado] [📤 Original] [❌ Cancelar]
Vos:             [✅ Mandar mejorado]
Jeffri:          ✅ Enviando versión mejorada, Sir Rich...
                 (el texto aparece en Claude Code Desktop en tu PC y Claude empieza
                  a trabajar; las respuestas te llegan al chat de Telegram)
```

---

## 🚀 Instalación (3 pasos, ~10 minutos)

### 1️⃣ Requisitos previos

| Requisito | Cómo verificar |
|---|---|
| Windows 10/11 | `winver` |
| Python 3.13+ | `python --version` |
| Claude Code Desktop instalado y autenticado con tu plan Max | Abrilo y verificá que podés chatear |
| Git (opcional, solo para clonar) | `git --version` |

> **Importante**: el bot usa la autenticación de Claude Code Desktop, no la API directa. Si tenés la variable `ANTHROPIC_API_KEY` en el entorno, el bot la ignora — perfecto.

### 2️⃣ Clonar e instalar dependencias

```powershell
# Clonar el repo
git clone https://github.com/<tu-usuario>/jeffri-mayordomo-automatico.git
cd jeffri-mayordomo-automatico

# Crear entorno virtual e instalar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell rechaza ejecutar scripts, corré una sola vez:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 3️⃣ Configurar `.env`

Copiá la plantilla:
```powershell
Copy-Item .env.example .env
```

Editá `.env` con tus valores:

```env
# Token del bot de Telegram (paso A más abajo)
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...

# Tu user_id de Telegram (paso B)
TELEGRAM_ALLOWED_USER_ID=123456789

# Ruta a la carpeta de proyectos de Claude (no cambiar a menos que sepas qué hacés)
CLAUDE_PROJECTS_DIR=C:\Users\TU_USUARIO\.claude\projects

# (Opcional) API keys de Groq para enhancer + transcripción de audio.
# Sin keys, el bot funciona pero sin mejora de prompts ni transcripción de voz.
GROQ_API_KEYS=gsk_xxx,gsk_yyy,gsk_zzz
```

**A. Crear bot de Telegram**:
1. En Telegram, abrí `@BotFather`.
2. Mandá `/newbot`.
3. Elegí nombre (cualquier cosa, ej: "Jeffri IA") y username (debe terminar en `bot`, ej: `mi_jeffri_bot`).
4. Copiá el token que te da (`123456789:ABC-DEF...`) al `.env`.

**B. Obtener tu user_id**:
1. En Telegram, abrí `@userinfobot`.
2. Pulsá `/start`.
3. Copiá tu user_id (~10 dígitos) al `.env`.

**C. (Opcional) Obtener keys de Groq**:
1. Andá a [console.groq.com/keys](https://console.groq.com/keys).
2. Creá una o más API keys (gratis hasta cierto cuota).
3. Pegalas separadas por coma en `GROQ_API_KEYS`.

### 4️⃣ Probar

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Debería decir `48 passed`. Si no, algo está mal con la instalación.

### 5️⃣ Arrancar

Doble-click en `run.bat`, o desde terminal:
```powershell
.\.venv\Scripts\Activate.ps1
python -m src.bot
```

En Telegram, mandale `/start` a tu bot. Debería responder con la sesión activa.

---

## 📱 Comandos de Telegram

| Comando | Qué hace |
|---|---|
| `/start` | Bienvenida + nombre de la sesión activa detectada |
| `/estado` | Muestra si Jeffri está activo/pausado, sesión actual, estado de Groq |
| `/proyectos` | Lista tus proyectos de Claude Code con botones. Tocá uno → cambia de sesión automáticamente |
| `/sesiones` | Lista plana de las 10 sesiones más recientes (sin agrupar por proyecto) |
| `/captura` | Screenshot de la ventana de Claude Desktop, te llega como foto |
| `/stop` | Manda ESC a Claude (lo interrumpe si está trabajando) |
| `/enhancer on/off` | Activa o desactiva el pulidor Groq. Si está OFF, los textos van crudos a Claude |
| `/parar` | Pausa el reenvío PC→Telegram (Claude sigue trabajando pero no recibís updates) |
| `/seguir` | Reanuda el reenvío |
| `/debug_ui` | Dump de los elementos UI visibles (para diagnóstico) |
| `/ayuda` | Lista de todos los comandos |

### 📥 Tipos de entrada que soporta

| Entrada en Telegram | Qué pasa |
|---|---|
| **Texto** | Pasa por Groq (pulido) → mostrá Original/Mejorado con botones → al confirmar, pega en Claude |
| **Voz/audio** | Whisper transcribe → Groq pule → mostrá Original/Mejorado con botones → al confirmar, pega en Claude |
| **Foto** | Se copia al clipboard como imagen → pega en Claude (con caption si pusiste uno) |
| **Texto destructivo** (`deploy`, `borra`, `rm`, `delete`, `drop`, `git push --force`, `producción`, etc.) | Pide confirmación Sí/No antes de pegar |

### 🎯 Cambiar de proyecto (flujo visual)

1. Tocá `/proyectos` en Telegram.
2. Te aparece una lista: `📁 IA-HUB · 4`, `📁 MiBot · 1`, etc. (el número es cuántas sesiones tiene cada proyecto).
3. Tocás el que quieras (ej: `📁 IA-HUB`).
4. Jeffri toma screenshot del sidebar de Claude Desktop, busca "IA-HUB" con OCR, calcula coordenadas y hace click. La sesión se abre en tu PC.
5. Ahora cuando mandes mensajes, van a esa sesión.

---

## 🛡️ Seguridad

- **Whitelist obligatoria**: solo el `TELEGRAM_ALLOWED_USER_ID` del `.env` puede usar el bot. Los demás se ignoran silenciosamente (y se logean como warning).
- **`.env` está `.gitignore`'d**: tu token y user_id nunca van al repo.
- **Confirmación destructiva**: comandos peligrosos requieren tap Sí/No.
- **Sin cloud**: todo corre en tu PC. Los audios, imágenes y textos no se guardan en servidores externos (excepto el procesamiento momentáneo de Groq para enhancer/Whisper).

---

## ⚠️ Limitaciones

- La PC debe estar **prendida y desbloqueada** (no funciona con Win+L).
- **Claude Code Desktop debe estar abierto** (en cualquier sesión).
- Si tenés **varias ventanas de Claude** abiertas, Jeffri usa la primera visible.
- El cambio de proyecto usa OCR — funciona bien con la mayoría de los proyectos pero puede fallar si:
  - El proyecto está fuera de vista en el sidebar (hay que scrollear).
  - El OCR lee mal el texto (ej: `IA-HUB` lo confunde con `IA+UB`). Jeffri tiene matching fuzzy para esto, pero no es perfecto.
- El input del chat se localiza por coordenadas aproximadas (mitad horizontal, 80px desde abajo). En resoluciones muy distintas puede caer en otro lado — si pasa, decímelo y ajustamos las constantes.

---

## 🧠 Cómo funciona por dentro

```
                    Tu celular (Telegram)
                            ↕
              ┌─────────────────────────────┐
              │  Jeffri (Python en tu PC)   │
              ├─────────────────────────────┤
              │ • bot.py     handlers Telegram        │
              │ • config.py  carga .env               │
              │ • groq_client      enhancer + Whisper │
              │ • formatters       eventos → Telegram │
              │ • security         whitelist + destr  │
              │ • session_detector  qué sesión usar   │
              │ • transcript_watcher  vigila .jsonl   │
              │ • claude_controller  UI + OCR + click │
              └─────────────────────────────┘
                            ↕
              ┌─────────────────────────────┐
              │   Claude Code Desktop       │
              │   (tu sesión activa)        │
              └─────────────────────────────┘
                            ↕
              C:\Users\TU\.claude\projects\
                   <proyecto>\<uuid>.jsonl
              ← se actualiza en tiempo real
                cada vez que Claude habla
```

### Flujo end-to-end

1. **Vos mandás algo por Telegram** (texto, voz, foto).
2. **`bot.py` lo recibe**, valida que sea tu user_id, lo procesa según tipo:
   - Voz → `groq_client.transcribe()` con Whisper.
   - Texto/transcripción → `groq_client.enhance_prompt()` con llama-3.3-70b para pulir.
3. **Te muestra confirmación** con botones (Original/Mejorado/Cancelar).
4. Al confirmar, **`claude_controller`** toma el control:
   - Encuentra la ventana de Claude Desktop.
   - Hace click en el área del input del chat.
   - Copia tu texto al clipboard y manda Ctrl+V, después Enter.
5. **Claude empieza a trabajar**. Cada cosa que escribe se va guardando en el `.jsonl` de la sesión.
6. **`transcript_watcher`** vigila ese `.jsonl` con `watchdog`. Cada línea nueva la parsea con `formatters` y la manda a tu Telegram.
7. **Filtro**: solo se reenvían mensajes de texto del asistente y screenshots del navegador (Playwright/Chrome). Los tool calls de Read/Edit/Bash NO se reenvían (sería spam).

---

## 🧪 Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Cubre los módulos puros (config, session_detector, formatters, security, transcript_watcher). El `bot.py` y `claude_controller.py` son integration points — se validan con smoke test manual.

---

## 🐛 Troubleshooting

### "No encontré ninguna ventana de Claude Desktop"
Abrí Claude Code Desktop. Sí, literalmente.

### "Tu PC está bloqueada"
Desbloqueala (escribí tu contraseña de Windows).

### Mando un mensaje pero Claude no recibe nada
- ¿El bot está corriendo? Mirá si `run.bat` sigue abierto o si la terminal muestra logs.
- ¿Está pausado? Mandá `/estado`.
- ¿El input del chat está visible? Tiene que estar al fondo de la ventana de Claude Desktop.

### `/proyectos` → toco un proyecto y no cambia
- El proyecto puede estar fuera de vista en el sidebar. Scrolleá manualmente y reintenta.
- Si el OCR lee mal el nombre, mandá `/debug_ui` para ver qué textos detecta.

### El enhancer hace al texto "conversacional" (responde en vez de pulir)
- Probablemente el modelo se confundió. Mandá `/enhancer off` para deshabilitarlo temporalmente.

### Pierdo el bot porque me trabé en otra ventana
- El bot sigue corriendo en background. Volvé a la terminal donde está y leé los logs.
- Si lo cerraste sin querer, doble-click en `run.bat` otra vez.

---

## 📚 Más detalles

- [Diseño y arquitectura](docs/plans/2026-05-13-telegram-claude-bridge-design.md)
- [Plan de implementación](docs/plans/2026-05-13-telegram-claude-bridge-plan.md)
- [Para Claude: instrucciones de auto-instalación](CLAUDE.md)

---

## ⚖️ Licencia

Uso personal. No es producto comercial. Anthropic's terms of service para Claude Code Desktop aplican — la autenticación OAuth es para uso individual.

---

🎩 *— A su servicio, Sir Rich.*
