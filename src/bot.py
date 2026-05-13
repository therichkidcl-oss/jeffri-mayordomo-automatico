import asyncio
import logging
import uuid
from pathlib import Path

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
from src.config import ALLOWED_USER_ID, CLAUDE_PROJECTS_DIR, TELEGRAM_BOT_TOKEN
from src.formatters import format_event
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
        self.pending_confirmations: dict[str, str] = {}
        self.controller = ClaudeController()
        self.send_lock = asyncio.Lock()


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
    msg = f"Estado: {paused}\nSesión: `{active.parent.name if active else '(ninguna)'}`"
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
async def cmd_captura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        png_bytes = await state.controller.capture()
    except ClaudeNotOpenError as e:
        await update.message.reply_text(f"❌ {e}")
        return
    except PCLockedError as e:
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
        "/start - bienvenida + sesión activa\n"
        "/estado - estado del bot\n"
        "/sesiones - lista sesiones recientes\n"
        "/captura - screenshot de la ventana de Claude\n"
        "/parar - pausa el reenvío\n"
        "/seguir - reanuda el reenvío\n"
        "/ayuda - este mensaje\n\n"
        "Cualquier mensaje sin slash se envía a Claude."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


def _confirmation_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, mandar", callback_data=f"confirm:yes:{token}"),
        InlineKeyboardButton("❌ No, cancelar", callback_data=f"confirm:no:{token}"),
    ]])


@requires_whitelist
async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if is_destructive(text):
        token = uuid.uuid4().hex[:8]
        state.pending_confirmations[token] = text
        await update.message.reply_text(
            f"⚠️ Detecté palabras destructivas (deploy/borrar/etc).\n\n"
            f"Mensaje: _{text[:200]}_\n\n¿Confirmas?",
            reply_markup=_confirmation_keyboard(token),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await _send_to_claude(update, text)


async def _send_to_claude(update: Update, text: str):
    try:
        async with state.send_lock:
            await state.controller.send(text)
        await update.message.reply_text("✉️ Enviado a Claude. Esperando respuesta...")
    except ClaudeNotOpenError as e:
        await update.message.reply_text(f"❌ {e}")
    except PCLockedError as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.exception("Error enviando a Claude")
        await update.message.reply_text(f"❌ Error inesperado: {e}")


@requires_whitelist
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "confirm":
        return
    decision, token = parts[1], parts[2]
    text = state.pending_confirmations.pop(token, None)
    if not text:
        await query.edit_message_text("⚠️ Confirmación expirada.")
        return
    if decision == "yes":
        await query.edit_message_text(
            f"✅ Confirmado, enviando...\n_{text[:200]}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            async with state.send_lock:
                await state.controller.send(text)
        except Exception as e:
            await query.message.reply_text(f"❌ {e}")
    else:
        await query.edit_message_text("❌ Cancelado.")


async def _forward_event_to_telegram(app: Application, event: dict):
    if state.paused:
        return
    messages = format_event(event)
    for msg in messages:
        try:
            await app.bot.send_message(
                chat_id=ALLOWED_USER_ID,
                text=msg,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            try:
                await app.bot.send_message(chat_id=ALLOWED_USER_ID, text=msg)
            except Exception as e:
                logger.exception(f"Failed to forward event: {e}")


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
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^confirm:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))

    logger.info("Bot iniciando...")
    app.run_polling()


if __name__ == "__main__":
    main()
