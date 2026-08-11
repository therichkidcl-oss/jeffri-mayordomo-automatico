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
        # Offset por archivo: al volver a una sesion se REANUDA donde quedamos
        # (no seek-to-end) para no perder eventos escritos mientras miraba otra.
        self._offsets: dict[str, int] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self._read_lock: asyncio.Lock | None = None
        self._seen_event_ids: set[str] = set()

    def start(self) -> None:
        if self._observer is not None:
            return
        self.loop = asyncio.get_running_loop()
        self._read_lock = asyncio.Lock()
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
        # Guarda donde quedamos en el archivo que dejamos.
        if self._active_file is not None:
            self._offsets[str(self._active_file)] = self._last_offset
        self._active_file = path
        key = str(path)
        if key in self._offsets:
            # Ya visto: REANUDAR (no perder lo escrito mientras mirabamos otra).
            self._last_offset = self._offsets[key]
        else:
            # Primera vez: arrancar desde el final (no volcar el historial).
            try:
                self._last_offset = path.stat().st_size
            except OSError:
                self._last_offset = 0
            self._offsets[key] = self._last_offset
        # OJO: NO limpiar _seen_event_ids — el dedup global (por uuid) debe
        # persistir entre cambios; el offset ya evita releer lo viejo.
        logger.info(f"Now watching: {path}")

    async def catch_up(self) -> None:
        """Lee y reenvia lo pendiente del archivo activo (desde _last_offset).
        Se llama justo despues de cambiar de sesion para no esperar al proximo
        write y reenviar de inmediato lo que se escribio mientras mirabamos otra.
        """
        if self._active_file is not None:
            await self._read_new(self._active_file)

    async def _on_file_modified(self, path: Path) -> None:
        if self._active_file is None or path != self._active_file:
            return
        await self._read_new(path)

    async def _read_new(self, path: Path) -> None:
        if self._read_lock is None:
            return
        async with self._read_lock:
            try:
                with open(path, "rb") as f:
                    f.seek(self._last_offset)
                    new_bytes = f.read()

                last_nl = new_bytes.rfind(b"\n")
                if last_nl < 0:
                    return

                complete = new_bytes[: last_nl + 1]
                new_offset = self._last_offset + len(complete)

                events_to_emit: list[dict] = []
                for raw_line in complete.decode("utf-8", errors="replace").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug(f"Skipping malformed JSON line: {line[:100]}")
                        continue
                    eid = event.get("uuid") or event.get("id") or event.get("timestamp")
                    if isinstance(eid, str):
                        if eid in self._seen_event_ids:
                            logger.debug(f"Skipping duplicate event uuid={eid[:8]}")
                            continue
                        self._seen_event_ids.add(eid)
                        if len(self._seen_event_ids) > 2000:
                            self._seen_event_ids = set(list(self._seen_event_ids)[-1000:])
                    events_to_emit.append(event)

                self._last_offset = new_offset
                self._offsets[str(path)] = new_offset

                for event in events_to_emit:
                    await self.on_event(event)
            except Exception as e:
                logger.exception(f"Error processing {path}: {e}")
