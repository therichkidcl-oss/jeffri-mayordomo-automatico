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
        if path.suffix == ".jsonl":
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
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def start(self) -> None:
        if self._observer is not None:
            return
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
        self._last_offset = path.stat().st_size if path.exists() else 0
        logger.info(f"Now watching: {path}")

    async def _on_file_modified(self, path: Path) -> None:
        if path != self._active_file:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(self._last_offset)
                new_data = f.read()
                self._last_offset = f.tell()

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug(f"Skipping malformed JSON line: {line[:100]}")
                    continue
                await self.on_event(event)
        except Exception as e:
            logger.exception(f"Error processing {path}: {e}")
