import time
from pathlib import Path
import pytest
from src.session_detector import detect_active_session, list_recent_sessions, SessionInfo


def test_detect_active_session_returns_most_recent(tmp_path):
    proj1 = tmp_path / "C--Users-Reimo-Desktop-A"
    proj1.mkdir()
    f1 = proj1 / "session-a.jsonl"
    f1.write_text('{"sessionId":"a"}\n')

    time.sleep(0.05)

    proj2 = tmp_path / "C--Users-Reimo-Desktop-B"
    proj2.mkdir()
    f2 = proj2 / "session-b.jsonl"
    f2.write_text('{"sessionId":"b"}\n')

    result = detect_active_session(tmp_path)
    assert result == f2


def test_detect_active_session_returns_none_when_empty(tmp_path):
    assert detect_active_session(tmp_path) is None


def test_list_recent_sessions_returns_sorted(tmp_path):
    for name in ["A", "B", "C"]:
        proj = tmp_path / f"C--Users-Reimo-Desktop-{name}"
        proj.mkdir()
        (proj / f"session-{name.lower()}.jsonl").write_text(f'{{"sessionId":"{name}"}}\n')
        time.sleep(0.05)

    result = list_recent_sessions(tmp_path, limit=2)
    assert len(result) == 2
    assert result[0].folder_name == "C--Users-Reimo-Desktop-C"
    assert result[1].folder_name == "C--Users-Reimo-Desktop-B"


def test_session_info_decoded_folder_name(tmp_path):
    # Claude Code codifica "\" como "-", perdiendo espacios del path. El decode
    # es best-effort: para rutas sin espacios se recupera exactamente; para rutas
    # con espacios se obtiene un path con \ en vez del espacio (aceptable: solo
    # se usa para display, el nombre amigable viene de sessions-index.json).
    proj = tmp_path / "C--Users-john-Desktop-my-project"
    proj.mkdir()
    (proj / "s.jsonl").write_text('{}\n')

    sessions = list_recent_sessions(tmp_path, limit=1)
    assert sessions[0].decoded_path == "C:\\Users\\john\\Desktop\\my\\project"


def test_detect_active_session_skips_deleted_files(tmp_path, monkeypatch):
    proj = tmp_path / "C--Users-Reimo-Desktop-A"
    proj.mkdir()
    f1 = proj / "alive.jsonl"
    f1.write_text('{}\n')
    ghost = proj / "deleted.jsonl"
    ghost.write_text('{}\n')

    real_stat = Path.stat
    def flaky_stat(self, *args, **kwargs):
        if self.name == "deleted.jsonl":
            raise FileNotFoundError(2, "Pretend it was deleted between rglob and stat")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    result = detect_active_session(tmp_path)
    assert result == f1


def test_list_recent_sessions_skips_deleted_files(tmp_path, monkeypatch):
    proj = tmp_path / "C--Users-Reimo-Desktop-A"
    proj.mkdir()
    f1 = proj / "alive.jsonl"
    f1.write_text('{}\n')
    ghost = proj / "deleted.jsonl"
    ghost.write_text('{}\n')

    real_stat = Path.stat
    def flaky_stat(self, *args, **kwargs):
        if self.name == "deleted.jsonl":
            raise FileNotFoundError(2, "Pretend it was deleted")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    result = list_recent_sessions(tmp_path)
    assert len(result) == 1
    assert result[0].path == f1
