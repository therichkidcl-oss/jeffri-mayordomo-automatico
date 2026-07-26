from telegram import BotCommand, ReplyKeyboardMarkup

from src.menu import (
    COMMAND_MENU,
    KEYBOARD_ROUTES,
    bot_command_menu,
    main_reply_keyboard,
)


def test_bot_command_menu_returns_botcommands():
    menu = bot_command_menu()
    assert menu, "el menu no debe estar vacio"
    assert all(isinstance(c, BotCommand) for c in menu)


def test_bot_command_menu_includes_core_commands():
    names = {c.command for c in bot_command_menu()}
    for expected in ("start", "proyectos", "estado", "captura", "stop", "enhancer", "ayuda"):
        assert expected in names, f"falta /{expected} en el menu"


def test_bot_command_menu_descriptions_are_valid():
    # Telegram exige descripciones de 1 a 256 caracteres.
    for c in bot_command_menu():
        assert 1 <= len(c.description) <= 256
        # los comandos no llevan slash
        assert not c.command.startswith("/")


def test_command_menu_source_matches_helper():
    assert len(bot_command_menu()) == len(COMMAND_MENU)


def test_main_reply_keyboard_is_persistent():
    kb = main_reply_keyboard()
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert kb.is_persistent is True
    assert kb.resize_keyboard is True


def test_main_reply_keyboard_has_expected_buttons():
    kb = main_reply_keyboard()
    labels = {btn.text for row in kb.keyboard for btn in row}
    # cada boton del teclado debe estar mapeado a un comando
    for label in labels:
        assert label in KEYBOARD_ROUTES, f"boton '{label}' sin ruta de comando"
    # y debe haber al menos 6 botones utiles
    assert len(labels) >= 6


def test_keyboard_routes_point_to_known_commands():
    known = {c.command for c in bot_command_menu()}
    for label, cmd_name in KEYBOARD_ROUTES.items():
        assert not cmd_name.startswith("/"), "la ruta guarda el nombre sin slash"
        assert cmd_name in known, f"la ruta '{label}' apunta a /{cmd_name} que no existe en el menu"
