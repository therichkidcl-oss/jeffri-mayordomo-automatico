# Jeffri Voz — Diseño

**Fecha:** 2026-07-31
**Estado:** Diseño aprobado (arquitectura A), pendiente plan de implementación
**Autor:** Sir Rich + Claude (sesión de brainstorming)

## 1. Problema y objetivo

Hoy Jeffri es un bot de Telegram que hace de puente hacia Claude Code Desktop
(el usuario manda texto/voz/fotos por Telegram y Jeffri los pega en Claude,
reenviando las respuestas). Dos necesidades nuevas:

1. **Arreglar y mejorar Jeffri de Telegram**: la transcripción de audio (Groq
   Whisper) y el mejorador de prompts fallaban, y algún comando no respondía.
   Se confirmó que la API de Groq FUNCIONA (keys válidas, modelos disponibles,
   chat/completions responde OK), así que la falla es interna del bot.
2. **Crear "Jeffri Voz" local**: una capa conversacional por voz en la PC. El
   usuario habla, un **cerebro conversacional (DeepSeek)** conversa con él,
   investiga, opina y sugiere; cuando el usuario quiere ejecutar/construir, el
   cerebro redacta un prompt "masticado y mejorado", lo confirma por voz, y se
   lo pasa a Claude (el "trabajador pesado"). Cuando Claude responde, el cerebro
   condensa la salida y se la habla al usuario.

Ambos sistemas deben **convivir** (Telegram para cuando el usuario está fuera de
casa, Voz para cuando está en la PC) y **compartir** el puente a Claude y la
transcripción local.

## 2. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Arquitectura | **A**: un proceso, núcleo compartido, 2 interfaces (Telegram + Voz) |
| Activación de voz | Push-to-talk: mantener **F9** para hablar, soltar para enviar |
| Disparo a Claude | **Confirma cada vez**: antes de mandar, el cerebro pregunta por voz y el usuario confirma sí/no |
| Rol del cerebro | Compañero conversacional que charla, **investiga**, opina y sugiere; solo la ejecución de código/trabajo va a Claude (prompt refinado) |
| Investigar | Conocimiento propio + **búsqueda web solo cuando haga falta** |
| Cerebro | **DeepSeek** vía API (cliente OpenAI-compatible), key en `.env` |
| STT (voz→texto) | **faster-whisper local**, modelo `small` int8 español (upgradeable a `medium`). Reemplaza Groq Whisper. $0, sin API, offline |
| TTS (texto→voz) | **Piper**, voz español neutro. Local, gratis |
| Búsqueda web | **DuckDuckGo** (librería `ddgs`, sin API key, gratis) |
| Coordinación | Un solo `ClaudeController` + un solo `send_lock` compartido; el watcher emite eventos a ambas interfaces |

## 3. Arquitectura (Approach A)

Un solo proceso Python; núcleo compartido + dos interfaces concurrentes (asyncio).

```
src/
├── core/                        # COMPARTIDO
│   ├── config.py                # .env unificado
│   ├── claude_controller.py     # puente a Claude Desktop (reciclado)
│   ├── transcript_watcher.py    # vigila el .jsonl de Claude (reciclado)
│   ├── session_detector.py      # sesión activa + proyectos (reciclado)
│   ├── session_tracker.py       # dedup de cambio de sesión (reciclado)
│   ├── formatters.py            # eventos de Claude → mensajes (reciclado)
│   ├── security.py              # whitelist + destructivo (reciclado)
│   └── stt.py                   # NUEVO: faster-whisper local
├── telegram/
│   ├── bot.py                   # handlers de Telegram (refactor de bot.py)
│   ├── menu.py                  # menú + teclado (reciclado)
│   └── groq_client.py           # mejorador de prompts de texto (reciclado)
├── voice/
│   ├── app.py                   # loop push-to-talk + orquestación
│   ├── brain.py                 # cerebro conversacional (estado + política)
│   ├── deepseek_client.py       # cliente API DeepSeek
│   ├── tts.py                   # Piper
│   ├── audio_io.py              # captura mic + hotkey F9
│   └── search.py                # búsqueda web (DuckDuckGo)
└── main.py                      # entrypoint: arranca ambas interfaces
```

**Coordinación clave:**
- **Un `ClaudeController` compartido** con **un `send_lock`** (asyncio.Lock).
  Telegram y Voz adquieren el mismo lock antes de escribirle a Claude → jamás
  se pisan.
