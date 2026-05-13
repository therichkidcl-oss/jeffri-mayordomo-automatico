from dataclasses import dataclass
from datetime import datetime
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


def detect_active_session(projects_dir: Path) -> Path | None:
    files = _all_jsonl(projects_dir)
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def list_recent_sessions(projects_dir: Path, limit: int = 10) -> list[SessionInfo]:
    files = _all_jsonl(projects_dir)
    sorted_files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [
        SessionInfo(
            path=p,
            folder_name=p.parent.name,
            last_modified=datetime.fromtimestamp(p.stat().st_mtime),
            session_uuid=p.stem,
        )
        for p in sorted_files
    ]
