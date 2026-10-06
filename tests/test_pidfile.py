"""Tests del pidfile lock (TDD).

Todo se hace bajo `tmp_path` para no ensuciar `logs/`.
"""
import os

import pytest

from src.pidfile import AlreadyRunning, acquire


def test_acquire_escribe_el_pid_propio(tmp_path):
    pidfile = tmp_path / "jeffri.pid"
    acquire(pidfile)

    assert pidfile.exists()
    assert pidfile.read_text().strip() == str(os.getpid())


def test_acquire_falla_si_hay_otra_instancia_viva(tmp_path, monkeypatch):
    pidfile = tmp_path / "jeffri.pid"
    # Simula un pidfile con el PID de un proceso "vivo" distinto al nuestro.
    # Usamos PID 1 en Unix / cualquier PID != el nuestro en Windows; monkey-patch
    # el checker para no depender del PID real.
    pidfile.write_text("99999")
    monkeypatch.setattr("src.pidfile._pid_alive", lambda pid: pid == 99999)

    with pytest.raises(AlreadyRunning):
        acquire(pidfile)


def test_acquire_sobrescribe_pidfile_stale(tmp_path, monkeypatch):
    """Si el pidfile apunta a un PID muerto, se sobrescribe sin error."""
    pidfile = tmp_path / "jeffri.pid"
    pidfile.write_text("99999")
    monkeypatch.setattr("src.pidfile._pid_alive", lambda pid: False)

    acquire(pidfile)
    assert pidfile.read_text().strip() == str(os.getpid())


def test_acquire_ignora_pidfile_corrupto(tmp_path, monkeypatch):
    """Si el pidfile no tiene un int valido, se sobreescribe."""
    pidfile = tmp_path / "jeffri.pid"
    pidfile.write_text("basura no numero")
    # _pid_alive con pid=0 devuelve False (por la guarda pid <= 0)
    acquire(pidfile)
    assert pidfile.read_text().strip() == str(os.getpid())


def test_acquire_pasa_si_pidfile_tiene_nuestro_pid(tmp_path):
    """Si el pidfile ya contiene NUESTRO PID (re-entry), no falla."""
    pidfile = tmp_path / "jeffri.pid"
    pidfile.write_text(str(os.getpid()))
    # No debe levantar aunque el pid este 'vivo' (somos nosotros mismos).
    acquire(pidfile)
    assert pidfile.exists()


def test_release_borra_pidfile_si_es_nuestro(tmp_path):
    from src.pidfile import _release

    pidfile = tmp_path / "jeffri.pid"
    pidfile.write_text(str(os.getpid()))
    _release(pidfile)
    assert not pidfile.exists()


def test_release_no_borra_pidfile_ajeno(tmp_path):
    from src.pidfile import _release

    pidfile = tmp_path / "jeffri.pid"
    pidfile.write_text("99999")
    _release(pidfile)
    # No es nuestro PID → NO se borra.
    assert pidfile.exists()


def test_pid_alive_falso_para_pid_no_positivo():
    from src.pidfile import _pid_alive

    assert _pid_alive(0) is False
    assert _pid_alive(-1) is False


def test_pid_alive_verdadero_para_nuestro_pid():
    from src.pidfile import _pid_alive

    # Nuestro propio PID siempre esta vivo mientras corramos.
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_falso_para_pid_gigante_inexistente():
    """Un PID muy alto que no puede existir debe reportar False.

    Este es el test de regresion del bug donde os.kill(pid, 0) en Windows daba
    OSError tanto para vivos como muertos y _pid_alive no diferenciaba.
    """
    from src.pidfile import _pid_alive

    # PIDs de Windows son ushort/dword; > 4 mil millones no existe nunca.
    assert _pid_alive(4_000_000_001) is False


def test_pid_alive_verdadero_para_proceso_hijo_recien_arrancado():
    """Un proceso hijo vivo debe reportarse como vivo.

    Regresion: antes _pid_alive() en Windows daba False para cualquier PID
    ajeno vivo, permitiendo doble-arranque del bot.
    """
    import subprocess
    import sys
    import time

    from src.pidfile import _pid_alive

    # Arranca un proceso que duerme 3 segundos y lo consultamos mientras vive.
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(3)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.3)  # dejar que arranque
        assert _pid_alive(proc.pid) is True
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    # Despues de terminar debe reportarse muerto.
    assert _pid_alive(proc.pid) is False
