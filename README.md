# 🎩 Jeffri — Mayordomo Automatico

> Tu mayordomo personal en Telegram que controla Claude Code Desktop por ti.
> Hablale por texto, voz o foto y Jeffri se encarga de que Claude haga el trabajo.

**Jeffri** es un bot de Telegram que se conecta a tu instalacion local de **Claude Code Desktop**. Cuando no estas frente al PC, le mandas un mensaje a Jeffri por Telegram y el:

1. Lo recibe en tu PC (que sigue corriendo en casa).
2. Lo mejora con Groq (corrige tildes, puntuacion).
3. Te pide confirmacion con `[✅ Mandar mejorado] [📤 Original] [❌ Cancelar]`.
4. Lo pega en la ventana de Claude Code Desktop como si lo hubieras tipeado tu.
5. Reenvia a tu Telegram lo que Claude responde, screenshots del navegador incluidos.

Todo usando **tu plan Max de Claude Code** — cero costos de API.

---

## 📜 ¿Por que Jeffri?

Imagina que estas afuera y te acuerdas de un bug que quieres arreglar en tu proyecto. Sin Jeffri tendrias que esperar a llegar a casa. Con Jeffri:

```
Tu en Telegram: 🎙 (audio) "oye, arregla el login que ayer me reportaron error"
Jeffri:         🎙 Transcribiendo con Whisper, Sir Rich...
Jeffri:         🎙 Original: Oye, arregla el login que ayer me reportaron error.
                ✨ Mejorado: Arregla el login. Ayer me reportaron un error alli.
                [✅ Mandar mejorado] [📤 Original] [❌ Cancelar]
Tu:             [✅ Mandar mejorado]
Jeffri:         ✅ Enviando version mejorada, Sir Rich...
                (el texto aparece en Claude Code Desktop en tu PC y Claude empieza
                 a trabajar; las respuestas te llegan al chat de Telegram)
```

---

## 🚀 Instalacion (3 pasos, ~10 minutos)

### 1️⃣ Requisitos previos

| Requisito | Como verificar |
|---|---|
| Windows 10/11 | `winver` |
| Python 3.13+ | `python --version` |
| Claude Code Desktop instalado y autenticado con tu plan Max | Abrelo y verifica que puedes chatear |
| Git (opcional, solo para clonar) | `git --version` |

> **Importante**: el bot usa la autenticacion de Claude Code Desktop, no la API directa. Si tienes la variable `ANTHROPIC_API_KEY` en el entorno, el bot la ignora — perfecto.

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

Si PowerShell rechaza ejecutar scripts, corre una sola vez:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 3️⃣ Configurar `.env`

Copia la plantilla:
```powershell
Copy-Item .env.example .env
```

Edita `.env` con tus valores:

```env
# Token del bot de Telegram (paso A mas abajo)
TELEGRAM_BOT_TOKEN=123456789:ABC-DEF...

# Tu user_id de Telegram (paso B)
TELEGRAM_ALLOWED_USER_ID=123456789

# Ruta a la carpeta de proyectos de Claude (no cambiar a menos que sepas que haces)
CLAUDE_PROJECTS_DIR=C:\Users\TU_USUARIO\.claude\projects

# (Opcional) API keys de Groq para enhancer + transcripcion de audio.
# Sin keys, el bot funciona pero sin mejora de prompts ni transcripcion de voz.
GROQ_API_KEYS=gsk_xxx,gsk_yyy,gsk_zzz
```

**A. Crear bot de Telegram**:
1. En Telegram, abre `@BotFather`.
2. Manda `/newbot`.
3. Elige nombre (cualquier cosa, ej: "Jeffri IA") y username (debe terminar en `bot`, ej: `mi_jeffri_bot`).
4. Copia el token que te da (`123456789:ABC-DEF...`) al `.env`.

**B. Obtener tu user_id**:
1. En Telegram, abre `@userinfobot`.
2. Pulsa `/start`.
3. Copia tu user_id (~10 digitos) al `.env`.

