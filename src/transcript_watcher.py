import asyncio
import json
import logging
from pathlib import Path
from typing import Awaitable, Callable
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict], Awaitable[None]]


class _JsonlHandler(FileSystemEventHandler):
    def __init__(self, watcher: "TranscriptWatcher"):
        self.watcher = watcher

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix != ".jsonl":
            return
        if self.watcher.loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self.watcher._on_file_modified(path),
            self.watcher.loop,
        )


class TranscriptWatcher:
    def __init__(self, projects_dir: Path, on_event: EventCallback):
        self.projects_dir = projects_dir
        self.on_event = on_event
        self._observer: Observer | None = None
        self._active_file: Path | None = None
        self._last_offset: int = 0
        self.loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        if self._observer is not None:
            return
        self.loop = asyncio.get_running_loop()
        self._observer = Observer()
        self._observer.schedule(_JsonlHandler(self), str(self.projects_dir), recursive=True)
        self._observer.start()
        logger.info(f"Watcher started on {self.projects_dir}")

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def set_active_file(self, path: Path) -> None:
        if self._active_file == path:
            return
        self._active_file = path
        try:
            self._last_offset = path.stat().st_size
        except OSError:
            self._last_offset = 0
        logger.info(f"Now watching: {path}")

    async def _on_file_modified(self, path: Path) -> None:
        if self._active_file is None or path != self._active_file:
            return
        try:
            with open(path, "rb") as f:
                f.seek(self._last_offset)
                new_bytes = f.read()

            last_nl = new_bytes.rfind(b"\n")
            if last_nl < 0:
                return

            complete = new_bytes[: last_nl + 1]
            new_offset = self._last_offset + len(complete)

            for raw_line in complete.decode("utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug(f"Skipping malformed JSON line: {line[:100]}")
                    continue
                await self.on_event(event)

            self._last_offset = new_offset
        except Exception as e:
            logger.exception(f"Error processing {path}: {e}")
