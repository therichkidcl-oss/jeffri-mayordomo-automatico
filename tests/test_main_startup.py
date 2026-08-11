"""Regresion: el ciclo de vida MANUAL de PTB (initialize/start/start_polling)
NO llama post_init solo — solo lo hacen run_polling/run_webhook (asi lo dice el
docstring de Application.initialize en python-telegram-bot). Si _startup no
invoca post_init a mano, el TranscriptWatcher nunca arranca y Jeffri deja de
reenviar las respuestas de Claude a Telegram (y de avisar cambios de sesion).

Este test fija que _startup SIEMPRE llame post_init.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.main import _startup


def test_startup_llama_post_init():
    app = MagicMock()
    app.initialize = AsyncMock()
    app.start = AsyncMock()
    app.post_init = AsyncMock()
    app.updater = MagicMock()
    app.updater.start_polling = AsyncMock()

    asyncio.run(_startup(app))

    # lo critico: post_init DEBE llamarse (si no, no hay watcher -> no reenvia)
    app.post_init.assert_awaited_once_with(app)
    # y en el orden correcto: initialize antes que post_init antes que polling
    app.initialize.assert_awaited_once()
    app.updater.start_polling.assert_awaited_once()


def test_startup_no_falla_si_no_hay_post_init():
    # Si por lo que sea no hay post_init registrado, no debe reventar.
    app = MagicMock()
    app.initialize = AsyncMock()
    app.start = AsyncMock()
    app.post_init = None
    app.updater = MagicMock()
    app.updater.start_polling = AsyncMock()

    asyncio.run(_startup(app))  # no debe lanzar
    app.updater.start_polling.assert_awaited_once()