- **El watcher emite a AMBAS interfaces** vía un pequeño fan-out de callbacks:
  Telegram reenvía como mensaje; Voz se lo pasa al cerebro para resumir y hablar.
- `main.py` corre las dos interfaces en el mismo loop asyncio. La tarea
  programada "Jeffri Telegram Bot" (ya existe) mantiene el proceso vivo.

## 4. Flujo de voz (una conversación completa)

```
1. Usuario mantiene F9 y habla ("oye, ¿qué opinas de usar Redis para cachear?")
2. Suelta F9 → audio_io entrega el buffer de audio
3. core/stt.py (faster-whisper) transcribe local → texto
4. voice/brain.py manda el texto al cerebro (DeepSeek) con el historial
5. DeepSeek decide el tipo de turno:
   a. CHARLA/OPINIÓN → responde con su conocimiento (y si hace falta, busca web)
   b. EJECUCIÓN → redacta un prompt refinado para Claude y pide confirmación
6. tts.py (Piper) habla la respuesta del cerebro
7a. Si fue charla → vuelve al paso 1 (sigue la conversación)
7b. Si fue ejecución → el cerebro pregunta por voz "¿Se lo mando a Claude así?"
    - Usuario dice "sí/dale/hazlo" → se detecta la afirmación → dispatch
    - Usuario dice "no/cambia X" → vuelve a conversar y ajustar
8. Dispatch: brain adquiere send_lock → claude_controller.send(prompt_refinado)
9. Claude trabaja; el watcher emite eventos según Claude escribe
10. El cerebro condensa esos eventos → "Claude ya arregló el login, dice que
    faltan 2 tests" → tts habla el resumen
11. Vuelve al paso 1
```

**Detección de confirmación (paso 7b):** el cerebro devuelve un estado
`awaiting_confirmation` con el prompt candidato. El siguiente turno de voz se
interpreta como sí/no vía DeepSeek (o una lista de frases afirmativas/negativas
como atajo rápido antes de llamar al LLM).

## 5. El cerebro (DeepSeek)

- **Cliente**: `deepseek_client.py`, endpoint OpenAI-compatible de DeepSeek
  (`https://api.deepseek.com`), key `DEEPSEEK_API_KEY` en `.env`.
- **System prompt**: define el rol (compañero que conversa, investiga, opina,
  sugiere; NO ejecuta; cuando el usuario quiere ejecutar, produce un prompt
  para Claude). Español latino neutro con "tú", trata al usuario como "Sir Rich",
  sin voseo argentino.
- **Herramientas (tool calling)**:
  - `web_search(query)` → DuckDuckGo, solo cuando el cerebro juzga que necesita
    info actual.
  - `dispatch_to_claude(prompt)` → NO ejecuta directo: pone el sistema en
    `awaiting_confirmation` y devuelve el prompt para que el usuario confirme.
  - `summarize_claude(events)` → condensa la salida de Claude en 1-3 frases
    habladas.
- **Memoria de conversación**: ventana rodante del diálogo (últimos N turnos)
  para mantener el hilo. Sin persistencia entre reinicios en v1 (YAGNI).
- **Estado**: `brain.py` mantiene una pequeña máquina de estados:
  `idle → conversing → awaiting_confirmation → dispatched → summarizing → idle`.

## 6. Piezas nuevas — detalle técnico

| Pieza | Librería | Notas |
|---|---|---|
| STT | `faster-whisper` | Modelo `small` int8, `language="es"`. Carga el modelo una vez al iniciar. Corre en CPU (Ryzen 9 9950X = rápido). Reemplaza `groq_client.transcribe`. |
| TTS | `piper-tts` | Voz español (ej. `es_MX-ald-medium` o `es_ES-...`). Descarga del modelo `.onnx` en setup. Reproduce por `sounddevice`. |
| Audio in | `sounddevice` + `pynput` | `pynput` para el hotkey global F9 (hold/release); `sounddevice` graba mientras F9 está presionado. |
| Búsqueda web | `ddgs` (DuckDuckGo) | Sin API key, gratis. El cerebro la llama como tool. |
| DeepSeek | `httpx` (ya está) | OpenAI-compatible; reutilizamos el patrón de `groq_client`. |

