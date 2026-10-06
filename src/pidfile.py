"""Single-instance lock via pidfile. Prevents Jeffri de correr dos veces.

Historia del bug (2026-09-12): el usuario tenia `run.bat` corriendo
`python -m src.bot` (solo Telegram) y ademas un shortcut que arrancaba
`pythonw -m src.main` (Telegram + voz). Resultado: 2 procesos pythonicos
peleandose por el mismo token — `getUpdates` daba `Conflict: terminated by
other getUpdates request` y cada mensaje se procesaba dos veces (llegaba
duplicado a Claude y a Telegram, y como cada proceso tenia una version
distinta del enhancer, unos decian "Groq" y otros "DeepSeek").

Este modulo bloquea el arranque cuando ya hay una instancia viva. Ambos
entrypoints (src.bot y src.main) usan el mismo pidfile — asi se protegen
uno al otro y no importa por cual arranques.
"""
import atexit
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class AlreadyRunning(RuntimeError):
    """Otra instancia viva de Jeffri ya tiene el lock."""


def acquire(pidfile: Path) -> None:
    """Adquiere el lock escribiendo el PID actual en `pidfile`.

    Si el archivo ya existe Y el PID que contiene esta VIVO Y es distinto al
    nuestro, levanta AlreadyRunning con instrucciones para matar el proceso.

    Si el archivo existe pero el PID esta muerto (stale lock), lo sobreescribe.
    Al `sys.exit` normal borra el pidfile via `atexit`.
    """
    if pidfile.exists():
        try:
            existing = int(pidfile.read_text().strip())
        except (ValueError, OSError):
            existing = 0
        if existing and existing != os.getpid() and _pid_alive(existing):
            raise AlreadyRunning(
                f"Otra instancia de Jeffri ya corre (PID {existing}). "
                f"Matala primero con: taskkill /F /PID {existing}"
            )

    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))
    atexit.register(_release, pidfile)


def _pid_alive(pid: int) -> bool:
    """True si el PID esta vivo.

    Windows: `os.kill(pid, 0)` NO funciona — devuelve OSError(EINVAL) tanto
    para procesos ajenos vivos como para PIDs muertos, sin distinguir. Usamos
    OpenProcess(SYNCHRONIZE) + GetExitCodeProcess para verificar de verdad si
    el proceso esta corriendo.

    Unix: `os.kill(pid, 0)` sigue siendo el patron correcto — hace un
    permission check sin senalizar; PermissionError = existe pero de otro
    usuario, y lo consideramos vivo.
    """
    if pid <= 0:
        return False

    import sys
    if sys.platform == "win32":
        return _pid_alive_windows(pid)

    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _pid_alive_windows(pid: int) -> bool:
    """Windows: OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) + GetExitCodeProcess.

    Sin declarar argtypes/restype, ctypes trata el handle como int 32-bit y en
    Windows x64 los handles son punteros de 64-bit — se truncan a 0 (falla
    silenciosa que hacia _pid_alive devolver False para todo). Los argtypes
    explicitos abajo lo arreglan.

    PROCESS_QUERY_LIMITED_INFORMATION (0x1000) es el acceso minimo que basta
    para GetExitCodeProcess y funciona sobre procesos de cualquier usuario
    sin necesidad de privilegios especiales.
    """
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return exit_code.value == STILL_ACTIVE
        return False
    finally:
        kernel32.CloseHandle(handle)


def _release(pidfile: Path) -> None:
    """Borra el pidfile solo si su contenido apunta a NUESTRO PID.

    Defensa contra race conditions raras: si otro proceso arranco despues de
    que nosotros muriesemos y reescribio el pidfile, no borramos el suyo.
    """
    try:
        current = pidfile.read_text().strip()
    except OSError:
        return
    if current == str(os.getpid()):
        try:
            pidfile.unlink()
        except OSError:
            pass
