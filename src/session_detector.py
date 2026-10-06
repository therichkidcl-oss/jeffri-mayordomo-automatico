import json
import os
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
        # Claude Code codifica cada "\" como "-" en el nombre de carpeta, lo que
        # pierde los espacios del path original. Este decode es best-effort.
        decoded = self.folder_name.replace("C--", "C:\\").replace("-", "\\")
        return decoded.replace("\\\\", "\\").replace("\\ ", " ")


@dataclass
class ProjectInfo:
    folder_name: str
    display_name: str
    last_modified: datetime
    session_count: int
    folder_path: Path


def _read_cwd_from_jsonl(jsonl_path: Path) -> str | None:
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i > 20:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = event.get("cwd")
                if isinstance(cwd, str) and cwd:
                    return cwd
    except OSError:
        return None
    return None


def read_sessions_index(folder_path: Path) -> dict | None:
    index_file = folder_path / "sessions-index.json"
    if not index_file.exists():
        return None
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _folder_display_name(folder_path: Path) -> str:
    index = read_sessions_index(folder_path)
    if index:
        original_path = index.get("originalPath")
        if isinstance(original_path, str) and original_path:
            return os.path.basename(original_path) or original_path
    for jsonl in folder_path.glob("*.jsonl"):
        cwd = _read_cwd_from_jsonl(jsonl)
        if cwd:
            return os.path.basename(cwd) or cwd
    name = folder_path.name
    if name.startswith("C--"):
        name = name[3:]
    parts = name.split("-")
    # Primer segmento siempre es "Users"; el siguiente es el nombre del
    # usuario (variable por maquina); los siguientes suelen ser una carpeta
    # standar. Los descartamos para quedarnos con el nombre del proyecto.
    _COMMON_ROOTS = {"Desktop", "Documents", "Downloads", "Pictures", "code", "src", "repos"}
    if parts and parts[0] == "Users":
        parts.pop(0)
        if parts:  # nombre de usuario
            parts.pop(0)
    while parts and parts[0] in _COMMON_ROOTS:
        parts.pop(0)
    return " ".join(parts) if parts else folder_path.name


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


def list_projects(projects_dir: Path) -> list[ProjectInfo]:
    if not projects_dir.exists():
        return []
    projects: list[ProjectInfo] = []
    for folder in projects_dir.iterdir():
        if not folder.is_dir():
            continue
        index = read_sessions_index(folder)
        if index is not None:
            entries = index.get("entries", [])
            session_count = len(entries)
            if session_count == 0:
                continue
            mtimes = [e.get("fileMtime", 0) / 1000.0 for e in entries if e.get("fileMtime")]
            if not mtimes:
                continue
            last_mod = datetime.fromtimestamp(max(mtimes))
        else:
            jsonls = list(folder.glob("*.jsonl"))
            if not jsonls:
                continue
            mtimes = [st.st_mtime for j in jsonls if (st := _stat_safely(j)) is not None]
            if not mtimes:
                continue
            session_count = len(jsonls)
            last_mod = datetime.fromtimestamp(max(mtimes))

        projects.append(ProjectInfo(
            folder_name=folder.name,
            display_name=_folder_display_name(folder),
            last_modified=last_mod,
            session_count=session_count,
            folder_path=folder,
        ))
    projects.sort(key=lambda p: p.last_modified, reverse=True)
    return projects


def list_sessions_in_folder(folder_path: Path, limit: int = 20, with_titles: bool = True) -> list[SessionInfo]:
    if not folder_path.exists() or not folder_path.is_dir():
        return []

    index = read_sessions_index(folder_path)
    if index is not None:
        entries = sorted(
            index.get("entries", []),
            key=lambda e: e.get("fileMtime", 0),
            reverse=True,
        )[:limit]
        sessions: list[SessionInfo] = []
        for entry in entries:
            full_path = entry.get("fullPath")
            if not isinstance(full_path, str):
                continue
            p = Path(full_path)
            mtime_ms = entry.get("fileMtime", 0)
            last_mod = datetime.fromtimestamp(mtime_ms / 1000.0) if mtime_ms else datetime.now()
            first_prompt = (entry.get("firstPrompt") or "").strip()
            title = ""
            if with_titles:
                if p.exists():
                    title = get_session_title(p)
                if not title and first_prompt:
                    title = first_prompt[:60] + ("…" if len(first_prompt) > 60 else "")
            sessions.append(SessionInfo(
                path=p,
                folder_name=folder_path.name,
                last_modified=last_mod,
                session_uuid=entry.get("sessionId", p.stem),
                title=title,
            ))
        return sessions

    pairs = [(p, st) for p in folder_path.glob("*.jsonl") if (st := _stat_safely(p)) is not None]
    pairs.sort(key=lambda pair: pair[1].st_mtime, reverse=True)
    return [
        SessionInfo(
            path=p,
            folder_name=p.parent.name,
            last_modified=datetime.fromtimestamp(st.st_mtime),
            session_uuid=p.stem,
            title=get_session_title(p) if with_titles else "",
        )
        for p, st in pairs[:limit]
    ]


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
