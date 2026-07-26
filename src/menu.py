"""Menu de comandos y teclado flotante persistente para Jeffri.

Dos capas de UX para elegir comandos sin escribirlos:

1. `bot_command_menu()` -> lista de BotCommand para `setMyCommands`.
   Alimenta el boton nativo "Menu" de Telegram (abajo-izquierda del chat).

2. `main_reply_keyboard()` -> ReplyKeyboardMarkup persistente.
   Botones fijos arriba del campo de texto; se quedan en la conversacion.
   Cada boton manda su etiqueta como texto; el bot la mapea a un comando
   via `KEYBOARD_ROUTES` (etiqueta -> nombre de comando sin slash).
"""

from telegram import BotCommand, KeyboardButton, ReplyKeyboardMarkup

# (comando_sin_slash, descripcion) — orden = orden en el menu de Telegram.
COMMAND_MENU: list[tuple[str, str]] = [
    ("start", "Bienvenida + sesion activa"),
    ("proyectos", "Lista de proyectos (recomendado)"),
    ("sesiones", "Ultimas 10 sesiones"),
    ("estado", "Estado del bot y del enhancer"),
    ("captura", "Screenshot de la ventana de Claude"),
    ("stop", "Interrumpe a Claude (envia ESC)"),
    ("enhancer", "Activa o desactiva el pulidor Groq"),
    ("parar", "Pausa el reenvio hacia Telegram"),
    ("seguir", "Reanuda el reenvio"),
    ("ayuda", "Lista de comandos y como usar el bot"),
]

# Etiqueta del boton flotante -> nombre de comando (sin slash).
KEYBOARD_ROUTES: dict[str, str] = {
    "🗂 Proyectos": "proyectos",
    "📊 Estado": "estado",
    "📸 Captura": "captura",
    "⏹ Stop": "stop",
    "✨ Enhancer": "enhancer",
    "❓ Ayuda": "ayuda",
}

# Disposicion visual del teclado (filas de etiquetas).
_KEYBOARD_LAYOUT: list[list[str]] = [
    ["🗂 Proyectos", "📊 Estado", "📸 Captura"],
    ["⏹ Stop", "✨ Enhancer", "❓ Ayuda"],
]


def bot_command_menu() -> list[BotCommand]:
    """Lista de BotCommand para registrar con `bot.set_my_commands(...)`."""
    return [BotCommand(cmd, desc) for cmd, desc in COMMAND_MENU]


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Teclado flotante persistente con los comandos mas usados."""
    keyboard = [[KeyboardButton(label) for label in row] for row in _KEYBOARD_LAYOUT]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Escribe o toca un comando, Sir Rich",
    )
