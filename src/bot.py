import asyncio
import logging
import time
import uuid
from io import BytesIO

import uvicorn
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.claude_controller import ClaudeController, ClaudeControllerError, ClaudeNotOpenError, PCLockedError
from src.config import (
    ALLOWED_USER_ID,
    CLAUDE_PROJECTS_DIR,
    GROQ_API_KEYS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ENABLED,
    WEB_BIND,
    WEB_ENABLED,
    WEB_PORT,
)
from src.formatters import PhotoMessage, TextMessage, format_event
from src.groq_client import GroqAllKeysFailed, GroqClient, GroqError
from src.menu import KEYBOARD_ROUTES, bot_command_menu, main_reply_keyboard
from src.security import is_destructive, requires_whitelist
from src.session_detector import detect_active_session, list_projects, list_recent_sessions, list_sessions_in_folder
from src.transcript_watcher import TranscriptWatcher
from src.web_server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("watchdog").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class BotState:
    def __init__(self) -> None:
        self.paused: bool = False
        self.pending_destructive: dict[str, str] = {}
        self.pending_enhanced: dict[str, dict[str, str]] = {}
        self.pending_switch: dict[str, str] = {}
        self.pending_project: dict[str, str] = {}
        self.pending_image: dict[str, dict] = {}
        self.processed_tokens: dict[str, float] = {}
        self.enhancer_enabled: bool = True
        self.album_buffers: dict[str, dict] = {}
        self.controller = ClaudeController()
        self.send_lock = asyncio.Lock()
        self.groq: GroqClient | None = GroqClient(GROQ_API_KEYS) if GROQ_API_KEYS else None
        if self.groq is None:
            logger.warning("GROQ_API_KEYS vacio: enhancer y transcripcion deshabilitados")
        else:
            logger.info(f"Groq habilitado con {len(GROQ_API_KEYS)} keys")

    def claim_token(self, token: str) -> bool:
        """Devuelve False si ya esta procesado, True si es nuevo (y lo marca)."""
        now = time.time()
        if len(self.processed_tokens) > 200:
            self.processed_tokens = {k: v for k, v in self.processed_tokens.items() if now - v < 120}
        if token in self.processed_tokens:
            return False
        self.processed_tokens[token] = now
        return True


state = BotState()


@requires_whitelist
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active:
        msg = f"👋 Hola Sir Rich. Sesion activa: `{active.parent.name}`"
    else:
        msg = "👋 Hola Sir Rich. No detecte ninguna sesion activa. Abre Claude Desktop."
    msg += "\n\nUsa el boton *Menu* o los botones de abajo para elegir comandos."
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(),
    )


