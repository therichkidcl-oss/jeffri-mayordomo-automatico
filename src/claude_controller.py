import asyncio
import logging
import time
import mss
import mss.tools
import pyperclip
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

logger = logging.getLogger(__name__)


class ClaudeControllerError(Exception):
    """Error general del controller."""


class ClaudeNotOpenError(ClaudeControllerError):
    """La app Claude Desktop no está abierta."""


class PCLockedError(ClaudeControllerError):
    """La PC está bloqueada o la UI no es accesible."""


class ClaudeController:
    WINDOW_TITLE_CONTAINS = "Claude"
    INPUT_NAMES = [
        "Escribe / para comandos",
        "Send a message",
        "Type a message",
    ]

    def __init__(self) -> None:
        self._resolved_input_name: str | None = None

    def find_window(self):
        try:
            windows = Desktop(backend="uia").windows(
                title_re=f".*{self.WINDOW_TITLE_CONTAINS}.*"
            )
        except Exception as e:
            logger.warning(f"UIA inaccesible buscando ventanas de Claude: {e!r}")
            raise PCLockedError(f"No puedo acceder a la UI (¿PC bloqueada?): {e}")

        if not windows:
            logger.warning("No encontré ninguna ventana de Claude Desktop")
            raise ClaudeNotOpenError("No encontré ninguna ventana de Claude Desktop")

        for w in windows:
            try:
                if w.is_visible():
                    return w
            except Exception as e:
                logger.debug(f"Ventana descartada por error en is_visible(): {e!r}")
                continue

        logger.warning(f"Encontré {len(windows)} ventana(s) de Claude pero ninguna visible")
        raise ClaudeNotOpenError("Hay ventanas de Claude pero ninguna visible")

    def _find_input(self, window):
        try:
            edits = window.descendants(control_type="Edit")
        except Exception as e:
            logger.warning(f"No pude listar Edits en la ventana: {e!r}")
            raise ClaudeControllerError(f"No pude inspeccionar la ventana: {e}")

        if not edits:
            logger.warning("No hay controles Edit en la ventana")
            raise ClaudeControllerError("No encontré ningún input en la ventana de Claude")

        names_to_try: list[str | None] = []
        if self._resolved_input_name is not None:
            names_to_try.append(self._resolved_input_name)
        names_to_try.extend(n for n in self.INPUT_NAMES if n != self._resolved_input_name)

        for name in names_to_try:
            for edit in edits:
                try:
                    if edit.element_info.name == name:
                        self._resolved_input_name = name
                        return edit
                except Exception:
                    continue

        logger.debug(f"Fallback: usando último Edit de {len(edits)} encontrados")
        return edits[-1]

    async def send(self, text: str) -> None:
        await asyncio.to_thread(self._send_sync, text)

    async def capture(self) -> bytes:
        return await asyncio.to_thread(self._capture_sync)

    def _capture_sync(self) -> bytes:
        window = self.find_window()
        try:
            window.set_focus()
            time.sleep(0.2)
        except Exception as e:
            logger.debug(f"set_focus en capture falló (continúo igual): {e!r}")

        rect = window.rectangle()
        bbox = {
            "left": rect.left,
            "top": rect.top,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        }
        if bbox["width"] <= 0 or bbox["height"] <= 0:
            raise ClaudeControllerError(f"Dimensiones de ventana inválidas: {bbox}")

        with mss.mss() as sct:
            sct_img = sct.grab(bbox)
            png_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
        logger.info(f"Captura {bbox['width']}x{bbox['height']} ({len(png_bytes)} bytes)")
        return png_bytes

    def _send_sync(self, text: str) -> None:
        window = self.find_window()

        try:
            window.set_focus()
        except Exception as e:
            logger.warning(f"No puedo enfocar la ventana de Claude: {e!r}")
            raise ClaudeControllerError(f"No puedo enfocar la ventana de Claude: {e}")

        time.sleep(0.3)

        input_ctrl = self._find_input(window)
        input_ctrl.set_focus()
        time.sleep(0.2)

        pyperclip.copy(text)
        send_keys("^v", pause=0.05)
        time.sleep(0.4)
        send_keys("{ENTER}")
        logger.info(f"Mensaje enviado a Claude ({len(text)} chars): {text[:80]!r}...")