## 7. Arreglos de Telegram (Fase 1)

1. **Audio → faster-whisper local**: `on_voice_or_audio` deja de usar
   `groq.transcribe` y usa `core/stt.py`. Esto arregla la transcripción y
   elimina la dependencia de Groq para audio.
2. **Bug del mejorador / "no se detiene"**: se confirmó que Groq chat funciona.
   Durante la implementación se agrega **logging a archivo** (`logs/jeffri.log`),
   se reproduce el fallo con el bot instrumentado, se encuentra la causa raíz
   (probable: `enhancer_enabled` quedó en False, o una excepción silenciada en
   `_process_user_text`, o el handler nuevo del teclado interceptando texto que
   no debía) y se corrige con un test. NO se parchea a ciegas.
3. El mejorador de **texto** de Telegram sigue con Groq (funciona). El de **voz**
   ahora transcribe local y el mejorado sigue por Groq (o se evalúa moverlo).

## 8. Manejo de errores

| Fallo | Respuesta |
|---|---|
| DeepSeek API cae | El cerebro avisa por voz "no pude pensar, reintenta" y no dispara nada |
| faster-whisper falla al transcribir | TTS dice "no te entendí, repite" |
| Piper falla | Fallback: imprime el texto en consola/log (no bloquea) |
| Claude Desktop cerrado / PC bloqueada | `ClaudeNotOpenError`/`PCLockedError` → el cerebro lo dice por voz |
| F9 no captura audio | Log + aviso; no crashea el loop |
| Búsqueda web falla | El cerebro opina solo con su conocimiento y lo aclara |
| Ambas interfaces piden Claude a la vez | El `send_lock` serializa; una espera |

## 9. Testing

- **Núcleo (TDD, sin audio real)**: `stt.py` contra un WAV de prueba corto;
  `brain.py` (máquina de estados: idle→conversing→awaiting_confirmation→dispatch)
  con un cliente DeepSeek mockeado; `deepseek_client` con httpx mockeado;
  `search.py` con respuesta mockeada.
- **Refactor a `core/`**: los 65 tests existentes deben seguir pasando (solo
  cambian rutas de import). Es la red de seguridad del refactor.
- **Integración manual**: probar el loop de voz completo en la PC (F9 → hablar →
  escuchar respuesta → confirmar → ver que Claude recibe el prompt).
- `superpowers:verification-before-completion` antes de dar por hecho cada fase.

## 10. Fases (entrega incremental)

**Fase 1 — Jeffri Telegram sano + faster-whisper (prioridad):**
- Refactor a `core/` + `telegram/` (sin cambio de comportamiento; tests pasan)
- `core/stt.py` con faster-whisper local; Telegram lo usa para audio
- Encontrar y arreglar el bug del mejorador / comandos (con logging + test)
- Reactivar la tarea programada → Telegram funcionando de nuevo
- **Valor**: devuelve al usuario su herramienta diaria, ya arreglada.

**Fase 2 — Jeffri Voz:**
- `voice/audio_io.py` (F9 + captura), `voice/tts.py` (Piper)
- `voice/deepseek_client.py` + `voice/brain.py` (cerebro + estados)
- `voice/search.py` (DuckDuckGo)
- `voice/app.py` (loop) + wiring en `main.py` (ambas interfaces)
- Integración con el `ClaudeController` compartido (send_lock, watcher fan-out)
- **Valor**: el nuevo sistema conversacional por voz.

## 11. Requisitos de setup (una vez)

- `pip install faster-whisper piper-tts sounddevice pynput ddgs` (+ deps)
- Descargar modelo faster-whisper `small` (automático en primer uso) y voz Piper
- Añadir `DEEPSEEK_API_KEY=...` al `.env` (el usuario la obtiene en
  https://platform.deepseek.com/). **Es el único dato que el usuario debe pegar**
  para activar la voz; Telegram + faster-whisper funcionan sin esto.

## 12. Fuera de alcance (v1)

- Persistencia del historial de conversación entre reinicios
- Wake word / always-listening (se eligió push-to-talk)
- Interrupciones de voz mientras el TTS habla (barge-in)
- Multi-idioma (solo español)
- GUI (es un servicio de fondo + hotkey)
- Migrar el cerebro a Ollama local (se hará cuando llegue la GPU; queda
  configurable el backend del cerebro para facilitarlo)
