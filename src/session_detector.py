from dataclasses import dataclass
from datetime import datetime
from os import stat_result
from pathlib import Path


@dataclass
class SessionInfo:
    path: Path
    folder_name: str
    last_modified: datetime
    session_uuid: str

    @property
    def decoded_path(self) -> str:
        decoded = self.folder_name.replace("C--", "C:\\").replace("-", "\\")
        return decoded.replace("\\\\", "\\").replace("\\ ", " ").replace(
            "C:\\Users\\Reimo\\Desktop\\pyton\\pantalla",
            "C:\\Users\\Reimo\\Desktop\\pyton pantalla",
        )


def _all_jsonl(projects_dir: Path) -> list[Path]:
    if not projects_dir.exists():
        return []
    return [p for p in projects_dir.rglob("*.jsonl") if p.is_file()]


def _stat_safely(path: Path) -> stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


def detect_active_session(projects_dir: Path) -> Path | None:
    pairs = [(p, st) for p in _all_jsonl(projects_dir) if (st := _stat_safely(p)) is not None]
    if not pairs:
        return None
    return max(pairs, key=lambda pair: pair[1].st_mtime)[0]


def list_recent_sessions(projects_dir: Path, limit: int = 10) -> list[SessionInfo]:
    pairs = [(p, st) for p in _all_jsonl(projects_dir) if (st := _stat_safely(p)) is not None]
    pairs.sort(key=lambda pair: pair[1].st_mtime, reverse=True)
    return [
        SessionInfo(
            path=p,
            folder_name=p.parent.name,
            last_modified=datetime.fromtimestamp(st.st_mtime),
            session_uuid=p.stem,
        )
        for p, st in pairs[:limit]
    ]
