import asyncio
import logging
import uuid
from io import BytesIO

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

from src.claude_controller import ClaudeController, ClaudeNotOpenError, PCLockedError
from src.config import (
    ALLOWED_USER_ID,
    CLAUDE_PROJECTS_DIR,
    GROQ_API_KEYS,
    TELEGRAM_BOT_TOKEN,
)
from src.formatters import PhotoMessage, TextMessage, format_event
from src.groq_client import GroqAllKeysFailed, GroqClient, GroqError
from src.security import is_destructive, requires_whitelist
from src.session_detector import detect_active_session, list_recent_sessions
from src.transcript_watcher import TranscriptWatcher

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
        self.controller = ClaudeController()
        self.send_lock = asyncio.Lock()
        self.groq: GroqClient | None = GroqClient(GROQ_API_KEYS) if GROQ_API_KEYS else None
        if self.groq is None:
            logger.warning("GROQ_API_KEYS vacío: enhancer y transcripción deshabilitados")
        else:
            logger.info(f"Groq habilitado con {len(GROQ_API_KEYS)} keys")


state = BotState()


@requires_whitelist
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active:
        msg = f"👋 Hola Reimo. Sesión activa: `{active.parent.name}`"
    else:
        msg = "👋 Hola Reimo. No detecté ninguna sesión activa. Abre Claude Desktop."
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    paused = "⏸️ pausado" if state.paused else "▶️ activo"
    groq_state = "🤖 Groq activo" if state.groq else "🤖 Groq deshabilitado"
    msg = (
        f"Estado: {paused}\n"
        f"Sesión: `{active.parent.name if active else '(ninguna)'}`\n"
        f"{groq_state}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_sesiones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions = list_recent_sessions(CLAUDE_PROJECTS_DIR, limit=10)
    if not sessions:
        await update.message.reply_text("No hay sesiones recientes.")
        return
    lines = ["📋 *Sesiones recientes:*"]
    for s in sessions:
        lines.append(f"• `{s.folder_name}` ({s.last_modified:%H:%M:%S})")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


@requires_whitelist
async def cmd_parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.paused = True
    await update.message.reply_text("⏸️ Reenvío pausado. /seguir para reanudar.")


@requires_whitelist
async def cmd_seguir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.paused = False
    await update.message.reply_text("▶️ Reenvío reanudado.")


@requires_whitelist
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with state.send_lock:
            await state.controller.interrupt()
        await update.message.reply_text("⏹ ESC enviado a Claude (interrumpido)")
    except (ClaudeNotOpenError, PCLockedError) as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error en /stop")
        await update.message.reply_text(f"❌ Error inesperado: {e}")


@requires_whitelist
async def cmd_captura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        png_bytes = await state.controller.capture()
    except (ClaudeNotOpenError, PCLockedError) as e:
        await update.message.reply_text(f"❌ {e}")
        return
    except Exception as e:
        logger.exception("Error capturando pantalla")
        await update.message.reply_text(f"❌ Error inesperado: {e}")
        return
    await update.message.reply_photo(photo=png_bytes, caption="📸 Ventana de Claude")


@requires_whitelist
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *TelegramClaudeBridge*\n\n"
        "*Comandos:*\n"
        "/start - bienvenida + sesión activa\n"
        "/estado - estado del bot\n"
        "/sesiones - lista sesiones recientes\n"
        "/captura - screenshot de la ventana de Claude\n"
        "/stop - interrumpe a Claude (envía ESC)\n"
        "/parar - pausa el reenvío hacia Telegram\n"
        "/seguir - reanuda el reenvío\n"
        "/ayuda - este mensaje\n\n"
        "*Entradas:*\n"
        "• Texto → mejorado por Groq → confirmas → Claude\n"
        "• Voz/audio → transcrito por Groq → mejorado → confirmas → Claude\n"
        "• Foto → pegada en Claude (con caption si lo pones)\n"
        "• Texto destructivo → confirmación Sí/No"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


def _destructive_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, mandar", callback_data=f"destr:yes:{token}"),
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
            f"⚠️ Detecté palabras destructivas (deploy/borrar/etc).\n\n"
            f"Mensaje: _{text[:300]}_\n\n¿Confirmas?",
            reply_markup=_destructive_keyboard(token),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if state.groq is None:
        await _send_to_claude(update, text)
        return

    try:
        enhanced = await state.groq.enhance_prompt(text)
    except GroqAllKeysFailed as e:
        logger.warning(f"Groq enhance falló, mandando original: {e}")
        await update.message.reply_text("⚠️ Groq no respondió, mando original sin mejorar.")
        await _send_to_claude(update, text)
        return
    except GroqError as e:
        logger.exception("Groq error inesperado")
        await update.message.reply_text(f"⚠️ Groq error: {e}. Mando original.")
        await _send_to_claude(update, text)
        return

    if enhanced.strip() == text.strip():
        await _send_to_claude(update, text)
        return

    token = uuid.uuid4().hex[:8]
    state.pending_enhanced[token] = {"original": text, "enhanced": enhanced}
    label = "📝" if source == "texto" else ("🎙" if source == "voz" else "🖼")
    await update.message.reply_text(
        f"{label} *Original*:\n_{text[:600]}_\n\n"
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
            await reply("✉️ Enviado a Claude.")
    except (ClaudeNotOpenError, PCLockedError) as e:
        if reply:
            await reply(f"❌ {e}")
    except Exception as e:
        logger.exception("Error enviando a Claude")
        if reply:
            await reply(f"❌ Error inesperado: {e}")


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


async def _handle_destructive_callback(query, decision: str, token: str):
    text = state.pending_destructive.pop(token, None)
    if not text:
        await query.edit_message_text("⚠️ Confirmación expirada.")
        return
    if decision == "yes":
        await query.edit_message_text(
            f"✅ Confirmado, enviando...\n_{text[:300]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _do_send(query, text)
    else:
        await query.edit_message_text("❌ Cancelado.")


async def _handle_enhanced_callback(query, decision: str, token: str):
    payload = state.pending_enhanced.pop(token, None)
    if not payload:
        await query.edit_message_text("⚠️ Confirmación expirada.")
        return
    if decision == "send":
        text = payload["enhanced"]
        await query.edit_message_text(
            f"✅ Enviando mejorado...\n_{text[:300]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _do_send(query, text)
    elif decision == "orig":
        text = payload["original"]
        await query.edit_message_text(
            f"📤 Enviando original...\n_{text[:300]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        await _do_send(query, text)
    else:
        await query.edit_message_text("❌ Cancelado.")


async def _do_send(query, text: str):
    try:
        async with state.send_lock:
            await state.controller.send(text)
    except (ClaudeNotOpenError, PCLockedError) as e:
        await query.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error en _do_send")
        await query.message.reply_text(f"❌ {e}")


@requires_whitelist
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photos = update.message.photo
    if not photos:
        return
    photo = photos[-1]
    caption = (update.message.caption or "").strip() or None

    try:
        tg_file = await photo.get_file()
        buf = BytesIO()
        await tg_file.download_to_memory(out=buf)
        image_bytes = buf.getvalue()
    except Exception as e:
        logger.exception("Error descargando foto")
        await update.message.reply_text(f"❌ No pude descargar la foto: {e}")
        return

    try:
        async with state.send_lock:
            await state.controller.send_image(image_bytes, caption=caption)
        await update.message.reply_text(
            f"🖼 Imagen enviada a Claude" + (f" con caption: _{caption[:120]}_" if caption else ""),
            parse_mode=ParseMode.MARKDOWN,
        )
    except (ClaudeNotOpenError, PCLockedError) as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error enviando imagen a Claude")
        await update.message.reply_text(f"❌ {e}")


@requires_whitelist
async def on_voice_or_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if state.groq is None:
        await update.message.reply_text("⚠️ Groq deshabilitado, no puedo transcribir audio.")
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

    await update.message.reply_text("🎙 Transcribiendo con Whisper...")
    try:
        filename = "voice.ogg" if update.message.voice else (media.file_name or "audio.ogg")
        transcript = await state.groq.transcribe(audio_bytes, filename=filename)
    except GroqAllKeysFailed as e:
        await update.message.reply_text(f"❌ Whisper falló: {e}")
        return
    except Exception as e:
        logger.exception("Error en transcripción")
        await update.message.reply_text(f"❌ Error transcribiendo: {e}")
        return

    if not transcript.strip():
        await update.message.reply_text("⚠️ La transcripción quedó vacía.")
        return

    await _process_user_text(update, transcript, source="voz")


async def _forward_event_to_telegram(app: Application, event: dict):
    if state.paused:
        return
    messages = format_event(event)
    for msg in messages:
        if isinstance(msg, TextMessage):
            await _send_text(app, msg.text)
        elif isinstance(msg, PhotoMessage):
            await _send_photo(app, msg.data, msg.caption)


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
                            text=f"ℹ️ Cambié al seguimiento de sesión: `{active.parent.name}`",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify session switch: {e}")
        except Exception as e:
            logger.exception(f"Error in _watch_active_session: {e}")
        await asyncio.sleep(5)


async def post_init(app: Application):
    async def on_event(event: dict):
        await _forward_event_to_telegram(app, event)

    watcher = TranscriptWatcher(CLAUDE_PROJECTS_DIR, on_event)
    watcher.start()
    active = detect_active_session(CLAUDE_PROJECTS_DIR)
    if active:
        watcher.set_active_file(active)
    app.bot_data["session_switch_task"] = asyncio.create_task(_watch_active_session(app, watcher))
    app.bot_data["watcher"] = watcher


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("sesiones", cmd_sesiones))
    app.add_handler(CommandHandler("parar", cmd_parar))
    app.add_handler(CommandHandler("seguir", cmd_seguir))
    app.add_handler(CommandHandler("captura", cmd_captura))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^(destr|enh):"))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice_or_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))

    logger.info("Bot iniciando...")
    app.run_polling()


if __name__ == "__main__":
    main()
