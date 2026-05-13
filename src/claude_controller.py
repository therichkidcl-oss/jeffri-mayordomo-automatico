import logging
import time
from pywinauto import Application, Desktop
from pywinauto.findwindows import ElementNotFoundError

logger = logging.getLogger(__name__)


class ClaudeControllerError(Exception):
    """Error general del controller."""


class ClaudeNotOpenError(ClaudeControllerError):
    """La app Claude Desktop no está abierta."""


class PCLockedError(ClaudeControllerError):
    """La PC está bloqueada — no se puede interactuar con la UI."""


class ClaudeController:
    WINDOW_TITLE_CONTAINS = "Claude"
    INPUT_NAMES = [
        "Escribe / para comandos",
        "Send a message",
        "Type a message",
    ]

    def find_window(self):
        try:
            windows = Desktop(backend="uia").windows(
                title_re=f".*{self.WINDOW_TITLE_CONTAINS}.*"
            )
            if not windows:
                raise ClaudeNotOpenError("No encontré ninguna ventana de Claude Desktop")
            for w in windows:
                try:
                    if w.is_visible():
                        return w
                except Exception:
                    continue
            raise ClaudeNotOpenError("Hay ventanas de Claude pero ninguna visible")
        except OSError as e:
            raise PCLockedError(f"No puedo acceder a la UI (¿PC bloqueada?): {e}")

    def _find_input(self, window):
        for name in self.INPUT_NAMES:
            try:
                ctrl = window.child_window(title=name, control_type="Edit")
                if ctrl.exists(timeout=2):
                    return ctrl
            except ElementNotFoundError:
                continue
        try:
            edits = window.descendants(control_type="Edit")
            if edits:
                return edits[-1]
        except Exception as e:
            logger.debug(f"Fallback edit search failed: {e}")
        raise ClaudeControllerError("No encontré el input de Claude en la ventana")

    def send(self, text: str) -> None:
        window = self.find_window()
        try:
            window.set_focus()
        except Exception as e:
            raise PCLockedError(f"No puedo enfocar la ventana de Claude: {e}")

        time.sleep(0.3)

        input_ctrl = self._find_input(window)
        input_ctrl.set_focus()
        time.sleep(0.2)

        input_ctrl.type_keys(text, with_spaces=True, with_newlines=False, with_tabs=False)
        time.sleep(0.3)
        input_ctrl.type_keys("{ENTER}")
        logger.info(f"Mensaje enviado a Claude: {text[:80]}...")
