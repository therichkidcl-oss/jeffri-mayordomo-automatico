import json
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
    title: str = ""

    @property
    def decoded_path(self) -> str:
        decoded = self.folder_name.replace("C--", "C:\\").replace("-", "\\")
        return decoded.replace("\\\\", "\\").replace("\\ ", " ").replace(
            "C:\\Users\\Reimo\\Desktop\\pyton\\pantalla",
            "C:\\Users\\Reimo\\Desktop\\pyton pantalla",
        )


def get_session_title(jsonl_path: Path, max_chars: int = 60) -> str:
    custom_title = ""
    first_user_content = ""
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "custom-title":
                    custom_title = (event.get("customTitle") or "").strip()
                    if custom_title:
                        break
                if not first_user_content and event.get("type") == "queue-operation" \
                        and event.get("operation") == "enqueue":
                    content = event.get("content")
                    if isinstance(content, str) and content.strip():
                        first_user_content = content.strip()
    except OSError:
        return ""

    title = custom_title or first_user_content or jsonl_path.stem[:8]
    title = " ".join(title.split())
    if len(title) > max_chars:
        title = title[: max_chars - 1] + "…"
    return title


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


def list_recent_sessions(projects_dir: Path, limit: int = 10, with_titles: bool = True) -> list[SessionInfo]:
    pairs = [(p, st) for p in _all_jsonl(projects_dir) if (st := _stat_safely(p)) is not None]
    pairs.sort(key=lambda pair: pair[1].st_mtime, reverse=True)
    sliced = pairs[:limit]
    return [
        SessionInfo(
            path=p,
            folder_name=p.parent.name,
            last_modified=datetime.fromtimestamp(st.st_mtime),
            session_uuid=p.stem,
            title=get_session_title(p) if with_titles else "",
        )
        for p, st in sliced
    ]