@requires_whitelist
async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    paused = "⏸️ pausado" if state.paused else "▶️ activo"
    if state.groq is None:
        groq_state = "🤖 Groq deshabilitado (sin keys)"
    elif state.enhancer_enabled:
        groq_state = "🤖 Enhancer ON (texto pasa por Groq)"
    else:
        groq_state = "🤖 Enhancer OFF (texto va directo a Claude)"
    msg = (
        f"Estado: {paused}\n"
        f"Sesion: `{active.parent.name if active else '(ninguna)'}`\n"
        f"{groq_state}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_sesiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions = list_recent_sessions(CLAUDE_PROJECTS_DIR, limit=10)
    if not sessions:
        await update.message.reply_text("No hay sesiones recientes, Sir Rich.")
        return

    buttons = []
    state.pending_switch.clear()
    for s in sessions:
        title = s.title or s.folder_name
        token = uuid.uuid4().hex[:8]
        state.pending_switch[token] = title
        label = f"📁 {title[:55]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"switch:go:{token}")])

    await update.message.reply_text(
        "📋 *Sesiones recientes, Sir Rich:*\nToque una para cambiar.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN,
    )


@requires_whitelist
async def cmd_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    projects = list_projects(CLAUDE_PROJECTS_DIR)
    if not projects:
        await update.message.reply_text("No hay proyectos detectados, Sir Rich.")
        return

    buttons = []
    state.pending_project.clear()
    for p in projects:
        token = uuid.uuid4().hex[:8]
        state.pending_project[token] = f"{p.folder_path}|{p.display_name}"
        label = f"📁 {p.display_name} · {p.session_count}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"proj:open:{token}")])

    await update.message.reply_text(
        "🗂 *Proyectos, Sir Rich:*\nToque uno para ver sus sesiones.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN,
    )


@requires_whitelist
async def cmd_parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.paused = True
    await update.message.reply_text("⏸️ Reenvio pausado, Sir Rich. /seguir para reanudar.")


@requires_whitelist
async def cmd_seguir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.paused = False
    await update.message.reply_text("▶️ Reenvio reanudado, Sir Rich.")


@requires_whitelist
async def cmd_enhancer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = (context.args or [])
    if args:
        arg = args[0].lower()
        if arg in ("on", "activar", "si"):
            state.enhancer_enabled = True
        elif arg in ("off", "desactivar", "no"):
            state.enhancer_enabled = False
        else:
            await update.message.reply_text("Usa `/enhancer on` o `/enhancer off`, Sir Rich.")
            return
    else:
        state.enhancer_enabled = not state.enhancer_enabled
    estado = "ON ✨" if state.enhancer_enabled else "OFF (texto va directo)"
    await update.message.reply_text(f"Enhancer: *{estado}*, Sir Rich.", parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with state.send_lock:
            await state.controller.interrupt()
        await update.message.reply_text("⏹ ESC enviado, Sir Rich. Claude interrumpido.")
    except (ClaudeNotOpenError, PCLockedError) as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error en /stop")
        await update.message.reply_text(f"❌ Error inesperado, Sir Rich: {e}")


@requires_whitelist
async def cmd_debug_ui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        items = await state.controller.dump_sidebar_items(max_items=60)
    except (ClaudeNotOpenError, PCLockedError) as e:
        await update.message.reply_text(f"❌ {e}")
        return
    except Exception as e:
        logger.exception("Error en /debug_ui")
        await update.message.reply_text(f"❌ {e}")
        return
    if not items:
        await update.message.reply_text("⚠️ No detecte items con nombre visible, Sir Rich.")
        return
    chunks = []
    current = "🔬 *UIA dump (primeros items con nombre):*\n```"
    for line in items:
        snippet = line[:110]
        if len(current) + len(snippet) + 5 > 3900:
            chunks.append(current + "\n```")
            current = "```"
        current += "\n" + snippet
    chunks.append(current + "\n```")
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(chunk)


@requires_whitelist
async def cmd_captura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        png_bytes = await state.controller.capture()
    except (ClaudeNotOpenError, PCLockedError) as e:
        await update.message.reply_text(f"❌ {e}")
        return
    except Exception as e:
        logger.exception("Error capturando pantalla")
        await update.message.reply_text(f"❌ Error inesperado, Sir Rich: {e}")
        return
    await update.message.reply_photo(photo=png_bytes, caption="📸 Ventana de Claude, Sir Rich")


@requires_whitelist
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *TelegramClaudeBridge — a la orden, Sir Rich*\n\n"
        "*Comandos:*\n"
        "/start - bienvenida + sesion activa\n"
        "/estado - estado del bot\n"
        "/proyectos - lista de proyectos agrupados (recomendado)\n"
        "/sesiones - lista plana de ultimas 10 sesiones\n"
        "/captura - screenshot de la ventana de Claude\n"
        "/stop - interrumpe a Claude (envia ESC)\n"
        "/enhancer on|off - activa o desactiva el pulidor Groq\n"
        "/parar - pausa el reenvio hacia Telegram\n"
        "/seguir - reanuda el reenvio\n"
        "/ayuda - este mensaje\n\n"
        "*Entradas:*\n"
        "• Texto → mejorado por Groq → confirmas → Claude\n"
        "• Voz/audio → transcrito por Whisper → mejorado → confirmas → Claude\n"
        "• Foto → pegada en Claude (con caption si lo pones)\n"
        "• Texto destructivo → confirmacion Si/No\n\n"
        "💡 Toca el boton *Menu* (abajo-izquierda) o los botones fijos de abajo "
        "para elegir comandos sin escribirlos."
    )
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(),
    )


