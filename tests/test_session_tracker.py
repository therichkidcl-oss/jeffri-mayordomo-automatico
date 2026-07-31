from pathlib import Path

from src.session_tracker import SessionTracker

A = Path("C--Users-Reimo-Desktop-IA-HUB/a.jsonl")
B = Path("C--Users-Reimo-Desktop-Fc-Piscina-Empresa/b.jsonl")


def test_first_detection_sets_current_without_announcing():
    t = SessionTracker(stability=2)
    assert t.observe(A, paused=False) is None  # 1ra lectura, aun no estable
    assert t.observe(A, paused=False) is None  # estable pero es la primera => no anuncia
    assert t.current == A


def test_same_session_never_announces():
    t = SessionTracker(stability=2)
    for _ in range(5):
        assert t.observe(A, paused=False) is None
    assert t.current == A


def test_flip_flop_does_not_announce():
    # A,B,A,B,A,B alternando: ninguno llega a 2 lecturas seguidas => sin avisos.
    t = SessionTracker(stability=2)
    t.observe(A, paused=False)
    t.observe(A, paused=False)  # current = A
    seq = [B, A, B, A, B, A]
    announces = [t.observe(s, paused=False) for s in seq]
    assert all(x is None for x in announces), f"no debe anunciar en flip-flop: {announces}"
    assert t.current == A  # se queda en el estable original


def test_stable_switch_announces_when_active():
    t = SessionTracker(stability=2)
    t.observe(A, paused=False)
    t.observe(A, paused=False)  # current = A
    assert t.observe(B, paused=False) is None  # B 1ra vez
    assert t.observe(B, paused=False) == B      # B estable => anuncia
    assert t.current == B


def test_paused_switches_silently_no_announce():
    t = SessionTracker(stability=2)
    t.observe(A, paused=False)
    t.observe(A, paused=False)  # current = A
    assert t.observe(B, paused=True) is None
    assert t.observe(B, paused=True) is None  # estable pero en pausa => silencio
    assert t.current == B  # el seguimiento cambia por dentro, sin avisar


def test_resume_after_paused_switch_does_not_spam():
    t = SessionTracker(stability=2)
    t.observe(A, paused=False)
    t.observe(A, paused=False)  # current = A
    t.observe(B, paused=True)
    t.observe(B, paused=True)   # current = B (silencioso)
    # al reanudar, B ya es la actual => no anuncia nada
    assert t.observe(B, paused=False) is None
    assert t.observe(B, paused=False) is None


def test_none_active_is_ignored():
    t = SessionTracker(stability=2)
    assert t.observe(None, paused=False) is None
    assert t.current is None
