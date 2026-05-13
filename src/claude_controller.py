import asyncio
import logging
import time
from io import BytesIO

import mss
import mss.tools
import pyperclip
import win32clipboard
from PIL import Image
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
            logger.debug("No hay controles Edit en la ventana (Electron app)")
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

    async def send_image(self, image_bytes: bytes, caption: str | None = None) -> None:
        await asyncio.to_thread(self._send_image_sync, image_bytes, caption)

    async def interrupt(self) -> None:
        await asyncio.to_thread(self._interrupt_sync)

    async def capture(self) -> bytes:
        return await asyncio.to_thread(self._capture_sync)

    async def switch_session(self, title: str) -> None:
        await asyncio.to_thread(self._switch_session_sync, title)

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

    def _focus_window(self) -> None:
        window = self.find_window()
        try:
            window.set_focus()
        except Exception as e:
            logger.warning(f"No puedo enfocar la ventana de Claude: {e!r}")
            raise ClaudeControllerError(f"No puedo enfocar la ventana de Claude: {e}")
        time.sleep(0.5)
        try:
            input_ctrl = self._find_input(window)
            input_ctrl.set_focus()
            time.sleep(0.2)
        except ClaudeControllerError as e:
            logger.debug(f"No expuse el input via UIA, usando foco de ventana: {e}")

    def _send_sync(self, text: str) -> None:
        self._focus_window()
        pyperclip.copy(text)
        send_keys("^v", pause=0.05)
        time.sleep(0.4)
        send_keys("{ENTER}")
        logger.info(f"Mensaje enviado a Claude ({len(text)} chars): {text[:80]!r}...")

    def _send_image_sync(self, image_bytes: bytes, caption: str | None) -> None:
        self._focus_window()
        _copy_image_to_clipboard(image_bytes)
        send_keys("^v", pause=0.05)
        time.sleep(0.6)
        if caption:
            pyperclip.copy(caption)
            send_keys("^v", pause=0.05)
            time.sleep(0.3)
        send_keys("{ENTER}")
        logger.info(f"Imagen enviada a Claude ({len(image_bytes)} bytes)" + (f" + caption: {caption[:60]!r}" if caption else ""))

    def _interrupt_sync(self) -> None:
        self._focus_window()
        send_keys("{ESC}")
        logger.info("Enviado ESC a Claude (interrumpir)")

    SEARCH_BUTTON_NAMES = {"search", "buscar"}

    def _find_search_button(self, window):
        try:
            for item in window.descendants(control_type="Button"):
                try:
                    name = (item.element_info.name or "").strip().lower()
                except Exception:
                    continue
                if name in self.SEARCH_BUTTON_NAMES:
                    return item
        except Exception as e:
            logger.debug(f"Búsqueda de Search button falló: {e!r}")
        return None

    def _switch_session_sync(self, title: str) -> None:
        window = self.find_window()
        try:
            window.set_focus()
        except Exception as e:
            raise ClaudeControllerError(f"No puedo enfocar la ventana: {e}")
        time.sleep(0.4)

        query_text = title.strip()
        if len(query_text) > 60:
            query_text = query_text[:60].rsplit(" ", 1)[0] or query_text[:60]
        logger.info(f"Switch: buscando '{query_text}' (titulo orig: '{title[:80]}')")

        search_btn = self._find_search_button(window)
        if search_btn is None:
            logger.info("No encontré botón Search, probando atajo Ctrl+K")
            send_keys("^k")
        else:
            try:
                search_btn.click_input()
                logger.info("Click en botón Search")
            except Exception as e:
                logger.warning(f"Click en Search falló, fallback a Ctrl+K: {e!r}")
                send_keys("^k")

        time.sleep(0.8)

        pyperclip.copy(query_text)
        send_keys("^v", pause=0.05)
        time.sleep(1.2)

        send_keys("{ENTER}")
        time.sleep(0.8)
        logger.info(f"Switch enviado para '{query_text}'")

    async def dump_sidebar_items(self, max_items: int = 80) -> list[str]:
        return await asyncio.to_thread(self._dump_sidebar_items_sync, max_items)

    def _dump_sidebar_items_sync(self, max_items: int) -> list[str]:
        window = self.find_window()
        try:
            all_items = window.descendants()
        except Exception as e:
            raise ClaudeControllerError(f"No pude inspeccionar la ventana: {e}")
        out = []
        for item in all_items:
            try:
                name = (item.element_info.name or "").strip()
                ctype = item.element_info.control_type
            except Exception:
                continue
            if name and 5 < len(name) < 120:
                out.append(f"[{ctype}] {name}")
                if len(out) >= max_items:
                    break
        return out


def _copy_image_to_clipboard(image_bytes: bytes) -> None:
    img = Image.open(BytesIO(image_bytes))
    output = BytesIO()
    img.convert("RGB").save(output, format="BMP")
    data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()