**C. (Opcional) Obtener keys de Groq**:
1. Ve a [console.groq.com/keys](https://console.groq.com/keys).
2. Crea una o mas API keys (gratis hasta cierta cuota).
3. Pegalas separadas por coma en `GROQ_API_KEYS`.

### 4️⃣ Probar

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Deberia decir `48 passed`. Si no, algo esta mal con la instalacion.

### 5️⃣ Arrancar

Doble-click en `run.bat`, o desde terminal:
```powershell
.\.venv\Scripts\Activate.ps1
python -m src.bot
```

En Telegram, escribele `/start` a tu bot. Deberia responder con la sesion activa.

---

## 📱 Comandos de Telegram

| Comando | Que hace |
|---|---|
| `/start` | Bienvenida + nombre de la sesion activa detectada |
| `/estado` | Muestra si Jeffri esta activo/pausado, sesion actual, estado de Groq |
| `/proyectos` | Lista tus proyectos de Claude Code con botones. Toca uno → cambia de sesion automaticamente |
| `/sesiones` | Lista plana de las 10 sesiones mas recientes (sin agrupar por proyecto) |
| `/captura` | Screenshot de la ventana de Claude Desktop, te llega como foto |
| `/stop` | Manda ESC a Claude (lo interrumpe si esta trabajando) |
| `/enhancer on/off` | Activa o desactiva el pulidor Groq. Si esta OFF, los textos van crudos a Claude |
| `/parar` | Pausa el reenvio PC→Telegram (Claude sigue trabajando pero no recibes updates) |
| `/seguir` | Reanuda el reenvio |
| `/debug_ui` | Dump de los elementos UI visibles (para diagnostico) |
| `/ayuda` | Lista de todos los comandos |

### 📥 Tipos de entrada que soporta

| Entrada en Telegram | Que pasa |
|---|---|
| **Texto** | Pasa por Groq (pulido) → muestra Original/Mejorado con botones → al confirmar, pega en Claude |
| **Voz/audio** | Whisper transcribe → Groq pule → muestra Original/Mejorado con botones → al confirmar, pega en Claude |
| **Foto** | Se copia al clipboard como imagen → pega en Claude (con caption si pusiste uno) |
| **Texto destructivo** (`deploy`, `borra`, `rm`, `delete`, `drop`, `git push --force`, `produccion`, etc.) | Pide confirmacion Si/No antes de pegar |

### 🎯 Cambiar de proyecto (flujo visual)

1. Toca `/proyectos` en Telegram.
2. Te aparece una lista: `📁 IA-HUB · 4`, `📁 MiBot · 1`, etc. (el numero es cuantas sesiones tiene cada proyecto).
3. Tocas el que quieras (ej: `📁 IA-HUB`).
4. Jeffri toma screenshot del sidebar de Claude Desktop, busca "IA-HUB" con OCR, calcula coordenadas y hace click. La sesion se abre en tu PC.
5. Ahora cuando mandes mensajes, van a esa sesion.

---

## 🛡️ Seguridad

- **Whitelist obligatoria**: solo el `TELEGRAM_ALLOWED_USER_ID` del `.env` puede usar el bot. Los demas se ignoran silenciosamente (y se logean como warning).
- **`.env` esta `.gitignore`'d**: tu token y user_id nunca van al repo.
- **Confirmacion destructiva**: comandos peligrosos requieren tap Si/No.
- **Sin cloud**: todo corre en tu PC. Los audios, imagenes y textos no se guardan en servidores externos (excepto el procesamiento momentaneo de Groq para enhancer/Whisper).

---

## ⚠️ Limitaciones

- La PC debe estar **prendida y desbloqueada** (no funciona con Win+L).
- **Claude Code Desktop debe estar abierto** (en cualquier sesion).
- Si tienes **varias ventanas de Claude** abiertas, Jeffri usa la primera visible.
- El cambio de proyecto usa OCR — funciona bien con la mayoria de los proyectos pero puede fallar si:
  - El proyecto esta fuera de vista en el sidebar (hay que scrollear).
  - El OCR lee mal el texto (ej: `IA-HUB` lo confunde con `IA+UB`). Jeffri tiene matching fuzzy para esto, pero no es perfecto.
- El input del chat se localiza por coordenadas aproximadas (mitad horizontal, 80px desde abajo). En resoluciones muy distintas puede caer en otro lado — si pasa, avisame y ajusto las constantes.

---

## 🧠 Como funciona por dentro

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
              │ • session_detector  que sesion usar   │
              │ • transcript_watcher  vigila .jsonl   │
              │ • claude_controller  UI + OCR + click │
              └─────────────────────────────┘
                            ↕
              ┌─────────────────────────────┐
              │   Claude Code Desktop       │
              │   (tu sesion activa)        │
              └─────────────────────────────┘
                            ↕
              C:\Users\TU\.claude\projects\
                   <proyecto>\<uuid>.jsonl
              ← se actualiza en tiempo real
                cada vez que Claude habla
```

### Flujo end-to-end

1. **Tu mandas algo por Telegram** (texto, voz, foto).
2. **`bot.py` lo recibe**, valida que sea tu user_id, lo procesa segun tipo:
   - Voz → `groq_client.transcribe()` con Whisper.
   - Texto/transcripcion → `groq_client.enhance_prompt()` con llama-3.3-70b para pulir.
3. **Te muestra confirmacion** con botones (Original/Mejorado/Cancelar).
4. Al confirmar, **`claude_controller`** toma el control:
   - Encuentra la ventana de Claude Desktop.
   - Hace click en el area del input del chat.
   - Copia tu texto al clipboard y manda Ctrl+V, despues Enter.
5. **Claude empieza a trabajar**. Cada cosa que escribe se va guardando en el `.jsonl` de la sesion.
6. **`transcript_watcher`** vigila ese `.jsonl` con `watchdog`. Cada linea nueva la parsea con `formatters` y la manda a tu Telegram.
7. **Filtro**: solo se reenvian mensajes de texto del asistente y screenshots del navegador (Playwright/Chrome). Los tool calls de Read/Edit/Bash NO se reenvian (seria spam).

---

## 🧪 Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Cubre los modulos puros (config, session_detector, formatters, security, transcript_watcher). El `bot.py` y `claude_controller.py` son integration points — se validan con smoke test manual.

---

## 🐛 Troubleshooting

### "No encontre ninguna ventana de Claude Desktop"
Abre Claude Code Desktop. Si, literalmente.

### "Tu PC esta bloqueada"
Desbloqueala (escribe tu contrasena de Windows).

### Mando un mensaje pero Claude no recibe nada
- ¿El bot esta corriendo? Mira si `run.bat` sigue abierto o si la terminal muestra logs.
- ¿Esta pausado? Manda `/estado`.
- ¿El input del chat esta visible? Tiene que estar al fondo de la ventana de Claude Desktop.

### `/proyectos` → toco un proyecto y no cambia
- El proyecto puede estar fuera de vista en el sidebar. Scrollea manualmente y reintenta.
- Si el OCR lee mal el nombre, manda `/debug_ui` para ver que textos detecta.

### El enhancer hace al texto "conversacional" (responde en vez de pulir)
- Probablemente el modelo se confundio. Manda `/enhancer off` para deshabilitarlo temporalmente.

### Pierdo el bot porque me trabe en otra ventana
- El bot sigue corriendo en background. Vuelve a la terminal donde esta y lee los logs.
- Si lo cerraste sin querer, doble-click en `run.bat` otra vez.

---

## 📚 Mas detalles

- [Diseno y arquitectura](docs/plans/2026-05-13-telegram-claude-bridge-design.md)
- [Plan de implementacion](docs/plans/2026-05-13-telegram-claude-bridge-plan.md)
- [Para Claude: instrucciones de auto-instalacion](CLAUDE.md)

---

## ⚖️ Licencia

Uso personal. No es producto comercial. Anthropic's terms of service para Claude Code Desktop aplican — la autenticacion OAuth es para uso individual.

---

🎩 *— A su servicio, Sir Rich.*
