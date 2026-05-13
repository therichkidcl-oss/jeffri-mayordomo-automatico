import asyncio
import logging
import time
from io import BytesIO

import mss
import mss.tools
import pyperclip
import win32api
import win32clipboard
import win32con
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

    def _focus_window(self, dismiss_modals: bool = True) -> None:
        window = self.find_window()
        try:
            window.set_focus()
        except Exception as e:
            logger.warning(f"No puedo enfocar la ventana de Claude: {e!r}")
            raise ClaudeControllerError(f"No puedo enfocar la ventana de Claude: {e}")
        time.sleep(0.5)
        if dismiss_modals:
            send_keys("{ESC}")
            time.sleep(0.2)
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
        time.sleep(0.5)

        send_keys("{ESC}")
        time.sleep(0.2)

        target = title.strip().lower()
        logger.info(f"Switch: buscando '{target}' en sidebar por OCR")

        rect = window.rectangle()
        sidebar_w = min(320, rect.right - rect.left)
        sidebar_bbox = {
            "left": rect.left,
            "top": rect.top,
            "width": sidebar_w,
            "height": rect.bottom - rect.top,
        }

        with mss.mss() as sct:
            shot = sct.grab(sidebar_bbox)
            png_bytes = mss.tools.to_png(shot.rgb, shot.size)

        coords = _ocr_find_text(png_bytes, target, sidebar_bbox["left"], sidebar_bbox["top"])
        if coords is None:
            raise ClaudeControllerError(
                f"No encontré '{title[:40]}' en el sidebar via OCR. ¿Está visible?"
            )

        cx, cy = coords
        logger.info(f"OCR match para '{target}' en pixel ({cx}, {cy})")
        _click_at(cx, cy)
        time.sleep(0.8)
        logger.info(f"Switch completado para '{target}'")

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


def _click_at(x: int, y: int) -> None:
    win32api.SetCursorPos((int(x), int(y)))
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _normalize_for_match(s: str) -> str:
    s = s.lower()
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in s)
    return " ".join(cleaned.split())


def _fuzzy_score(query: str, text: str) -> int:
    qn = _normalize_for_match(query)
    tn = _normalize_for_match(text)
    if not qn or not tn:
        return 0

    if qn == tn:
        return 1000
    if qn in tn:
        return 900 - min(50, abs(len(tn) - len(qn)))
    if len(tn) >= 3 and tn in qn:
        return 800 - min(50, abs(len(tn) - len(qn)))

    qwords = qn.split()
    twords = tn.split()
    if not qwords:
        return 0
    found = 0
    for qw in qwords:
        for tw in twords:
            if qw == tw or (len(qw) >= 3 and qw in tw) or (len(tw) >= 3 and tw in qw):
                found += 1
                break
    if found == len(qwords):
        return 600
    if found >= len(qwords) * 0.6:
        return int(400 * found / len(qwords))
    return 0


def _ocr_find_text(png_bytes: bytes, query: str, offset_x: int, offset_y: int) -> tuple[int, int] | None:
    try:
        import winocr
    except ImportError:
        logger.error("winocr no está instalado")
        return None

    img = Image.open(BytesIO(png_bytes))
    try:
        result = asyncio.run(winocr.recognize_pil(img, "es-ES"))
    except Exception as e:
        logger.warning(f"OCR falló con es-ES: {e!r}, reintentando sin lang")
        try:
            result = asyncio.run(winocr.recognize_pil(img))
        except Exception as e2:
            logger.error(f"OCR falló completamente: {e2!r}")
            return None

    try:
        lines = list(result.lines)
    except Exception as e:
        logger.error(f"No pude leer result.lines: {e!r}")
        return None

    candidates: list[tuple[int, int, int, str]] = []
    for line in lines:
        try:
            text = (line.text or "").strip()
            words = list(line.words)
        except Exception:
            continue
        if not text:
            continue
        score = _fuzzy_score(query, text)
        if score > 0 and words:
            try:
                rects = []
                for w in words:
                    br = w.bounding_rect
                    rects.append((br.x, br.y, br.width, br.height))
                if rects:
                    min_x = min(r[0] for r in rects)
                    max_x = max(r[0] + r[2] for r in rects)
                    min_y = min(r[1] for r in rects)
                    max_y = max(r[1] + r[3] for r in rects)
                    cx = int((min_x + max_x) / 2)
                    cy = int((min_y + max_y) / 2)
                    candidates.append((score, cx, cy, text))
            except Exception as e:
                logger.debug(f"No pude calcular bbox para '{text}': {e!r}")
                continue

    if not candidates:
        sample = []
        for line in lines[:15]:
            try:
                sample.append((line.text or "")[:50])
            except Exception:
                continue
        logger.warning(f"OCR no encontró '{query}'. Textos leídos: {sample}")
        return None

    candidates.sort(key=lambda c: c[0], reverse=True)
    score, cx, cy, matched = candidates[0]
    logger.info(f"OCR best match score={score} '{matched[:60]}' @ ({cx},{cy})")
    return (offset_x + cx, offset_y + cy)


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