# --- Teclado flotante: enruta la etiqueta del boton al comando correspondiente ---
_KEYBOARD_HANDLERS = {
    "proyectos": cmd_proyectos,
    "estado": cmd_estado,
    "captura": cmd_captura,
    "stop": cmd_stop,
    "enhancer": cmd_enhancer,
    "ayuda": cmd_ayuda,
}


@requires_whitelist
async def on_keyboard_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    label = (update.message.text or "").strip()
    cmd_name = KEYBOARD_ROUTES.get(label)
    if cmd_name is None:
        return
    handler = _KEYBOARD_HANDLERS.get(cmd_name)
    if handler is not None:
        await handler(update, context)


def _destructive_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Si, mandar", callback_data=f"destr:yes:{token}"),
        InlineKeyboardButton("❌ No, cancelar", callback_data=f"destr:no:{token}"),
    ]])


def _enhanced_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Mandar mejorado", callback_data=f"enh:send:{token}")],
        [InlineKeyboardButton("📤 Mandar original", callback_data=f"enh:orig:{token}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"enh:cancel:{token}")],
    ])


@requires_whitelist
async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _process_user_text(update, update.message.text, source="texto")


async def _process_user_text(update: Update, text: str, source: str = "texto"):
    text = text.strip()
    if not text:
        return

    if is_destructive(text):
        token = uuid.uuid4().hex[:8]
        state.pending_destructive[token] = text
        await update.message.reply_text(
            f"⚠️ Detecte palabras destructivas (deploy/borrar/etc), Sir Rich.\n\n"
            f"Mensaje: _{text[:300]}_\n\n¿Confirma?",
            reply_markup=_destructive_keyboard(token),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if state.groq is None or not state.enhancer_enabled:
        await _send_to_claude(update, text)
        return

    try:
        enhanced = await state.groq.enhance_prompt(text, source=source)
    except GroqAllKeysFailed as e:
        logger.warning(f"Groq enhance fallo, mandando original: {e}")
        await update.message.reply_text("⚠️ Groq no respondio, mando original sin mejorar.")
        await _send_to_claude(update, text)
        return
    except GroqError as e:
        logger.exception("Groq error inesperado")
        await update.message.reply_text(f"⚠️ Groq error: {e}. Mando original.")
        await _send_to_claude(update, text)
        return

    if enhanced.strip() == text.strip() and source != "voz":
        await _send_to_claude(update, text)
        return

    token = uuid.uuid4().hex[:8]
    state.pending_enhanced[token] = {"original": text, "enhanced": enhanced}
    label = "📝" if source == "texto" else ("🎙" if source == "voz" else "🖼")
    await update.message.reply_text(
        f"{label} *Original, Sir Rich*:\n_{text[:600]}_\n\n"
        f"✨ *Mejorado por Groq*:\n_{enhanced[:600]}_",
        reply_markup=_enhanced_keyboard(token),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _send_to_claude(update_or_query, text: str):
    reply = (
        update_or_query.message.reply_text
        if hasattr(update_or_query, "message") and update_or_query.message is not None
        else None
    )
    try:
        async with state.send_lock:
            await state.controller.send(text)
        if reply:
            await reply("✉️ Enviado, Sir Rich.")
    except (ClaudeNotOpenError, PCLockedError) as e:
        if reply:
            await reply(f"❌ {e}")
    except Exception as e:
        logger.exception("Error enviando a Claude")
        if reply:
            await reply(f"❌ Error inesperado, Sir Rich: {e}")


@requires_whitelist
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3:
        return
    family, decision, token = parts

    if family == "destr":
        await _handle_destructive_callback(query, decision, token)
    elif family == "enh":
        await _handle_enhanced_callback(query, decision, token)
    elif family == "switch":
        await _handle_switch_callback(query, decision, token)
    elif family == "proj":
        await _handle_project_open(query, decision, token)
    elif family == "img":
        await _handle_image_callback(query, decision, token)


async def _handle_destructive_callback(query, decision: str, token: str):
    if not state.claim_token(f"destr:{token}"):
        logger.warning(f"Token destructivo duplicado ignorado: {token}")
        return
    text = state.pending_destructive.pop(token, None)
    if not text:
        await query.edit_message_text("⚠️ Confirmacion expirada, Sir Rich.")
        return
    if decision == "yes":
        await query.edit_message_text(
            f"✅ Confirmado, Sir Rich. Enviando...\n_{text[:300]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _do_send(query, text)
    else:
        await query.edit_message_text("❌ Cancelado, Sir Rich.")


async def _handle_enhanced_callback(query, decision: str, token: str):
    if not state.claim_token(f"enh:{token}"):
        logger.warning(f"Token enhanced duplicado ignorado: {token}")
        return
    payload = state.pending_enhanced.pop(token, None)
    if not payload:
        await query.edit_message_text("⚠️ Confirmacion expirada, Sir Rich.")
        return
    if decision == "send":
        text = payload["enhanced"]
        await query.edit_message_text(
            f"✅ Enviando version mejorada, Sir Rich...\n_{text[:300]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _do_send(query, text)
    elif decision == "orig":
        text = payload["original"]
        await query.edit_message_text(
            f"📤 Enviando original, Sir Rich...\n_{text[:300]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _do_send(query, text)
    else:
        await query.edit_message_text("❌ Cancelado, Sir Rich.")


async def _handle_image_callback(query, decision: str, token: str):
    if not state.claim_token(f"img:{token}"):
        logger.warning(f"Token img duplicado ignorado: {token}")
        return
    payload = state.pending_image.pop(token, None)
    if not payload:
        await query.edit_message_text("⚠️ Esa imagen expiro, Sir Rich.")
        return
    images = payload["images"]
    if decision == "cancel":
        await query.edit_message_text("❌ Cancelado, Sir Rich. No envie las imagenes.")
        return
    caption = payload["enhanced"] if decision == "send" else payload["original"]
    label = "version mejorada" if decision == "send" else "caption original"
    n = len(images)
    plural = "imagenes" if n > 1 else "imagen"
    await query.edit_message_text(
        f"✅ Enviando {n} {plural} con {label}, Sir Rich...\n_{caption[:300]}_",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        async with state.send_lock:
            await state.controller.send_images(images, caption=caption)
    except (ClaudeNotOpenError, PCLockedError) as e:
        await query.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error enviando imagenes")
        await query.message.reply_text(f"❌ {e}")


async def _handle_project_open(query, decision: str, token: str):
    if not state.claim_token(f"proj:{token}"):
        logger.warning(f"Token proj duplicado ignorado: {token}")
        return
    payload = state.pending_project.pop(token, None)
    if not payload:
        await query.edit_message_text("⚠️ Esa lista expiro, Sir Rich. Pida /proyectos de nuevo.")
        return
    from pathlib import Path
    folder_path_str, _, display_name = payload.partition("|")
    folder = Path(folder_path_str)
    if not display_name:
        display_name = folder.name

    await query.edit_message_text(
        f"🔁 Cambiando a proyecto *{display_name}*, Sir Rich...",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        async with state.send_lock:
            await state.controller.switch_session(display_name)
        await query.message.reply_text(
            f"✅ Cambiado al proyecto *{display_name}*, Sir Rich. Listo para escribir.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except (ClaudeNotOpenError, PCLockedError) as e:
        await query.message.reply_text(f"❌ {e}")
    except ClaudeControllerError as e:
        await _offer_sidebar_alternatives(query, str(e))
    except Exception as e:
        logger.exception("Error cambiando proyecto")
        await query.message.reply_text(f"❌ {e}")


async def _offer_sidebar_alternatives(query, error_msg: str):
    try:
        headers = await state.controller.list_sidebar_headers()
    except Exception as e:
        logger.exception("Error obteniendo sidebar via OCR")
        await query.message.reply_text(f"❌ {error_msg}")
        return

    if not headers:
        await query.message.reply_text(
            f"❌ {error_msg}\n\nNo pude leer el sidebar para sugerir alternativas, Sir Rich."
        )
        return

    buttons = []
    for h in headers[:25]:
        switch_token = uuid.uuid4().hex[:8]
        state.pending_switch[switch_token] = h
        buttons.append([InlineKeyboardButton(f"💬 {h[:55]}", callback_data=f"switch:go:{switch_token}")])

    await query.message.reply_text(
        f"❌ {error_msg}\n\n"
        f"📋 *Esto es lo que veo en el sidebar, Sir Rich:*\n"
        f"Toca el correcto y lo abro.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_switch_callback(query, decision: str, token: str):
    title = state.pending_switch.pop(token, None)
    if not title:
        await query.edit_message_text("⚠️ Esa lista expiro, Sir Rich. Pida /sesiones de nuevo.")
        return
    await query.edit_message_text(
        f"🔁 Cambiando a sesion, Sir Rich:\n_{title[:200]}_",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        async with state.send_lock:
            await state.controller.switch_session(title)
        await query.message.reply_text(
            f"✅ Cambiada, Sir Rich. Ahora seguimos en:\n_{title[:200]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
    except (ClaudeNotOpenError, PCLockedError) as e:
        await query.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error cambiando sesion")
        await query.message.reply_text(f"❌ {e}")


async def _do_send(query, text: str):
    try:
        async with state.send_lock:
            await state.controller.send(text)
    except (ClaudeNotOpenError, PCLockedError) as e:
        await query.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error en _do_send")
        await query.message.reply_text(f"❌ {e}")


ALBUM_WAIT_SECONDS = 1.8


@requires_whitelist
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = update.message.photo
    if not photos:
        return
    photo = photos[-1]
    caption = (update.message.caption or "").strip() or None
    media_group_id = update.message.media_group_id

    try:
        tg_file = await photo.get_file()
        buf = BytesIO()
        await tg_file.download_to_memory(out=buf)
        image_bytes = buf.getvalue()
    except Exception as e:
        logger.exception("Error descargando foto")
        await update.message.reply_text(f"❌ No pude descargar la foto: {e}")
        return

    if media_group_id:
        await _accumulate_album_photo(update, media_group_id, image_bytes, caption)
        return

    await _present_image(update, [image_bytes], caption)


async def _accumulate_album_photo(update: Update, group_id: str, image_bytes: bytes, caption: str | None):
    existing = state.album_buffers.get(group_id)
    if existing is None:
        state.album_buffers[group_id] = {
            "images": [image_bytes],
            "caption": caption,
            "update": update,
            "task": None,
        }
        task = asyncio.create_task(_album_flush_after_delay(group_id))
        state.album_buffers[group_id]["task"] = task
    else:
        existing["images"].append(image_bytes)
        if caption and not existing["caption"]:
            existing["caption"] = caption


async def _album_flush_after_delay(group_id: str):
    await asyncio.sleep(ALBUM_WAIT_SECONDS)
    payload = state.album_buffers.pop(group_id, None)
    if payload is None:
        return
    await _present_image(payload["update"], payload["images"], payload["caption"])


async def _present_image(update: Update, images: list[bytes], caption: str | None):
    if not caption or state.groq is None or not state.enhancer_enabled:
        await _send_images_to_claude(update, images, caption)
        return

    try:
        enhanced = await state.groq.enhance_prompt(caption, source="texto")
    except GroqAllKeysFailed:
        await _send_images_to_claude(update, images, caption)
        return
    except GroqError:
        logger.exception("Groq error en caption de imagen")
        await _send_images_to_claude(update, images, caption)
        return

    if enhanced.strip() == caption.strip():
        await _send_images_to_claude(update, images, caption)
        return

    token = uuid.uuid4().hex[:8]
    state.pending_image[token] = {"images": images, "original": caption, "enhanced": enhanced}
    n = len(images)
    plural = "imagenes" if n > 1 else "imagen"
    await update.message.reply_text(
        f"🖼 {n} {plural} con caption, Sir Rich:\n\n"
        f"📝 *Original*:\n_{caption[:600]}_\n\n"
        f"✨ *Mejorado por Groq*:\n_{enhanced[:600]}_",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Mandar mejorado", callback_data=f"img:send:{token}")],
            [InlineKeyboardButton("📤 Mandar original", callback_data=f"img:orig:{token}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data=f"img:cancel:{token}")],
        ]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _send_images_to_claude(update: Update, images: list[bytes], caption: str | None):
    n = len(images)
    try:
        async with state.send_lock:
            await state.controller.send_images(images, caption=caption)
        plural = "imagenes" if n > 1 else "imagen"
        cap_part = f" con caption: _{caption[:120]}_" if caption else ""
        await update.message.reply_text(
            f"🖼 {n} {plural} enviada(s) a Claude, Sir Rich{cap_part}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except (ClaudeNotOpenError, PCLockedError) as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error enviando imagen(es) a Claude")
        await update.message.reply_text(f"❌ {e}")


@requires_whitelist
async def on_voice_or_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if state.groq is None:
        await update.message.reply_text("⚠️ Groq deshabilitado, Sir Rich. No puedo transcribir audio.")
        return

    media = update.message.voice or update.message.audio
    if media is None:
        return

    try:
        tg_file = await media.get_file()
        buf = BytesIO()
        await tg_file.download_to_memory(out=buf)
        audio_bytes = buf.getvalue()
    except Exception as e:
        logger.exception("Error descargando audio")
        await update.message.reply_text(f"❌ No pude descargar el audio: {e}")
        return

    await update.message.reply_text("🎙 Transcribiendo con Whisper, Sir Rich...")
    try:
        filename = "voice.ogg" if update.message.voice else (media.file_name or "audio.ogg")
        transcript = await state.groq.transcribe(audio_bytes, filename=filename)
    except GroqAllKeysFailed as e:
        await update.message.reply_text(f"❌ Whisper fallo: {e}")
        return
    except Exception as e:
        logger.exception("Error en transcripcion")
        await update.message.reply_text(f"❌ Error transcribiendo: {e}")
        return

    if not transcript.strip():
        await update.message.reply_text("⚠️ La transcripcion quedo vacia.")
        return

    await _process_user_text(update, transcript, source="voz")


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


async def _send_text(app: Application, text: str):
    try:
        await app.bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        try:
            await app.bot.send_message(chat_id=ALLOWED_USER_ID, text=text)
        except Exception as e:
            logger.exception(f"Failed to forward text: {e}")


async def _send_photo(app: Application, data: bytes, caption: str | None):
    try:
        await app.bot.send_photo(chat_id=ALLOWED_USER_ID, photo=data, caption=caption)
    except Exception as e:
        logger.exception(f"Failed to forward photo: {e}")


async def _watch_active_session(app: Application, watcher: TranscriptWatcher):
    while True:
        try:
            active = detect_active_session(CLAUDE_PROJECTS_DIR)
            if active and active != watcher._active_file:
                previous = watcher._active_file
                watcher.set_active_file(active)
                if previous is not None:
                    try:
                        await app.bot.send_message(
                            chat_id=ALLOWED_USER_ID,
                            text=f"ℹ️ Cambie el seguimiento, Sir Rich. Ahora sigo: `{active.parent.name}`",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify session switch: {e}")
        except Exception as e:
            logger.exception(f"Error in _watch_active_session: {e}")
        await asyncio.sleep(5)


async def post_init(app: Application):
    try:
        await app.bot.set_my_commands(bot_command_menu())
        logger.info("Menu de comandos registrado en Telegram (boton Menu)")
    except Exception as e:
        logger.warning(f"No pude registrar el menu de comandos: {e}")

    async def on_event(event: dict):
        await _forward_event(app, event)

    watcher = TranscriptWatcher(CLAUDE_PROJECTS_DIR, on_event)
    watcher.start()
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active:
        watcher.set_active_file(active)
    app.bot_data["session_switch_task"] = asyncio.create_task(_watch_active_session(app, watcher))
    app.bot_data["watcher"] = watcher

    if not WEB_ENABLED:
        logger.info("Web Batcave deshabilitada (WEB_ENABLED=false). Solo Telegram.")
        return

    web_app = create_app(state)
    config = uvicorn.Config(
        web_app, host=WEB_BIND, port=WEB_PORT,
        log_level="warning", access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.1)
    if task.done():
        task.result()
    app.bot_data["web_server"] = server
    app.bot_data["web_server_task"] = task
    logger.info(f"Batcave web disponible en http://{WEB_BIND}:{WEB_PORT}")


async def _run_web_only():
    """Modo web-only: sin Telegram, solo Batcave web + watcher."""
    logger.info("Modo web-only (TELEGRAM_ENABLED=false)")

    async def on_event(event: dict):
        await _forward_event_web_only(event)

    watcher = TranscriptWatcher(CLAUDE_PROJECTS_DIR, on_event)
    watcher.start()
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active:
        watcher.set_active_file(active)

    web_app = create_app(state)
    config = uvicorn.Config(
        web_app, host=WEB_BIND, port=WEB_PORT,
        log_level="warning", access_log=False,
    )
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.1)
    if web_task.done():
        web_task.result()

    logger.info(f"Batcave web disponible en http://{WEB_BIND}:{WEB_PORT}")

    # Mantener el proceso vivo + poll de sesion activa
    while True:
        try:
            new_active = detect_active_session(CLAUDE_PROJECTS_DIR)
            if new_active and new_active != watcher._active_file:
                watcher.set_active_file(new_active)
        except Exception:
            logger.exception("Error en poll de sesion activa")
        await asyncio.sleep(5)


async def _forward_event_web_only(event: dict):
    if state.paused:
        return
    messages = format_event(event)
    from src.ws_events import broadcaster
    import base64
    for msg in messages:
        if isinstance(msg, TextMessage):
            await broadcaster.broadcast({"type": "claude_text", "text": msg.text})
        elif isinstance(msg, PhotoMessage):
            await broadcaster.broadcast({
                "type": "claude_photo",
                "png_b64": base64.b64encode(msg.data).decode(),
                "caption": msg.caption,
            })


def main():
    if not TELEGRAM_ENABLED:
        asyncio.run(_run_web_only())
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("sesiones", cmd_sesiones))
    app.add_handler(CommandHandler("proyectos", cmd_proyectos))
    app.add_handler(CommandHandler("parar", cmd_parar))
    app.add_handler(CommandHandler("seguir", cmd_seguir))
    app.add_handler(CommandHandler("captura", cmd_captura))
    app.add_handler(CommandHandler("debug_ui", cmd_debug_ui))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("enhancer", cmd_enhancer))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^(destr|enh|switch|proj|img):"))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice_or_audio))
    # El teclado flotante manda la etiqueta como texto: interceptala ANTES del
    # handler general para que ejecute el comando en vez de mandarla a Claude.
    app.add_handler(MessageHandler(filters.Text(set(KEYBOARD_ROUTES.keys())), on_keyboard_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))

    logger.info("Bot iniciando...")
    app.run_polling()


if __name__ == "__main__":
    main()
